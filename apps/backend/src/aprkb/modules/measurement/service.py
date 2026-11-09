"""Business rules for the measurement catalog and its reviewed slot links."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.audit.service import record_event
from aprkb.modules.measurement import repository
from aprkb.modules.measurement.models import MeasurementEntry, MeasurementSlotLink
from aprkb.modules.measurement.schemas import (
    MeasurementDetail,
    MeasurementListResponse,
    MeasurementSummary,
    RelatedMeasurement,
    SlotLinkListResponse,
    SlotLinkProposal,
    SlotLinkRead,
    SlotLinkReview,
    SlotSuggestion,
    SlotSuggestionsResponse,
)


def _link_read(
    link: MeasurementSlotLink, entry: MeasurementEntry, frame: str | None
) -> SlotLinkRead:
    return SlotLinkRead(
        id=link.id,
        entry_code=entry.code,
        pattern_id=link.pattern_id,
        canonical_frame=frame,
        slot_name=link.slot_name,
        review_status=link.review_status,  # type: ignore[arg-type]
        note=link.note,
        created_at=link.created_at,
        reviewed_at=link.reviewed_at,
    )


async def list_entries(
    session: AsyncSession, *, kind: str | None, query: str | None, limit: int, offset: int
) -> MeasurementListResponse:
    entries, total = await repository.search_entries(
        session, kind=kind, query=query.strip() if query else None, limit=limit, offset=offset
    )
    return MeasurementListResponse(
        catalog_version=await repository.latest_catalog_version(session),
        items=[MeasurementSummary.model_validate(entry) for entry in entries],
        total=total,
    )


async def get_entry(session: AsyncSession, code: str) -> MeasurementDetail:
    entry = await repository.entry_by_code(session, code)
    if entry is None:
        raise HTTPException(status_code=404, detail="Measurement entry not found")
    related = [
        RelatedMeasurement(
            relation=relation,
            direction=direction,  # type: ignore[arg-type]
            code=other.code,
            kind=other.kind,  # type: ignore[arg-type]
            name=other.name,
        )
        for relation, direction, other in await repository.relations_of(session, entry.id)
    ]
    approved = await repository.links(session, entry_id=entry.id, status="approved")
    return MeasurementDetail(
        code=entry.code,
        kind=entry.kind,  # type: ignore[arg-type]
        name=entry.name,
        aliases=list(entry.aliases),
        definition=entry.definition,
        formula=entry.formula,
        scale=entry.scale,
        value_range=entry.value_range,
        usage_note=entry.usage_note,
        example=entry.example,
        catalog_version=entry.catalog_version,
        related=related,
        slot_links=[_link_read(*row) for row in approved],
    )


async def slot_suggestions(
    session: AsyncSession, *, pattern_id: UUID, slot_name: str
) -> SlotSuggestionsResponse:
    """Approved catalog entries for one slot. Never fills the slot (FR-07.5, AT-08)."""
    rows = await repository.links(
        session, pattern_id=pattern_id, slot_name=slot_name, status="approved"
    )
    return SlotSuggestionsResponse(
        pattern_id=pattern_id,
        slot_name=slot_name,
        items=[
            SlotSuggestion(
                code=entry.code,
                kind=entry.kind,  # type: ignore[arg-type]
                name=entry.name,
                example=entry.example,
            )
            for _, entry, _ in rows
        ],
    )


async def list_links(session: AsyncSession, *, status: str | None) -> SlotLinkListResponse:
    rows = await repository.links(session, status=status)
    return SlotLinkListResponse(items=[_link_read(*row) for row in rows])


async def propose_link(
    session: AsyncSession, payload: SlotLinkProposal, *, actor_id: UUID, request_id: str
) -> SlotLinkRead:
    entry = await repository.entry_by_code(session, payload.entry_code)
    if entry is None:
        raise HTTPException(status_code=404, detail="Measurement entry not found")
    slots = await repository.current_slots(session, payload.pattern_id)
    if slots is None:
        raise HTTPException(status_code=404, detail="Pattern not found")
    if payload.slot_name not in slots:
        raise HTTPException(status_code=422, detail="Slot does not exist in the current version")
    if await repository.find_link(
        session, entry_id=entry.id, pattern_id=payload.pattern_id, slot_name=payload.slot_name
    ):
        raise HTTPException(status_code=409, detail="Slot link already exists")
    link = MeasurementSlotLink(
        entry_id=entry.id,
        pattern_id=payload.pattern_id,
        slot_name=payload.slot_name,
        review_status="proposed",
        proposed_by=actor_id,
        note=payload.note,
    )
    session.add(link)
    await session.flush()
    await record_event(
        session,
        actor_id=actor_id,
        action="measurement.slot_link_proposed",
        entity_type="measurement_slot_link",
        entity_id=link.id,
        after={"entry_code": entry.code, "slot_name": link.slot_name, "status": "proposed"},
        request_id=request_id,
    )
    await session.commit()
    await session.refresh(link)
    rows = await repository.links(session, entry_id=entry.id, pattern_id=link.pattern_id)
    return next(_link_read(*row) for row in rows if row[0].id == link.id)


async def review_link(
    session: AsyncSession,
    link_id: UUID,
    payload: SlotLinkReview,
    *,
    actor_id: UUID,
    request_id: str,
) -> SlotLinkRead:
    link = await session.get(MeasurementSlotLink, link_id, with_for_update=True)
    if link is None:
        raise HTTPException(status_code=404, detail="Slot link not found")
    if link.review_status != "proposed":
        raise HTTPException(status_code=409, detail="Slot link was already reviewed")
    link.review_status = payload.decision
    link.reviewed_by = actor_id
    link.reviewed_at = datetime.now(UTC)
    if payload.note is not None:
        link.note = payload.note
    await record_event(
        session,
        actor_id=actor_id,
        action=f"measurement.slot_link_{payload.decision}",
        entity_type="measurement_slot_link",
        entity_id=link.id,
        before={"status": "proposed"},
        after={"status": payload.decision},
        request_id=request_id,
    )
    await session.commit()
    rows = await repository.links(session, entry_id=link.entry_id, pattern_id=link.pattern_id)
    return next(_link_read(*row) for row in rows if row[0].id == link.id)
