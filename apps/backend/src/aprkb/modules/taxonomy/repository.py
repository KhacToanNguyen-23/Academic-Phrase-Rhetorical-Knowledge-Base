"""Database access for taxonomy releases and their ordered hierarchy."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.taxonomy.models import ArticleGenre, Intent, Move, Section, Step, TaxonomyRelease
from aprkb.shared.models import RefEnum


async def list_releases(session: AsyncSession) -> list[TaxonomyRelease]:
    return list(
        await session.scalars(select(TaxonomyRelease).order_by(TaxonomyRelease.created_at.desc()))
    )


async def published_release(session: AsyncSession) -> TaxonomyRelease | None:
    return await session.scalar(
        select(TaxonomyRelease)
        .where(TaxonomyRelease.status == "published")
        .order_by(TaxonomyRelease.published_at.desc(), TaxonomyRelease.version.desc())
        .limit(1)
    )


async def sections_for_release(session: AsyncSession, release_id: UUID) -> list[Section]:
    return list(
        await session.scalars(
            select(Section)
            .where(Section.release_id == release_id)
            .order_by(Section.order, Section.code)
        )
    )


async def moves_for_sections(session: AsyncSession, section_ids: Sequence[UUID]) -> list[Move]:
    if not section_ids:
        return []
    return list(
        await session.scalars(
            select(Move).where(Move.section_id.in_(section_ids)).order_by(Move.code)
        )
    )


async def steps_for_moves(session: AsyncSession, move_ids: Sequence[UUID]) -> list[Step]:
    if not move_ids:
        return []
    return list(
        await session.scalars(select(Step).where(Step.move_id.in_(move_ids)).order_by(Step.code))
    )


async def intents_for_steps(session: AsyncSession, step_ids: Sequence[UUID]) -> list[Intent]:
    if not step_ids:
        return []
    return list(
        await session.scalars(
            select(Intent).where(Intent.step_id.in_(step_ids)).order_by(Intent.code)
        )
    )


async def intent_exists_in_release(session: AsyncSession, *, release_id: UUID, code: str) -> bool:
    intent_id = await session.scalar(
        select(Intent.id)
        .join(Step, Step.id == Intent.step_id)
        .join(Move, Move.id == Step.move_id)
        .join(Section, Section.id == Move.section_id)
        .where(Section.release_id == release_id, Intent.code == code)
        .limit(1)
    )
    return intent_id is not None


async def article_genres(session: AsyncSession) -> list[ArticleGenre]:
    return list(await session.scalars(select(ArticleGenre).order_by(ArticleGenre.code)))


async def reference_options(session: AsyncSession) -> list[RefEnum]:
    return list(
        await session.scalars(
            select(RefEnum)
            .where(RefEnum.group.in_(["claim_type", "evidence_level", "epistemic_strength"]))
            .order_by(RefEnum.group, RefEnum.order, RefEnum.code)
        )
    )
