"""Journal and guideline database access."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.journals.models import GuidelineRule, JournalProfile


async def list_journals(session: AsyncSession) -> list[JournalProfile]:
    return list(await session.scalars(select(JournalProfile).order_by(JournalProfile.name)))


async def get_journal(session: AsyncSession, journal_id: UUID) -> JournalProfile | None:
    return await session.get(JournalProfile, journal_id)


async def add_guideline(session: AsyncSession, rule: GuidelineRule) -> GuidelineRule:
    session.add(rule)
    await session.flush()
    return rule
