"""Persistence and asynchronous enrichment for syntax-gated epistemic OOV keys."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.config import DEV_APP_ENVS, settings
from aprkb.modules.mining.epistemic_labelers import (
    EpistemicKey,
    EpistemicLabeler,
    EpistemicLabelerError,
    EpistemicPredicate,
    GroqEpistemicLabeler,
)
from aprkb.modules.mining.models import EpistemicLexiconAudit, EpistemicLexiconEntry, Job
from aprkb.modules.mining.queue import execution_lock
from aprkb.policies.loader import load_policy_bundle

EPISTEMIC_ENRICHMENT_JOB_TYPE = "enrich_epistemic_lexicon"
MAX_EPISTEMIC_BATCH_SIZE = 20
_SAFE_LEMMA = re.compile(r"^[\w'-]{1,96}$", re.UNICODE)


@dataclass(frozen=True)
class EpistemicLexiconSnapshot:
    entries: dict[tuple[str, str, str], float]
    revision: str


def external_epistemic_processing_enabled() -> bool:
    return bool(
        settings.epistemic_labeler == "groq"
        and settings.app_env in DEV_APP_ENVS
        and settings.groq_allow_external_processing
        and settings.groq_api_key is not None
    )


def _normalize_key(lemma: str, pos: str, construction_family: str) -> tuple[str, str, str]:
    normalized = (
        lemma.strip().casefold(),
        pos.strip().casefold(),
        construction_family.strip().casefold(),
    )
    if not _SAFE_LEMMA.fullmatch(normalized[0]) or not normalized[1] or not normalized[2]:
        raise ValueError("Invalid epistemic lexicon key")
    return normalized


async def load_active_epistemic_snapshot(session: AsyncSession) -> EpistemicLexiconSnapshot:
    entries = list(
        await session.scalars(
            select(EpistemicLexiconEntry).where(EpistemicLexiconEntry.status == "active")
        )
    )
    active = sorted(
        entries,
        key=lambda entry: (entry.lemma, entry.pos, entry.construction_family, entry.revision),
    )
    snapshot_material = "\n".join(
        f"{entry.lemma}\0{entry.pos}\0{entry.construction_family}\0"
        f"{entry.revision}\0{entry.tier}\0{entry.score:.8g}"
        for entry in active
    )
    revision = (
        "lex:" + hashlib.sha256(snapshot_material.encode("utf-8")).hexdigest()[:16]
        if active
        else "lex:empty"
    )
    return EpistemicLexiconSnapshot(
        entries={
            (entry.lemma, entry.pos, entry.construction_family): entry.score for entry in active
        },
        revision=revision,
    )


async def discover_epistemic_oov(
    session: AsyncSession,
    *,
    lemma: str,
    pos: str,
    construction_family: str,
    rights_allow_external_processing: bool = False,
    enqueue_job: bool = True,
) -> EpistemicLexiconEntry:
    """Create one pending assessment and an optional safe metadata-only job."""
    key = _normalize_key(lemma, pos, construction_family)
    identity = "epistemic-oov:" + "|".join(key)
    await execution_lock(session, identity, wait=True)
    lemma, pos, construction_family = key
    policies = load_policy_bundle()
    policy_conflict = lemma in {
        verb.strip().casefold() for verb in policies.epistemic_markers.neutral_verbs
    }
    active = await session.scalar(
        select(EpistemicLexiconEntry).where(
            EpistemicLexiconEntry.lemma == lemma,
            EpistemicLexiconEntry.pos == pos,
            EpistemicLexiconEntry.construction_family == construction_family,
            EpistemicLexiconEntry.status == "active",
        )
    )
    if active is not None:
        if policy_conflict:
            active.status = "policy_conflict_hold"
            active.provenance = "policy_conflict_hold"
            active.review_reason = "locked_neutral_policy"
            await session.flush()
        return active
    latest = await session.scalar(
        select(EpistemicLexiconEntry)
        .where(
            EpistemicLexiconEntry.lemma == lemma,
            EpistemicLexiconEntry.pos == pos,
            EpistemicLexiconEntry.construction_family == construction_family,
        )
        .order_by(EpistemicLexiconEntry.revision.desc())
        .limit(1)
        .with_for_update()
    )
    if (
        latest is None
        or latest.status in {"rejected", "superseded"}
        or (latest.status == "policy_conflict_hold" and not policy_conflict)
    ):
        revision = (
            await session.scalar(
                select(func.max(EpistemicLexiconEntry.revision)).where(
                    EpistemicLexiconEntry.lemma == lemma,
                    EpistemicLexiconEntry.pos == pos,
                    EpistemicLexiconEntry.construction_family == construction_family,
                )
            )
            or 0
        ) + 1
        moderate_score = load_policy_bundle().epistemic_scoring.baseline_scores["moderate"]
        latest = EpistemicLexiconEntry(
            lemma=lemma,
            pos=pos,
            construction_family=construction_family,
            revision=revision,
            tier="moderate",
            score=moderate_score,
            status="policy_conflict_hold" if policy_conflict else "pending",
            provenance="policy_conflict_hold" if policy_conflict else "ai_assessment_pending",
        )
        session.add(latest)
        await session.flush()
    elif policy_conflict and latest.status not in {"rejected", "superseded"}:
        latest.status = "policy_conflict_hold"
        latest.provenance = "policy_conflict_hold"
        latest.review_reason = "locked_neutral_policy"

    if (
        enqueue_job
        and latest.status == "pending"
        and rights_allow_external_processing
        and external_epistemic_processing_enabled()
    ):
        await enqueue_epistemic_oov_batch(
            session,
            [latest],
            rights_allow_external_processing=rights_allow_external_processing,
        )
    return latest


async def enqueue_epistemic_oov_batch(
    session: AsyncSession,
    entries: list[EpistemicLexiconEntry],
    *,
    rights_allow_external_processing: bool = False,
) -> None:
    if not rights_allow_external_processing or not external_epistemic_processing_enabled():
        return
    pending_ids: list[str] = []
    for entry in entries:
        if entry.status != "pending":
            continue
        entry_id = str(entry.id)
        existing = await session.scalar(
            select(Job.id).where(
                Job.type == EPISTEMIC_ENRICHMENT_JOB_TYPE,
                Job.status.in_(("queued", "processing", "succeeded")),
                or_(
                    Job.payload["entry_id"].as_string() == entry_id,
                    Job.payload["entry_ids"].contains([entry_id]),
                ),
            )
        )
        if existing is None:
            pending_ids.append(entry_id)
    for start in range(0, len(pending_ids), MAX_EPISTEMIC_BATCH_SIZE):
        batch_ids = pending_ids[start : start + MAX_EPISTEMIC_BATCH_SIZE]
        session.add(
            Job(
                type=EPISTEMIC_ENRICHMENT_JOB_TYPE,
                payload={"entry_ids": batch_ids},
                status="queued",
            )
        )


def build_epistemic_labeler(
    *, api_key: str | None = None, model: str | None = None
) -> EpistemicLabeler:
    if not external_epistemic_processing_enabled():
        raise EpistemicLabelerError("Epistemic external processing is disabled")
    policies = load_policy_bundle()
    gold_policy = policies.gold_labeling
    secret = api_key
    if secret is None:
        configured_key = settings.groq_api_key
        if configured_key is None:
            raise EpistemicLabelerError("GROQ_API_KEY is required")
        secret = configured_key.get_secret_value()
    return GroqEpistemicLabeler(
        api_key=secret,
        model=model or gold_policy.model,
        prompt_version="epistemic-dual-consensus-v1",
    )


async def assess_epistemic_entries(
    session: AsyncSession,
    *,
    entry_ids: list[UUID],
    labeler: EpistemicLabeler | None = None,
) -> list[EpistemicLexiconEntry]:
    entries = list(
        await session.scalars(
            select(EpistemicLexiconEntry)
            .where(EpistemicLexiconEntry.id.in_(set(entry_ids)))
            .order_by(EpistemicLexiconEntry.id)
            .with_for_update()
        )
    )
    if len(entries) != len(set(entry_ids)):
        raise EpistemicLabelerError(
            "Enrichment batch contains an unknown entry",
            safe_code="epistemic_invalid_batch",
        )
    locked_neutral = {
        value.strip().casefold() for value in load_policy_bundle().epistemic_markers.neutral_verbs
    }
    for entry in entries:
        if entry.status == "pending" and entry.lemma.casefold() in locked_neutral:
            entry.status = "policy_conflict_hold"
            entry.review_reason = "locked_neutral_policy"
            entry.provenance = "policy_conflict_hold"
    pending = [entry for entry in entries if entry.status == "pending"]
    if not pending:
        return entries
    if labeler is None:
        labeler = build_epistemic_labeler()
    try:
        results = await labeler.assess_batch(
            [
                EpistemicPredicate(
                    lemma=entry.lemma,
                    pos=entry.pos,
                    construction_family=entry.construction_family,
                )
                for entry in pending
            ]
        )
    except EpistemicLabelerError:
        for entry in pending:
            entry.provenance = "ai_assessment_pending"
        raise
    policy = load_policy_bundle().epistemic_scoring
    confidence_threshold = policy.oov_activation_confidence_threshold
    for entry in pending:
        key: EpistemicKey = (entry.lemma, entry.pos, entry.construction_family)
        dual = results.get(key)
        if dual is None:
            raise EpistemicLabelerError(
                "Provider response omitted an entry from the batch",
                safe_code="epistemic_invalid_response",
            )
        entry.run1_tier = dual.run1.tier
        entry.run1_confidence = dual.run1.confidence
        entry.run1_rationale = dual.run1.rationale
        entry.run2_tier = dual.run2.tier
        entry.run2_confidence = dual.run2.confidence
        entry.run2_rationale = dual.run2.rationale
        entry.confidence = min(dual.run1.confidence, dual.run2.confidence)
        entry.provider = labeler.provider
        entry.model = labeler.model
        entry.prompt_version = labeler.prompt_version

        if dual.run1.tier != dual.run2.tier:
            entry.tier = "moderate"
            entry.score = policy.baseline_scores["moderate"]
            entry.status = "needs_review"
            entry.review_reason = "tier_disagreement"
            entry.provenance = "ai_consensus_disagreement"
        elif entry.confidence < confidence_threshold:
            entry.tier = dual.run1.tier
            entry.score = policy.baseline_scores[dual.run1.tier]
            entry.status = "needs_review"
            entry.review_reason = "low_confidence"
            entry.provenance = "ai_consensus_low_confidence"
        else:
            entry.tier = dual.run1.tier
            entry.score = policy.baseline_scores[dual.run1.tier]
            entry.status = "active"
            entry.review_reason = None
            entry.provenance = "ai_dual_consensus_activated"
        entry.updated_at = datetime.now(UTC)
    await session.flush()
    return entries


async def assess_epistemic_entry(
    session: AsyncSession,
    *,
    entry_id: UUID,
    labeler: EpistemicLabeler | None = None,
) -> EpistemicLexiconEntry:
    entries = await assess_epistemic_entries(
        session,
        entry_ids=[entry_id],
        labeler=labeler,
    )
    if not entries:
        raise ValueError("Epistemic lexicon entry not found")
    return entries[0]


async def review_epistemic_entry(
    session: AsyncSession,
    *,
    entry_id: UUID,
    actor_id: UUID,
    action: str,
) -> EpistemicLexiconEntry:
    if action not in {"activate", "reject", "deactivate"}:
        raise ValueError("Unsupported epistemic lexicon review action")
    entry = await session.scalar(
        select(EpistemicLexiconEntry).where(EpistemicLexiconEntry.id == entry_id).with_for_update()
    )
    if entry is None:
        raise ValueError("Epistemic lexicon entry not found")
    if action == "activate" and entry.status == "policy_conflict_hold":
        raise ValueError("Locked neutral policy entries cannot be activated by curator review")
    if action in {"activate", "deactivate"}:
        active = await session.scalar(
            select(EpistemicLexiconEntry)
            .where(
                EpistemicLexiconEntry.lemma == entry.lemma,
                EpistemicLexiconEntry.pos == entry.pos,
                EpistemicLexiconEntry.construction_family == entry.construction_family,
                EpistemicLexiconEntry.status == "active",
            )
            .with_for_update()
        )
        if active is not None and active.id != entry.id:
            previous = active.status
            active.status = "superseded"
            active.reviewed_by = actor_id
            active.reviewed_at = datetime.now(UTC)
            session.add(
                EpistemicLexiconAudit(
                    entry_id=active.id,
                    actor_id=actor_id,
                    action="deactivate",
                    previous_status=previous,
                    new_status="superseded",
                )
            )
    previous_status = entry.status
    entry.status = (
        "active" if action == "activate" else "rejected" if action == "reject" else "superseded"
    )
    entry.reviewed_by = actor_id
    entry.reviewed_at = datetime.now(UTC)
    entry.provenance = f"curator_{action}"
    if action == "activate":
        entry.review_reason = None
    session.add(
        EpistemicLexiconAudit(
            entry_id=entry.id,
            actor_id=actor_id,
            action=action,
            previous_status=previous_status,
            new_status=entry.status,
        )
    )
    await session.flush()
    return entry
