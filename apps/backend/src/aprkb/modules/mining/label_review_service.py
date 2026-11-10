"""Frame-label review service with atomic, audit-safe approval decisions."""

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.audit.service import record_event
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.mining import candidate_label_repository as repository
from aprkb.modules.mining.label_review_schemas import (
    BulkFrameLabelReviewCreate,
    BulkFrameLabelReviewResult,
    CandidateLabelRead,
    FrameLabelReviewPage,
    FrameLabelReviewRead,
)
from aprkb.modules.mining.labelers import vocabulary_codes
from aprkb.modules.mining.labeling_service import _candidate_family
from aprkb.modules.mining.models import Candidate, CandidateLabel
from aprkb.modules.review.repository import lock_candidate
from aprkb.policies.loader import load_policy_bundle


async def list_frame_label_reviews(
    session: AsyncSession,
    *,
    label_code: str | None,
    min_confidence: float | None,
    needs_attention: bool | None,
    agreement: str | None,
    paper_count: int | None,
    offset: int,
    limit: int,
) -> FrameLabelReviewPage:
    page, total = await repository.review_candidate_page(
        session,
        label_code=label_code,
        min_confidence=min_confidence,
        needs_attention=needs_attention,
        agreement=agreement,
        paper_count=paper_count,
        offset=offset,
        limit=limit,
    )
    candidate_ids = [candidate_id for candidate_id, _ in page]
    if not candidate_ids:
        return FrameLabelReviewPage(items=[], total=total)
    candidates = list(
        await session.scalars(select(Candidate).where(Candidate.id.in_(candidate_ids)))
    )
    candidates_by_id = {candidate.id: candidate for candidate in candidates}
    rows = list(
        await session.scalars(
            select(CandidateLabel)
            .where(
                CandidateLabel.candidate_id.in_(candidate_ids),
                CandidateLabel.status == "proposed",
            )
            .order_by(CandidateLabel.candidate_id, CandidateLabel.label_code)
        )
    )
    labels_by_candidate: dict[Any, list[CandidateLabelRead]] = {}
    for row in rows:
        labels_by_candidate.setdefault(row.candidate_id, []).append(
            CandidateLabelRead.model_validate(row, from_attributes=True)
        )
    return FrameLabelReviewPage(
        items=[
            FrameLabelReviewRead(
                candidate_id=candidate_id,
                canonical_frame=candidates_by_id[candidate_id].canonical_frame,
                family=_candidate_family(candidates_by_id[candidate_id].cluster_key),
                paper_count=count,
                labels=labels_by_candidate.get(candidate_id, []),
            )
            for candidate_id, count in page
            if candidate_id in candidates_by_id
        ],
        total=total,
    )


async def decide_frame_labels(
    session: AsyncSession,
    *,
    payload: BulkFrameLabelReviewCreate,
    reviewer: ApiClient,
    request_id: str,
) -> BulkFrameLabelReviewResult:
    policies = load_policy_bundle()
    codes = vocabulary_codes(policies.frame_label_vocabulary)
    label_codes = {label for label in codes}
    decisions = sorted(payload.decisions, key=lambda item: (item.candidate_id.int, item.label_code))
    reviewed_at = datetime.now(UTC)
    audit_changes: list[dict[str, Any]] = []
    try:
        for decision in decisions:
            if decision.label_code not in label_codes:
                raise HTTPException(status_code=422, detail="Unknown frame-label code")
            allowed_values = codes[decision.label_code]
            if decision.decision == "edit" and decision.value not in allowed_values:
                raise HTTPException(
                    status_code=422, detail="Value is outside the approved vocabulary"
                )
            candidate = await lock_candidate(session, decision.candidate_id)
            if candidate is None:
                raise HTTPException(status_code=404, detail="Candidate not found")
            row = await repository.lock_candidate_label(
                session,
                candidate_id=decision.candidate_id,
                label_code=decision.label_code,
            )
            if row is None or row.status != "proposed":
                raise HTTPException(status_code=409, detail="Frame label is not awaiting review")
            before_value = row.value
            if decision.decision == "approve":
                if not isinstance(row.value, str) or row.value not in allowed_values:
                    raise HTTPException(status_code=409, detail="Proposal has no reviewable value")
                final_value: str | None = row.value
                row.status = "confirmed"
            elif decision.decision == "edit":
                final_value = decision.value
                row.value = final_value
                row.status = "confirmed"
            else:
                final_value = None
                row.value = None
                row.status = "rejected"
            row.source = "human"
            row.reviewer_id = reviewer.id
            row.reviewed_at = reviewed_at
            audit_changes.append(
                {
                    "label_code": decision.label_code,
                    "before_value": before_value,
                    "after_value": final_value,
                }
            )
        await record_event(
            session,
            actor_id=reviewer.id,
            action="frame_labels.review.bulk",
            entity_type="candidate_labels",
            after={"decision_count": len(audit_changes), "labels": audit_changes},
            request_id=request_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return BulkFrameLabelReviewResult(decisions_applied=len(audit_changes), reviewed_at=reviewed_at)
