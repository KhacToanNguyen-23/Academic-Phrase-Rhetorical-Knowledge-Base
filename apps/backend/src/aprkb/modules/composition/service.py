"""Render orchestration; pattern ownership and rights stay in patterns.service."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.composition.renderer import render_frame
from aprkb.modules.patterns import service as pattern_service
from aprkb.modules.recommendation import service as recommendation_service


async def render_pattern(
    session: AsyncSession,
    *,
    recommendation_id: UUID,
    pattern_version_id: UUID,
    client_id: UUID,
    slots: dict[str, str],
) -> dict[str, object]:
    """FR-07.5 / BR-01: render only a displayable approved version issued to this client."""
    await recommendation_service.require_issued_candidate(
        session,
        recommendation_id=recommendation_id,
        pattern_version_id=pattern_version_id,
        client_id=client_id,
    )
    version, _source = await pattern_service.get_renderable_version(session, pattern_version_id)
    try:
        text, unfilled = render_frame(version.canonical_frame, version.slots, slots)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {
        "pattern_version_id": pattern_version_id,
        "text": text,
        "unfilled_slots": unfilled,
    }
