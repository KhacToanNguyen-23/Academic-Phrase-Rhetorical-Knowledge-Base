"""Routes for the Metric & Measurement catalog; 404 everywhere while the flag is off."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_current_client, get_db_session
from aprkb.core.security import require_role
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.measurement import service
from aprkb.modules.measurement.importer import import_catalog, parse_catalog
from aprkb.modules.measurement.schemas import (
    Kind,
    LinkStatus,
    MeasurementDetail,
    MeasurementImportResult,
    MeasurementListResponse,
    PatternMeasurementsResponse,
    SlotLinkListResponse,
    SlotLinkProposal,
    SlotLinkRead,
    SlotLinkReview,
    SlotSuggestionsResponse,
)


async def require_enabled(request: Request) -> None:
    if not request.app.state.settings.measurement_enabled:
        raise HTTPException(status_code=404, detail="Measurement catalog is disabled")


Session = Annotated[AsyncSession, Depends(get_db_session)]
Curator = Annotated[ApiClient, Depends(require_role("curator"))]

router = APIRouter(
    tags=["measurement"],
    dependencies=[Depends(require_enabled), Depends(get_current_client)],
)
admin_router = APIRouter(tags=["measurement"], dependencies=[Depends(require_enabled)])


@router.get("", response_model=MeasurementListResponse)
async def list_measurements(
    session: Session,
    kind: Kind | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MeasurementListResponse:
    return await service.list_entries(session, kind=kind, query=q, limit=limit, offset=offset)


@router.get("/slot-suggestions", response_model=SlotSuggestionsResponse)
async def slot_suggestions(
    session: Session,
    pattern_id: UUID,
    slot: Annotated[str, Query(min_length=1, max_length=64)],
) -> SlotSuggestionsResponse:
    return await service.slot_suggestions(session, pattern_id=pattern_id, slot_name=slot)


@router.get("/pattern-measurements", response_model=PatternMeasurementsResponse)
async def pattern_measurements(session: Session, pattern_id: UUID) -> PatternMeasurementsResponse:
    return await service.pattern_measurements(session, pattern_id=pattern_id)


@router.get("/{code}", response_model=MeasurementDetail)
async def get_measurement(code: str, session: Session) -> MeasurementDetail:
    return await service.get_entry(session, code)


@admin_router.post("/imports", response_model=MeasurementImportResult)
async def import_measurements(
    request: Request,
    session: Session,
    actor: Curator,
    file: Annotated[UploadFile, File()],
) -> MeasurementImportResult:
    policy = request.app.state.policy_bundle.measurement
    raw = await file.read(policy.max_import_bytes + 1)
    try:
        catalog = parse_catalog(raw, policy)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    result = await import_catalog(
        session, catalog, actor_id=actor.id, request_id=request.state.request_id
    )
    return MeasurementImportResult.model_validate(result)


@admin_router.get("/slot-links", response_model=SlotLinkListResponse)
async def list_slot_links(
    session: Session,
    _actor: Curator,
    status: LinkStatus | None = None,
) -> SlotLinkListResponse:
    return await service.list_links(session, status=status)


@admin_router.post("/slot-links", response_model=SlotLinkRead, status_code=201)
async def propose_slot_link(
    request: Request, payload: SlotLinkProposal, session: Session, actor: Curator
) -> SlotLinkRead:
    return await service.propose_link(
        session, payload, actor_id=actor.id, request_id=request.state.request_id
    )


@admin_router.post("/slot-links/{link_id}/review", response_model=SlotLinkRead)
async def review_slot_link(
    request: Request,
    link_id: UUID,
    payload: SlotLinkReview,
    session: Session,
    actor: Curator,
) -> SlotLinkRead:
    return await service.review_link(
        session, link_id, payload, actor_id=actor.id, request_id=request.state.request_id
    )
