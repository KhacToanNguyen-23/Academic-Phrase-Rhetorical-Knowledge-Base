"""Create gold sampling batches without copying source text into gold storage."""

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.config import DEV_APP_ENVS, settings
from aprkb.modules.audit.service import record_event
from aprkb.modules.corpus.models import Article, ArticleSection, License, Sentence
from aprkb.modules.gold.labelers import (
    GoldLabeler,
    GoldLabelerError,
    GoldLabelingQuotaError,
    GoldLabelingRequestError,
    GroqGoldLabeler,
)
from aprkb.modules.gold.labels import GoldLabels
from aprkb.modules.gold.models import GoldItem
from aprkb.modules.gold.sampling import SamplingRow, select_sample
from aprkb.modules.gold.schemas import (
    GoldItemDetail,
    GoldItemSummary,
    GoldReviewDecision,
    GoldReviewResult,
    GoldSampleCreate,
    GoldSampleResult,
    GoldStats,
)
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.mining.models import Job
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.modules.mining.stages.sentence_filter import SentenceFilter
from aprkb.policies.loader import load_policy_bundle


async def create_sample(
    session: AsyncSession,
    *,
    payload: GoldSampleCreate,
    actor: ApiClient | None,
    request_id: str,
) -> GoldSampleResult:
    rows = list(
        await session.execute(
            select(Sentence, Article.id, ArticleSection.section_code)
            .join(Article, Article.id == Sentence.article_id)
            .join(License, License.id == Article.license_id)
            .outerjoin(ArticleSection, ArticleSection.id == Sentence.article_section_id)
            .where(
                License.allows_mining.is_(True),
                Article.ingest_status == "ready",
                Article.source == "slr",
            )
            .order_by(Sentence.article_id, Sentence.char_start, Sentence.id)
        )
    )
    policies = load_policy_bundle()
    mining_filter = SentenceFilter(
        min_words=policies.mining_filter.sentence_filter.min_words,
        max_words=policies.mining_filter.sentence_filter.max_words,
        noise=policies.mining_filter.noise_filter,
    )
    eligible: list[SamplingRow] = []
    for sentence, article_id, section_code in rows:
        # Rejected sentences fill a small quota so the filter itself can be evaluated.
        eligible.append(
            SamplingRow(
                sentence_id=sentence.id,
                article_id=article_id,
                section=section_code or "OTHER",
                text=sentence.text,
                filter_reason=mining_filter.reject_reason(
                    MiningItem(sentence.text, [sentence.id], section_code)
                ),
            )
        )
    try:
        chosen, test_ids = select_sample(
            eligible,
            size=payload.size,
            seed=payload.seed,
            max_per_article=payload.max_per_article,
            filtered_fraction=policies.gold_sampling.filtered_fraction,
            test_fraction=policies.gold_sampling.test_fraction,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Not enough eligible sentences") from error

    by_id = {sentence.id: sentence for sentence, _, _ in rows}
    batch = uuid.uuid4().hex
    items: list[GoldItem] = []
    for row in chosen:
        sentence = by_id[row.sentence_id]
        items.append(
            GoldItem(
                article_id=row.article_id,
                sentence_id=row.sentence_id,
                char_start=sentence.char_start,
                char_end=sentence.char_end,
                text_sha256=hashlib.sha256(sentence.text.encode("utf-8")).hexdigest(),
                section_at_sampling=row.section,
                split="test" if row.sentence_id in test_ids else "dev",
                sample_batch=batch,
                guideline_version=policies.gold_labeling.guideline_version,
                status="pending_ai",
                created_by=actor.id if actor is not None else None,
            )
        )
    session.add_all(items)
    await session.flush()
    await record_event(
        session,
        actor_id=actor.id if actor is not None else None,
        action="gold.sample.create",
        entity_type="gold_sample_batch",
        entity_id=None,
        after={
            "sample_batch": batch,
            "count": len(items),
            "test_count": len(test_ids),
            "filtered_count": sum(row.filter_reason is not None for row in chosen),
            "sampling_policy_version": policies.gold_sampling.version,
        },
        request_id=request_id,
    )
    await session.commit()
    return GoldSampleResult(
        sample_batch=batch,
        count=len(items),
        test_count=len(test_ids),
    )


async def delete_sample_batch(
    session: AsyncSession,
    *,
    sample_batch: str,
    request_id: str,
) -> int:
    """Delete an unlabeled sample batch and audit the deletion atomically."""
    items = list(
        await session.scalars(
            select(GoldItem)
            .where(GoldItem.sample_batch == sample_batch)
            .order_by(GoldItem.id)
            .with_for_update()
        )
    )
    if not items:
        raise ValueError("Gold sample batch not found")
    if any(item.ai_labels is not None or item.final_labels is not None for item in items):
        raise ValueError("Cannot delete a gold sample batch that contains labels")

    await record_event(
        session,
        actor_id=None,
        action="gold.sample.delete",
        entity_type="gold_sample_batch",
        before={"sample_batch": sample_batch, "count": len(items)},
        after={"deleted_count": len(items)},
        request_id=request_id,
    )
    for item in items:
        await session.delete(item)
    await session.commit()
    return len(items)


async def enqueue_label_job(
    session: AsyncSession,
    *,
    sample_batch: str,
    actor: ApiClient,
    request_id: str,
) -> Job:
    """Queue draft labeling without reading any article content."""
    policies = load_policy_bundle()
    if not _groq_is_enabled(policies.gold_labeling.provider):
        raise HTTPException(
            status_code=409, detail="Gold labeling is disabled or rights are not approved"
        )
    pending = await session.scalar(
        select(GoldItem.id)
        .where(
            GoldItem.sample_batch == sample_batch,
            GoldItem.status.in_(["pending_ai", "label_failed"]),
        )
        .limit(1)
    )
    if pending is None:
        raise ValueError("No unlabeled gold items in sample batch")
    job = Job(
        type="label_gold",
        payload={"sample_batch": sample_batch},
        status="queued",
        created_by=actor.id,
    )
    session.add(job)
    await session.flush()
    await record_event(
        session,
        actor_id=actor.id,
        action="gold.label.enqueue",
        entity_type="gold_sample_batch",
        after={"sample_batch": sample_batch, "job_id": str(job.id)},
        request_id=request_id,
    )
    await session.commit()
    return job


async def label_sample_batch(
    session: AsyncSession,
    *,
    sample_batch: str,
    request_id: str,
    labeler: GoldLabeler | None = None,
    limit: int | None = None,
) -> dict[str, int | str]:
    """Label one batch after a separate rights check, never logging source content."""
    policies = load_policy_bundle()
    if labeler is None:
        if not _groq_is_enabled(policies.gold_labeling.provider):
            raise GoldLabelerError(
                "Gold labeling is disabled or external processing is not approved"
            )
        assert settings.groq_api_key is not None
        labeler = GroqGoldLabeler(
            api_key=settings.groq_api_key.get_secret_value(),
            policy=policies.gold_labeling,
            guideline=_load_gold_guideline(policies.gold_labeling.guideline_version),
        )

    # Load only item and license metadata first. Do not select source text until every
    # sentence in the selected batch has passed the current rights check.
    rows = list(
        await session.execute(
            select(GoldItem, License.allows_mining)
            .join(Article, Article.id == GoldItem.article_id)
            .join(License, License.id == Article.license_id)
            .where(
                GoldItem.sample_batch == sample_batch,
                GoldItem.status.in_(["pending_ai", "label_failed"]),
            )
            .order_by(GoldItem.id)
            .limit(limit)
            .with_for_update(of=[GoldItem, License])
        )
    )
    if not rows:
        raise ValueError("Gold sample batch has no items awaiting labels")
    if any(not allows_mining or item.sentence_id is None for item, allows_mining in rows):
        raise GoldLabelerError("Gold source is unavailable or no longer licensed")

    from aprkb.modules.corpus.models import Sentence

    article_ids = {item.article_id for item, _ in rows}
    source_rows = list(
        await session.execute(
            select(Sentence, ArticleSection.section_code)
            .join(Article, Article.id == Sentence.article_id)
            .join(License, License.id == Article.license_id)
            .outerjoin(ArticleSection, ArticleSection.id == Sentence.article_section_id)
            .where(Article.id.in_(article_ids), License.allows_mining.is_(True))
            .order_by(Sentence.article_id, Sentence.char_start, Sentence.id)
        )
    )
    sentences = {sentence.id: (sentence, section) for sentence, section in source_rows}
    context_by_id: dict[UUID, tuple[str | None, str | None]] = {}
    grouped: dict[tuple[UUID, str], list[Sentence]] = {}
    for sentence, section in source_rows:
        if section is not None:
            grouped.setdefault((sentence.article_id, section), []).append(sentence)
    for siblings in grouped.values():
        for index, sentence in enumerate(siblings):
            context_by_id[sentence.id] = (
                siblings[index - 1].text if index > 0 else None,
                siblings[index + 1].text if index + 1 < len(siblings) else None,
            )
    labeled = 0
    stale = 0
    stopped: GoldLabelingRequestError | None = None
    for item, _ in rows:
        source = sentences.get(item.sentence_id) if item.sentence_id is not None else None
        source_sentence = source[0] if source is not None else None
        current_section = source[1] if source is not None else None
        if (
            source_sentence is None
            or source_sentence.article_id != item.article_id
            or hashlib.sha256(source_sentence.text.encode("utf-8")).hexdigest() != item.text_sha256
        ):
            item.status = "stale"
            stale += 1
            continue
        try:
            previous_sentence, next_sentence = context_by_id.get(source_sentence.id, (None, None))
            labels = await labeler.label(
                sentence=source_sentence.text,
                section=current_section or "OTHER",
                previous_sentence=previous_sentence,
                next_sentence=next_sentence,
            )
            labels.validate_source_offsets(source_sentence.text)
            labels.validate_frame_matches_source(source_sentence.text)
        except GoldLabelingRequestError as error:
            # Keep the labels already drafted: they cost provider quota to produce.
            stopped = error
            break
        except (ValueError, GoldLabelerError):
            item.status = "label_failed"
            continue
        item.ai_labels = labels.model_dump(mode="json")
        item.ai_model = labeler.model
        item.ai_prompt_version = labeler.prompt_version
        item.guideline_version = policies.gold_labeling.guideline_version
        item.ai_labeled_at = datetime.now(UTC)
        item.status = "draft"
        labeled += 1
    await record_event(
        session,
        actor_id=None,
        action="gold.label.complete",
        entity_type="gold_sample_batch",
        after={
            "sample_batch": sample_batch,
            "labeled_count": labeled,
            "stale_count": stale,
            "stopped": stopped is not None,
        },
        request_id=request_id,
    )
    await session.commit()
    result: dict[str, int | str] = {
        "labeled_count": labeled,
        "stale_count": stale,
        "tokens_used": labeler.total_tokens,
    }
    if isinstance(stopped, GoldLabelingQuotaError):
        # Daily quota used up: the remaining items stay pending_ai for a later run.
        remaining = sum(item.status in ("pending_ai", "label_failed") for item, _ in rows)
        return {
            **result,
            "stopped": "quota",
            "remaining_count": remaining,
            "retry_after_seconds": int(stopped.retry_after_seconds),
        }
    if stopped is not None:
        raise stopped
    return result


def _groq_is_enabled(policy_provider: str) -> bool:
    return (
        settings.app_env in DEV_APP_ENVS
        and settings.gold_labeler == "groq"
        and policy_provider == "groq"
        and settings.groq_allow_external_processing
        and settings.groq_api_key is not None
    )


def _load_gold_guideline(version: str) -> str:
    guideline_path = (
        Path(__file__).resolve().parents[6] / "eval" / "mining" / "gold" / "GUIDELINE.md"
    )
    try:
        content = guideline_path.read_text(encoding="utf-8")
    except OSError:
        raise GoldLabelerError("Gold labeling guideline is unavailable") from None
    if f"guideline {version}" not in content.casefold():
        raise GoldLabelerError("Gold labeling guideline version does not match policy")
    return content


async def list_gold_items(
    session: AsyncSession,
    *,
    status: str | None,
    split: str | None,
    section: str | None,
    sample_batch: str | None,
    offset: int,
    limit: int,
) -> list[GoldItemSummary]:
    query = select(GoldItem)
    if status:
        query = query.where(GoldItem.status == status)
    if split:
        query = query.where(GoldItem.split == split)
    if section:
        query = query.where(GoldItem.section_at_sampling == section)
    if sample_batch:
        query = query.where(GoldItem.sample_batch == sample_batch)
    items = await session.scalars(query.order_by(GoldItem.id).offset(offset).limit(limit))
    return [
        GoldItemSummary(
            id=item.id,
            sample_batch=item.sample_batch,
            split=item.split,
            section=item.section_at_sampling,
            status=item.status,
        )
        for item in items
    ]


async def get_gold_item(session: AsyncSession, *, item_id: UUID, request_id: str) -> GoldItemDetail:
    from aprkb.modules.corpus.models import ArticleSection

    row = await session.execute(
        select(GoldItem, License.allows_display, ArticleSection.heading)
        .join(Sentence, Sentence.id == GoldItem.sentence_id)
        .join(Article, Article.id == GoldItem.article_id)
        .join(License, License.id == Article.license_id)
        .outerjoin(ArticleSection, ArticleSection.id == Sentence.article_section_id)
        .where(GoldItem.id == item_id)
        .with_for_update(of=License)
    )
    item, allows_display, section_heading = row.one_or_none() or (None, False, None)
    if item is None or item.sentence_id is None:
        raise HTTPException(status_code=404, detail="Gold item not found")
    if item.status == "stale":
        raise HTTPException(status_code=409, detail="Gold source is stale")
    if not allows_display:
        raise HTTPException(status_code=409, detail="License does not allow source display")
    sentence = await session.get(Sentence, item.sentence_id)
    if sentence is None or sentence.article_id != item.article_id:
        raise HTTPException(status_code=409, detail="Gold source is unavailable")
    if hashlib.sha256(sentence.text.encode("utf-8")).hexdigest() != item.text_sha256:
        previous_status = item.status
        item.status = "stale"
        await record_event(
            session,
            actor_id=None,
            action="gold.item.stale",
            entity_type="gold_item",
            entity_id=item.id,
            before={"status": previous_status},
            after={"status": "stale"},
            request_id=request_id,
        )
        await session.commit()
        raise HTTPException(status_code=409, detail="Gold source changed after sampling")
    previous = next(
        iter(
            await session.scalars(
                select(Sentence)
                .where(
                    Sentence.article_id == item.article_id,
                    Sentence.char_start < sentence.char_start,
                    Sentence.article_section_id == sentence.article_section_id,
                )
                .order_by(Sentence.char_start.desc())
                .limit(1)
            )
        ),
        None,
    )
    following = next(
        iter(
            await session.scalars(
                select(Sentence)
                .where(
                    Sentence.article_id == item.article_id,
                    Sentence.char_start > sentence.char_start,
                    Sentence.article_section_id == sentence.article_section_id,
                )
                .order_by(Sentence.char_start)
                .limit(1)
            )
        ),
        None,
    )
    return GoldItemDetail(
        id=item.id,
        sample_batch=item.sample_batch,
        split=item.split,
        section=item.section_at_sampling,
        status=item.status,
        ai_labels=item.ai_labels,
        final_labels=item.final_labels,
        text=sentence.text,
        previous_text=previous.text if previous else None,
        next_text=following.text if following else None,
        section_heading=section_heading,
    )


async def review_gold_item(
    session: AsyncSession,
    *,
    item_id: UUID,
    payload: GoldReviewDecision,
    reviewer: ApiClient,
    request_id: str,
) -> GoldReviewResult:
    item = await session.scalar(select(GoldItem).where(GoldItem.id == item_id).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Gold item not found")
    if item.status != "draft" or item.ai_labels is None or item.sentence_id is None:
        raise HTTPException(status_code=409, detail="Gold item is not awaiting human review")
    license_row = await session.scalar(
        select(License)
        .join(Article, Article.license_id == License.id)
        .where(Article.id == item.article_id)
        .with_for_update(of=License)
    )
    if license_row is None:
        raise HTTPException(status_code=409, detail="Gold source is unavailable for review")
    if not license_row.allows_display:
        raise HTTPException(status_code=409, detail="License does not allow source display")
    sentence = await session.get(Sentence, item.sentence_id, with_for_update=True)
    if sentence is None or sentence.article_id != item.article_id:
        raise HTTPException(status_code=409, detail="Gold source is unavailable for review")
    if hashlib.sha256(sentence.text.encode("utf-8")).hexdigest() != item.text_sha256:
        previous_status = item.status
        item.status = "stale"
        await record_event(
            session,
            actor_id=reviewer.id,
            action="gold.item.stale",
            entity_type="gold_item",
            entity_id=item.id,
            before={"status": previous_status},
            after={"status": "stale"},
            request_id=request_id,
        )
        await session.commit()
        raise HTTPException(status_code=409, detail="Gold source changed after sampling")
    if payload.decision == "reject":
        item.status = "rejected"
        item.final_labels = None
    else:
        try:
            labels = GoldLabels.model_validate(payload.final_labels or item.ai_labels)
        except ValueError:
            raise HTTPException(
                status_code=422, detail="Gold labels do not match the schema"
            ) from None
        try:
            labels.validate_source_offsets(sentence.text)
        except ValueError as error:
            raise HTTPException(
                status_code=422, detail="Label slot is outside the source sentence"
            ) from error
        item.final_labels = labels.model_dump(mode="json")
        item.status = "approved"
    item.reviewed_by = reviewer.id
    reviewed_at = datetime.now(UTC)
    item.reviewed_at = reviewed_at
    await record_event(
        session,
        actor_id=reviewer.id,
        action="gold.item.review",
        entity_type="gold_item",
        entity_id=item.id,
        before={"status": "draft"},
        after={
            "status": item.status,
            "decision": payload.decision,
            "changed_fields": _changed_label_fields(item.ai_labels, item.final_labels),
        },
        request_id=request_id,
    )
    await session.commit()
    return GoldReviewResult(id=item.id, status=item.status, reviewed_at=reviewed_at.isoformat())


async def get_gold_stats(session: AsyncSession) -> GoldStats:
    rows = list(
        await session.execute(
            select(GoldItem.status, GoldItem.split, GoldItem.ai_labels, GoldItem.final_labels)
        )
    )
    by_status: dict[str, int] = {}
    by_split: dict[str, int] = {}
    field_edits: dict[str, int] = {}
    for status, split, ai_labels, final_labels in rows:
        by_status[status] = by_status.get(status, 0) + 1
        by_split[split] = by_split.get(split, 0) + 1
        for field in _changed_label_fields(ai_labels, final_labels):
            field_edits[field] = field_edits.get(field, 0) + 1
    return GoldStats(
        total=len(rows), by_status=by_status, by_split=by_split, field_edits=field_edits
    )


def _changed_label_fields(
    ai_labels: dict[str, object] | None, final_labels: dict[str, object] | None
) -> list[str]:
    if ai_labels is None or final_labels is None:
        return []
    return sorted(
        field
        for field in set(ai_labels) | set(final_labels)
        if ai_labels.get(field) != final_labels.get(field)
    )
