"""Feedback and validation override write services."""

from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.analytics.schemas import FeedbackCreate, OverrideCreate
from aprkb.modules.audit.service import record_event
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.recommendation.models import Feedback, Override
from aprkb.modules.recommendation.service import require_issued_candidate


async def create_feedback(
    session: AsyncSession,
    *,
    payload: FeedbackCreate,
    actor: ApiClient,
    request_id: str,
) -> Feedback:
    """FR-07.7 / BR-08: persist feedback against the issued pattern version.

    Writer text itself is not stored as feedback.
    """
    await require_issued_candidate(
        session,
        recommendation_id=payload.recommendation_id,
        pattern_version_id=payload.pattern_version_id,
        client_id=actor.id,
    )
    row = Feedback(
        client_id=actor.id,
        recommendation_id=payload.recommendation_id,
        pattern_version_id=payload.pattern_version_id,
        signal=payload.signal,
        payload=payload.payload.model_dump() if payload.payload is not None else None,
    )
    session.add(row)
    try:
        await session.flush()
        await record_event(
            session,
            actor_id=actor.id,
            action="feedback.create",
            entity_type="feedback",
            entity_id=row.id,
            after={"pattern_version_id": str(row.pattern_version_id), "signal": row.signal},
            request_id=request_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return row


async def create_override(
    session: AsyncSession,
    *,
    payload: OverrideCreate,
    actor: ApiClient,
    request_id: str,
) -> Override:
    row = Override(
        client_id=actor.id,
        validation_id=payload.validation_id,
        rule_code=payload.rule_code,
        rationale=payload.rationale,
    )
    session.add(row)
    try:
        await session.flush()
        await record_event(
            session,
            actor_id=actor.id,
            action="validation.override",
            entity_type="override",
            entity_id=row.id,
            after={"validation_id": str(row.validation_id), "rule_code": row.rule_code},
            request_id=request_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return row
