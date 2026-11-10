"""Queue and execute proposal-only AI labeling over masked candidate frames."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import any_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.config import DEV_APP_ENVS, settings
from aprkb.modules.audit.service import record_event
from aprkb.modules.corpus.models import Article, ArticleSection, License, Sentence
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.mining.candidate_label_repository import upsert_proposals
from aprkb.modules.mining.frame_labels import FrameSourceLabelData, build_frame_labels
from aprkb.modules.mining.frame_sections import FrameSectionDistribution, summarize_frame_sections
from aprkb.modules.mining.label_merge import merge_frame_labels
from aprkb.modules.mining.labelers import (
    FrameLabeler,
    FrameLabelerError,
    FrameLabelingQuotaError,
    FrameLabelingRequestError,
    FrameLabelOutput,
    FrameLabelPayload,
    GroqFrameLabeler,
    NullFrameLabeler,
    validate_frame_label_output,
)
from aprkb.modules.mining.models import Candidate, Job
from aprkb.modules.mining.read_filter import unknown_single_paper_reason
from aprkb.policies.loader import load_policy_bundle
from aprkb.policies.schemas import FrameLabelVocabularyPolicy

FRAME_LABEL_JOB_TYPE = "label_frames"
FRAME_LABEL_FILTER = "pending_cluster_two_papers_v1"
_CANDIDATE_PAGE_SIZE = 100


@dataclass(frozen=True)
class CandidateSourceMetadata:
    sentence_id: UUID
    article_id: UUID
    section_code: str | None
    genre_code: str | None
    license_code: str
    allows_mining: bool
    allows_display: bool


@dataclass(frozen=True)
class FrameLabelEligibility:
    eligible: bool
    reason: str | None
    distribution: FrameSectionDistribution


def frame_label_eligibility(
    *,
    source_sentence_ids: list[UUID],
    source_rows: list[CandidateSourceMetadata],
    threshold: float,
) -> FrameLabelEligibility:
    """Check current rights and the read-side II.2 rule using metadata only."""
    rows_by_sentence = {row.sentence_id: row for row in source_rows}
    if len(rows_by_sentence) != len(source_sentence_ids) or any(
        not row.allows_mining or not row.allows_display for row in source_rows
    ):
        return FrameLabelEligibility(
            eligible=False,
            reason="rights_denied_or_source_missing",
            distribution=summarize_frame_sections([], dominant_share_threshold=threshold),
        )
    distribution = summarize_frame_sections(
        [(row.article_id, row.section_code) for row in source_rows],
        dominant_share_threshold=threshold,
    )
    if reason := unknown_single_paper_reason(distribution, enabled=True):
        return FrameLabelEligibility(False, reason, distribution)
    if distribution.paper_count < 2:
        return FrameLabelEligibility(False, "fewer_than_two_papers", distribution)
    return FrameLabelEligibility(True, None, distribution)


def frame_groq_is_enabled(provider: str) -> bool:
    return (
        settings.app_env in DEV_APP_ENVS
        and settings.frame_labeler == "groq"
        and provider == "groq"
        and settings.groq_allow_external_processing
        and settings.groq_api_key is not None
    )


def build_frame_labeler() -> FrameLabeler:
    policy = load_policy_bundle()
    if settings.frame_labeler == "null":
        return NullFrameLabeler()
    if not frame_groq_is_enabled(policy.frame_labeling.provider):
        raise FrameLabelerError("Frame labeling is disabled or external processing is not approved")
    assert settings.groq_api_key is not None
    return GroqFrameLabeler(
        api_key=settings.groq_api_key.get_secret_value(),
        policy=policy.frame_labeling,
        vocabulary=policy.frame_label_vocabulary,
    )


async def enqueue_frame_label_job(
    session: AsyncSession,
    *,
    actor: ApiClient,
    request_id: str,
) -> Job:
    policies = load_policy_bundle()
    if not frame_groq_is_enabled(policies.frame_labeling.provider):
        raise HTTPException(
            status_code=409,
            detail="Frame labeling is disabled or external processing is not approved",
        )
    existing = await session.scalar(
        select(Job)
        .where(
            Job.type == FRAME_LABEL_JOB_TYPE,
            Job.status.in_(["queued", "processing"]),
            Job.payload["candidate_filter"].as_string() == FRAME_LABEL_FILTER,
        )
        .order_by(Job.created_at, Job.id)
        .limit(1)
    )
    if existing is not None:
        return existing
    job = Job(
        type=FRAME_LABEL_JOB_TYPE,
        payload={
            "candidate_filter": FRAME_LABEL_FILTER,
            "batch_size": policies.frame_labeling.batch_size,
        },
        status="queued",
        created_by=actor.id,
    )
    session.add(job)
    await session.flush()
    from aprkb.modules.audit.service import record_event

    await record_event(
        session,
        actor_id=actor.id,
        action="frame_labels.label.enqueue",
        entity_type="frame_label_job",
        entity_id=job.id,
        after={"job_id": str(job.id), "candidate_filter": FRAME_LABEL_FILTER},
        request_id=request_id,
    )
    await session.commit()
    return job


async def label_candidate_frames(
    session: AsyncSession,
    *,
    job_payload: dict[str, Any],
    request_id: str,
    labeler: FrameLabeler | None = None,
) -> dict[str, Any]:
    """Label eligible frames in two resumable passes without reading sentence text."""
    if job_payload.get("candidate_filter") != FRAME_LABEL_FILTER:
        raise ValueError("Frame-label job has an unsupported candidate filter")
    if labeler is None:
        labeler = build_frame_labeler()
    if isinstance(labeler, NullFrameLabeler):
        return {"frames_scanned": 0, "frames_labeled": 0, "provider": "null"}

    policies = load_policy_bundle()
    requested_batch_size = job_payload.get("batch_size")
    batch_size = (
        requested_batch_size
        if isinstance(requested_batch_size, int) and 1 <= requested_batch_size <= 100
        else policies.frame_labeling.batch_size
    )
    counters: Counter[str] = Counter()
    agreement: dict[str, Counter[str]] = defaultdict(Counter)
    value_counts: dict[str, Counter[str]] = defaultdict(Counter)
    stopped: str | None = None
    offset = 0

    while True:
        candidates = list(
            await session.scalars(
                select(Candidate)
                .where(Candidate.status == "pending", Candidate.cluster_key.is_not(None))
                .order_by(Candidate.id)
                .offset(offset)
                .limit(_CANDIDATE_PAGE_SIZE)
            )
        )
        if not candidates:
            break
        offset += len(candidates)
        counters["candidates_scanned"] += len(candidates)
        candidate_ids = [candidate.id for candidate in candidates]
        source_rows_by_candidate = await _candidate_source_metadata(session, candidate_ids)
        prepared: list[tuple[Candidate, FrameLabelPayload, dict[str, str]]] = []
        for candidate in candidates:
            source_rows = source_rows_by_candidate.get(candidate.id, [])
            eligibility = frame_label_eligibility(
                source_sentence_ids=candidate.source_sentence_ids,
                source_rows=source_rows,
                threshold=policies.mining_filter.frame_section_dominant_share_threshold,
            )
            if not eligibility.eligible:
                counters[eligibility.reason or "ineligible"] += 1
                continue
            label_sources = [
                FrameSourceLabelData(
                    article_id=str(row.article_id),
                    genre_code=row.genre_code,
                    license_code=row.license_code,
                    allows_mining=row.allows_mining,
                    allows_display=row.allows_display,
                )
                for row in source_rows
            ]
            base_labels = build_frame_labels(
                canonical_frame=candidate.canonical_frame,
                slot_types={},
                epistemic_strength=candidate.epistemic_strength,
                source_sentence_count=len(candidate.source_sentence_ids),
                cluster_key=candidate.cluster_key,
                sources=label_sources,
                section_distribution=eligibility.distribution,
                dominant_share_threshold=policies.mining_filter.frame_section_dominant_share_threshold,
                anchor_policy=policies.frame_function_anchors,
            )
            anchors = {
                field: label.value
                for field in ("function_group", "intent", "general_function")
                if (label := getattr(base_labels, field)).status == "proposed"
                and isinstance(label.value, str)
            }
            payload = FrameLabelPayload(
                candidate_id=candidate.id,
                canonical_frame=candidate.canonical_frame,
                family=_candidate_family(candidate.cluster_key),
                epistemic_strength=candidate.epistemic_strength,
                paper_count=eligibility.distribution.paper_count,
                observed_section_counts={
                    code: count
                    for code, count in eligibility.distribution.counts.items()
                    if count > 0
                },
                anchor_proposal=anchors or None,
            )
            prepared.append((candidate, payload, anchors))
        counters["frames_eligible"] += len(prepared)
        if not prepared:
            continue

        pass_a, pass_b, calls, failed_ids, stop_reason = await _run_two_passes(
            prepared,
            labeler=labeler,
            batch_size=batch_size,
            vocabulary=policies.frame_label_vocabulary,
        )
        counters["provider_batches"] += calls
        counters["label_failed"] += len(failed_ids)
        if stop_reason is not None:
            stopped = stop_reason

        run_id = request_id[:64]
        for _candidate, payload, anchors in prepared:
            candidate_id = payload.candidate_id
            if (
                candidate_id in failed_ids
                or candidate_id not in pass_a
                or candidate_id not in pass_b
            ):
                continue
            merged = merge_frame_labels(
                candidate_id=candidate_id,
                pass_a=pass_a[candidate_id],
                pass_b=pass_b[candidate_id],
                anchors=anchors,
                vocabulary=policies.frame_label_vocabulary,
            )
            for label in merged:
                agreement[label.label_code][label.agreement] += 1
                if label.value is not None:
                    value_counts[label.label_code][label.value] += 1
            counters["label_rows_written"] += await upsert_proposals(
                session,
                candidate_id=candidate_id,
                labels=merged,
                run_id=run_id,
            )
            counters["frames_merged"] += 1
        await session.flush()
        await session.commit()
        if stopped is not None:
            break

    result: dict[str, Any] = {
        **dict(counters),
        "provider": labeler.model,
        "prompt_versions": [
            policies.frame_labeling.prompt_version_a,
            policies.frame_labeling.prompt_version_b,
        ],
        "tokens_used": labeler.total_tokens,
        "agreement_by_label": {
            label_code: dict(sorted(counts.items()))
            for label_code, counts in sorted(agreement.items())
        },
        "value_counts_by_label": {
            label_code: dict(sorted(counts.items()))
            for label_code, counts in sorted(value_counts.items())
        },
    }
    if stopped is not None:
        result["stopped"] = stopped
    await record_event(
        session,
        actor_id=None,
        action="frame_labels.label.complete",
        entity_type="frame_label_run",
        after={
            "counts": dict(counters),
            "agreement_by_label": result["agreement_by_label"],
            "value_counts_by_label": result["value_counts_by_label"],
            "stopped": stopped,
        },
        request_id=request_id,
    )
    await session.commit()
    return result


async def _candidate_source_metadata(
    session: AsyncSession, candidate_ids: list[UUID]
) -> dict[UUID, list[CandidateSourceMetadata]]:
    from aprkb.modules.taxonomy.models import ArticleGenre

    rows = await session.execute(
        select(
            Candidate.id,
            Sentence.id,
            Article.id,
            ArticleSection.section_code,
            ArticleGenre.code,
            License.code,
            License.allows_mining,
            License.allows_display,
        )
        .join(Sentence, Sentence.id == any_(Candidate.source_sentence_ids))
        .join(Article, Article.id == Sentence.article_id)
        .join(License, License.id == Article.license_id)
        .outerjoin(ArticleSection, ArticleSection.id == Sentence.article_section_id)
        .outerjoin(ArticleGenre, ArticleGenre.id == Article.genre_id)
        .where(Candidate.id.in_(candidate_ids))
        .order_by(Candidate.id, Article.id, Sentence.id)
        .with_for_update(of=License)
    )
    result: defaultdict[UUID, list[CandidateSourceMetadata]] = defaultdict(list)
    for candidate_id, sentence_id, article_id, section, genre, code, mining, display in rows:
        result[candidate_id].append(
            CandidateSourceMetadata(
                sentence_id=sentence_id,
                article_id=article_id,
                section_code=section,
                genre_code=genre,
                license_code=code,
                allows_mining=bool(mining),
                allows_display=bool(display),
            )
        )
    return dict(result)


def _candidate_family(cluster_key: str | None) -> str:
    if cluster_key and cluster_key.startswith("construction="):
        construction_id = cluster_key.removeprefix("construction=").split(":", 1)[0]
        return f"Tier 2:{construction_id}"
    return "Tier 1"


async def _run_two_passes(
    prepared: list[tuple[Candidate, FrameLabelPayload, dict[str, str]]],
    *,
    labeler: FrameLabeler,
    batch_size: int,
    vocabulary: FrameLabelVocabularyPolicy,
) -> tuple[
    dict[UUID, FrameLabelOutput],
    dict[UUID, FrameLabelOutput],
    int,
    set[UUID],
    str | None,
]:
    payloads = [payload for _, payload, _ in prepared]
    pass_results: list[dict[UUID, FrameLabelOutput]] = []
    calls = 0
    failed: set[UUID] = set()
    for variant in ("a", "b"):
        ordered = _pass_order(payloads, batch_size, variant)
        results: dict[UUID, FrameLabelOutput] = {}
        for batch in ordered:
            try:
                outputs = await labeler.label_batch(frames=batch, prompt_variant=variant)
            except FrameLabelingQuotaError:
                return (pass_results[0] if pass_results else {}, results, calls, failed, "quota")
            except FrameLabelingRequestError:
                return (
                    pass_results[0] if pass_results else {},
                    results,
                    calls,
                    failed,
                    "request_error",
                )
            except FrameLabelerError:
                failed.update(item.candidate_id for item in batch)
                continue
            calls += 1
            expected = {item.candidate_id for item in batch}
            returned = [item.candidate_id for item in outputs]
            if len(returned) != len(set(returned)) or set(returned) - expected:
                failed.update(expected)
                continue
            by_id = {item.candidate_id: item for item in outputs}
            for candidate_id in expected:
                output = by_id.get(candidate_id)
                if output is None:
                    failed.add(candidate_id)
                    continue
                try:
                    results[candidate_id] = validate_frame_label_output(
                        output, vocabulary=vocabulary
                    )
                except FrameLabelerError:
                    failed.add(candidate_id)
        pass_results.append(results)
    if len(pass_results) < 2:
        return pass_results[0], {}, calls, failed, "request_error"
    failed.update(set(pass_results[0]) ^ set(pass_results[1]))
    return pass_results[0], pass_results[1], calls, failed, None


def _pass_order(
    payloads: list[FrameLabelPayload],
    batch_size: int,
    variant: Literal["a", "b"],
) -> list[list[FrameLabelPayload]]:
    ordered = sorted(payloads, key=lambda item: item.candidate_id.int)
    if variant == "b":
        if len(ordered) > batch_size:
            offset = max(1, batch_size // 2)
            ordered = ordered[offset:] + ordered[:offset]
        else:
            ordered.reverse()
    return [ordered[index : index + batch_size] for index in range(0, len(ordered), batch_size)]
