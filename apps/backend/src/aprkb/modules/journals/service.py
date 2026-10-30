"""Journal query and guideline-write services."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.audit.service import record_event
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.journals import repository
from aprkb.modules.journals.models import GuidelineRule, JournalProfile
from aprkb.modules.journals.schemas import GuidelineCreate


async def list_journals(session: AsyncSession) -> list[JournalProfile]:
    return await repository.list_journals(session)


async def get_journal(session: AsyncSession, journal_id: UUID) -> JournalProfile:
    journal = await repository.get_journal(session, journal_id)
    if journal is None:
        raise HTTPException(status_code=404, detail="Journal not found")
    return journal


async def create_guideline(
    session: AsyncSession,
    *,
    journal_id: UUID,
    payload: GuidelineCreate,
    actor: ApiClient,
    request_id: str,
) -> GuidelineRule:
    await get_journal(session, journal_id)
    rule = GuidelineRule(
        journal_id=journal_id,
        rule_type=payload.rule_type,
        payload=payload.payload,
        is_mandatory=payload.is_mandatory,
        active_from=payload.active_from,
        active_to=payload.active_to,
        created_by=actor.id,
    )
    try:
        await repository.add_guideline(session, rule)
        await record_event(
            session,
            actor_id=actor.id,
            action="journal.guideline.create",
            entity_type="guideline_rule",
            entity_id=rule.id,
            after={"journal_id": str(journal_id), "rule_type": rule.rule_type},
            request_id=request_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return rule
