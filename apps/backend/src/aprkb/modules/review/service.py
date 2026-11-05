"""Transactional two-round review and candidate promotion."""

from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.audit.service import record_event
from aprkb.modules.corpus.models import Article, ArticleSection, License, Sentence
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.mining.models import Candidate
from aprkb.modules.mining.schemas import SlotDefinition, is_safe_masked_frame
from aprkb.modules.patterns.models import (
    EvidenceProvenance,
    PatternVersion,
    PhrasePattern,
    ReviewDecision,
    UsageConstraint,
)
from aprkb.modules.review import repository
from aprkb.modules.review.schemas import CandidateIntentUpdate, ReviewDecisionCreate
from aprkb.modules.taxonomy.models import Intent, Move, Section, Step, TaxonomyRelease
from aprkb.policies.loader import load_policy_bundle
from aprkb.policies.schemas import is_safe_construction_frame

_POLICIES = load_policy_bundle()
_REPORTING_FORMS = _POLICIES.reporting_verbs.all_forms


async def list_review_queue(session: AsyncSession) -> list[Candidate]:
    return await repository.pending_candidates(session)


async def assign_intent(
    session: AsyncSession,
    *,
    candidate_id: UUID,
    payload: CandidateIntentUpdate,
    reviewer: ApiClient,
    request_id: str,
) -> Candidate:
    """Assign intent before review, or let a legacy first reviewer confirm their missing label."""
    candidate = await repository.lock_candidate(session, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.status != "pending":
        raise HTTPException(status_code=409, detail="Candidate is no longer pending review")
    previous = await repository.decisions_for_candidate(session, candidate_id)
    recovering_first_approval = (
        len(previous) == 1
        and previous[0].round == 1
        and previous[0].decision == "approve"
        and candidate.intent_id is None
        and previous[0].reviewer_id == reviewer.id
    )
    if previous and not recovering_first_approval:
        raise HTTPException(status_code=409, detail="Intent is frozen after review begins")
    if not _candidate_is_safe_to_promote(candidate):
        raise HTTPException(status_code=409, detail="Candidate abstraction schema is invalid")
    intent = await session.scalar(
        select(Intent)
        .join(Step, Step.id == Intent.step_id)
        .join(Move, Move.id == Step.move_id)
        .join(Section, Section.id == Move.section_id)
        .join(TaxonomyRelease, TaxonomyRelease.id == Section.release_id)
        .where(Intent.id == payload.intent_id, TaxonomyRelease.status == "published")
    )
    if intent is None:
        raise HTTPException(status_code=422, detail="Intent must belong to a published taxonomy")
    before = {
        "intent_id": str(candidate.intent_id) if candidate.intent_id else None,
    }
    try:
        candidate.intent_id = payload.intent_id
        await record_event(
            session,
            actor_id=reviewer.id,
            action="candidate.intent.update",
            entity_type="candidate",
            entity_id=candidate.id,
            before=before,
            after={
                **payload.model_dump(mode="json"),
                "first_reviewer_confirmed_intent": recovering_first_approval,
            },
            request_id=request_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return candidate


async def decide(
    session: AsyncSession,
    *,
    candidate_id: UUID,
    payload: ReviewDecisionCreate,
    reviewer: ApiClient,
    request_id: str,
) -> dict[str, object]:
    candidate = await repository.lock_candidate(session, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.status != "pending":
        raise HTTPException(status_code=409, detail="Candidate is no longer pending review")
    if payload.decision == "approve" and not _candidate_is_safe_to_promote(candidate):
        raise HTTPException(status_code=409, detail="Candidate abstraction schema is invalid")
    if payload.decision == "approve" and candidate.intent_id is None:
        raise HTTPException(
            status_code=409, detail="Assign an intent before approving the candidate"
        )
    previous = await repository.decisions_for_candidate(session, candidate_id)
    if len(previous) >= 2:
        raise HTTPException(status_code=409, detail="Candidate has completed both review rounds")
    round_number = len(previous) + 1
    decision = ReviewDecision(
        candidate_id=candidate.id,
        round=round_number,
        decision=payload.decision,
        reviewer_id=reviewer.id,
        comment=payload.comment,
        created_by=reviewer.id,
    )
    session.add(decision)
    version: PatternVersion | None = None
    before = {"status": candidate.status, "decision_count": len(previous)}
    try:
        await session.flush()
        if payload.decision == "reject":
            candidate.status = "rejected"
        elif round_number == 2 and all(item.decision == "approve" for item in previous):
            version = await _promote_candidate(session, candidate, reviewer)
            candidate.status = "accepted"
            candidate.matched_pattern_id = version.pattern_id
        await record_event(
            session,
            actor_id=reviewer.id,
            action="candidate.review.decision",
            entity_type="candidate",
            entity_id=candidate.id,
            before=before,
            after={
                "status": candidate.status,
                "round": round_number,
                "decision": payload.decision,
                "pattern_version_id": str(version.id) if version else None,
            },
            request_id=request_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return {
        "candidate_id": candidate.id,
        "round": round_number,
        "decision": decision.decision,
        "candidate_status": candidate.status,
        "pattern_version_id": version.id if version else None,
    }


async def _promote_candidate(
    session: AsyncSession, candidate: Candidate, reviewer: ApiClient
) -> PatternVersion:
    if candidate.intent_id is None:
        raise HTTPException(status_code=409, detail="Candidate has no intent for promotion")
    source_ids = candidate.source_sentence_ids
    if not source_ids or len(set(source_ids)) != len(source_ids):
        raise HTTPException(status_code=409, detail="Candidate has no source sentences")
    source_rows = []
    if candidate.source_sentence_ids:
        source_rows = list(
            (
                await session.execute(
                    select(
                        Sentence.id.label("sentence_id"),
                        ArticleSection.section_code.label("section_code"),
                        Article.license_id.label("license_id"),
                        Article.id.label("article_id"),
                        License.allows_mining.label("allows_mining"),
                    )
                    .select_from(Sentence)
                    .outerjoin(ArticleSection, ArticleSection.id == Sentence.article_section_id)
                    .join(Article, Article.id == Sentence.article_id)
                    .join(License, License.id == Article.license_id)
                    .where(Sentence.id.in_(candidate.source_sentence_ids))
                )
            ).all()
        )
    sections = sorted({row.section_code for row in source_rows if row.section_code})
    if len(source_rows) != len(source_ids) or any(not row.allows_mining for row in source_rows):
        raise HTTPException(
            status_code=409,
            detail="Candidate provenance is missing or not licensed",
        )
    licenses = {row.license_id for row in source_rows if row.license_id}
    articles = {row.article_id for row in source_rows}
    pattern = PhrasePattern(
        intent_id=candidate.intent_id,
        status="approved",
        created_by=reviewer.id,
    )
    session.add(pattern)
    await session.flush()
    version = PatternVersion(
        pattern_id=pattern.id,
        version_no=1,
        canonical_frame=candidate.canonical_frame,
        slots=candidate.slots,
        # Missing human labels remain unknown rather than being inferred for export.
        claim_type="unknown",
        epistemic_strength=candidate.epistemic_strength or "unknown",
        change_note=(
            "TODO(owner, PRD-6.3): classify claim type and review epistemic strength. "
            "Promoted after two review approvals."
        ),
        created_by=reviewer.id,
    )
    session.add(version)
    await session.flush()
    pattern.current_version_id = version.id
    session.add(
        UsageConstraint(
            pattern_version_id=version.id,
            allowed_sections=sections,
            allowed_genres=[],
        )
    )
    session.add(
        EvidenceProvenance(
            pattern_version_id=version.id,
            source_type="mined",
            article_id=next(iter(articles)) if len(articles) == 1 else None,
            sentence_ids=candidate.source_sentence_ids,
            license_id=next(iter(licenses)) if len(licenses) == 1 else None,
            source_sentence_count=len(source_ids),
            source_section_code=sections[0] if len(sections) == 1 else None,
        )
    )
    await session.flush()
    return version


def _candidate_is_safe_to_promote(candidate: Candidate) -> bool:
    if not (
        is_safe_masked_frame(candidate.canonical_frame, _REPORTING_FORMS)
        or is_safe_construction_frame(candidate.canonical_frame, _POLICIES.constructions)
    ):
        return False
    if not isinstance(candidate.slots, dict):
        return False
    try:
        slots = {
            name: SlotDefinition.model_validate(value) for name, value in candidate.slots.items()
        }
    except (TypeError, ValueError, ValidationError):
        return False
    return not (set(slots) - {"X", "Y", "Z"})
