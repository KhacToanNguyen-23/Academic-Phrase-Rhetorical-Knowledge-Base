"""Pattern discovery and curator/admin write endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.patterns import service
from aprkb.modules.patterns.schemas import (
    PatternCreate,
    PatternDetail,
    PatternSummary,
    PatternVersionCreate,
    PatternVersionRead,
    RenderableVersionRead,
)

router = APIRouter(tags=["patterns"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Client = Annotated[ApiClient, Depends(require_role("client"))]
Curator = Annotated[ApiClient, Depends(require_role("curator"))]
Admin = Annotated[ApiClient, Depends(require_role("admin"))]


@router.get("/versions/{version_id}", response_model=RenderableVersionRead)
async def get_renderable_version(
    version_id: UUID, _client: Client, session: DatabaseSession, request: Request
) -> RenderableVersionRead:
    version = await service.get_renderable_version(
        session,
        version_id,
        frozenset(request.app.state.policy_bundle.license.internal_use_codes),
    )
    return RenderableVersionRead.model_validate(
        {
            **version.as_response(),
            "id": version.current_version_id,
            "pattern_id": version.id,
        }
    )


@router.get("", response_model=list[PatternSummary])
async def list_patterns(
    client: Client,
    session: DatabaseSession,
    request: Request,
    intent: str | None = None,
    section: str | None = None,
    q: Annotated[str | None, Query(max_length=500)] = None,
    has_slots: Annotated[
        bool | None, Query(description="Filter by whether fill-in fields are defined.")
    ] = None,
    pattern_status: Annotated[str | None, Query(alias="status")] = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PatternSummary]:
    rows = await service.list_patterns(
        session,
        intent=intent,
        section=section,
        query=q,
        has_slots=has_slots,
        status=pattern_status,
        offset=offset,
        limit=limit,
        renderable_only=client.role not in {"curator", "admin"},
        internal_use_codes=frozenset(request.app.state.policy_bundle.license.internal_use_codes),
    )
    return [PatternSummary.model_validate(row) for row in rows]


@router.get("/{pattern_id}", response_model=PatternDetail)
async def get_pattern(
    pattern_id: UUID, client: Client, session: DatabaseSession, request: Request
) -> PatternDetail:
    detail = (
        await service.pattern_detail(
            session,
            pattern_id,
            frozenset(request.app.state.policy_bundle.license.internal_use_codes),
        )
        if client.role in {"curator", "admin"}
        else await service.renderable_pattern_detail(
            session,
            pattern_id,
            frozenset(request.app.state.policy_bundle.license.internal_use_codes),
        )
    )
    return PatternDetail.model_validate(detail)


@router.get("/{pattern_id}/versions", response_model=list[PatternVersionRead])
async def get_versions(
    pattern_id: UUID, client: Client, session: DatabaseSession, request: Request
) -> list[PatternVersionRead]:
    versions = (
        await service.pattern_versions(session, pattern_id)
        if client.role in {"curator", "admin"}
        else await service.renderable_pattern_versions(
            session,
            pattern_id,
            frozenset(request.app.state.policy_bundle.license.internal_use_codes),
        )
    )
    return [PatternVersionRead.model_validate(version) for version in versions]


@router.post("", response_model=PatternDetail, status_code=status.HTTP_201_CREATED)
async def create_pattern(
    payload: PatternCreate,
    request: Request,
    actor: Curator,
    session: DatabaseSession,
) -> PatternDetail:
    result = await service.create_pattern(
        session, payload=payload, actor=actor, request_id=request.state.request_id
    )
    return PatternDetail.model_validate(result)


@router.post(
    "/{pattern_id}/versions",
    response_model=PatternVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def append_version(
    pattern_id: UUID,
    payload: PatternVersionCreate,
    request: Request,
    actor: Curator,
    session: DatabaseSession,
) -> PatternVersionRead:
    version = await service.append_version(
        session,
        pattern_id=pattern_id,
        payload=payload,
        actor=actor,
        request_id=request.state.request_id,
    )
    return PatternVersionRead.model_validate(version)


@router.post("/{pattern_id}/retire", response_model=PatternDetail)
async def retire_pattern(
    pattern_id: UUID,
    request: Request,
    actor: Admin,
    session: DatabaseSession,
) -> PatternDetail:
    await service.retire_pattern(
        session, pattern_id=pattern_id, actor=actor, request_id=request.state.request_id
    )
    return PatternDetail.model_validate(await service.pattern_detail(session, pattern_id))
