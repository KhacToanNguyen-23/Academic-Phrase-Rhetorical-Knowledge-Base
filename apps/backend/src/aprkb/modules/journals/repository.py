"""Journal and guideline database access."""

from datetime import UTC, datetime
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


async def list_active_mandatory_guidelines(
    session: AsyncSession, journal_id: UUID
) -> list[GuidelineRule]:
    now = datetime.now(UTC)
    return list(
        await session.scalars(
            select(GuidelineRule)
            .where(
                GuidelineRule.journal_id == journal_id,
                GuidelineRule.is_mandatory.is_(True),
                (GuidelineRule.active_from.is_(None) | (GuidelineRule.active_from <= now)),
                (GuidelineRule.active_to.is_(None) | (GuidelineRule.active_to > now)),
            )
            .order_by(GuidelineRule.created_at, GuidelineRule.id)
        )
    )
