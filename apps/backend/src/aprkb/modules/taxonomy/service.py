"""Taxonomy query services and published-tree projection."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.taxonomy import repository
from aprkb.modules.taxonomy.models import Intent, Move, Step, TaxonomyRelease


async def get_releases(session: AsyncSession) -> list[TaxonomyRelease]:
    return await repository.list_releases(session)


async def get_reference_options(session: AsyncSession) -> list[dict[str, object]]:
    return [
        {"group": row.group, "code": row.code, "label": row.label, "order": row.order}
        for row in await repository.reference_options(session)
    ]


async def get_published_tree(session: AsyncSession) -> dict[str, object] | None:
    release = await repository.published_release(session)
    if release is None:
        return None
    sections = await repository.sections_for_release(session, release.id)
    moves = await repository.moves_for_sections(session, [section.id for section in sections])
    steps = await repository.steps_for_moves(session, [move.id for move in moves])
    intents = await repository.intents_for_steps(session, [step.id for step in steps])
    genres = await repository.article_genres(session)
    moves_by_section: dict[UUID, list[Move]] = {}
    for move in moves:
        moves_by_section.setdefault(move.section_id, []).append(move)
    steps_by_move: dict[UUID, list[Step]] = {}
    for step in steps:
        steps_by_move.setdefault(step.move_id, []).append(step)
    intents_by_step: dict[UUID, list[Intent]] = {}
    for intent in intents:
        intents_by_step.setdefault(intent.step_id, []).append(intent)
    return {
        "release_id": release.id,
        "version": release.version,
        "sections": [
            {
                "id": section.id,
                "code": section.code,
                "name": section.name,
                "order": section.order,
                "moves": [
                    {
                        "id": move.id,
                        "code": move.code,
                        "name": move.name,
                        "steps": [
                            {
                                "id": step.id,
                                "code": step.code,
                                "name": step.name,
                                "intents": [
                                    {
                                        "id": intent.id,
                                        "code": intent.code,
                                        "name": intent.name,
                                        "description": intent.description,
                                    }
                                    for intent in intents_by_step.get(step.id, [])
                                ],
                            }
                            for step in steps_by_move.get(move.id, [])
                        ],
                    }
                    for move in moves_by_section.get(section.id, [])
                ],
            }
            for section in sections
        ],
        "article_genres": [{"code": genre.code, "name": genre.name} for genre in genres],
    }
