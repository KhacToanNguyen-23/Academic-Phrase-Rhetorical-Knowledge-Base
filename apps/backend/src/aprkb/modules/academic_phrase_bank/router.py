"""Academic Phrase Bank browse and curator metadata routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.academic_phrase_bank import service
from aprkb.modules.academic_phrase_bank.schemas import (
    AcademicPhraseMetadataCreate,
    AcademicPhrasePage,
    AcademicPhraseRead,
    DomainCatalog,
    DomainOption,
    FunctionCatalog,
    FunctionOption,
    PragmaticCatalog,
    PragmaticFeatureOption,
)
from aprkb.modules.identity.models import ApiClient

router = APIRouter(tags=["academic phrase bank"])
admin_router = APIRouter(tags=["admin academic phrase bank"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Client = Annotated[ApiClient, Depends(require_role("client"))]
Curator = Annotated[ApiClient, Depends(require_role("curator"))]


@router.get("/functions", response_model=FunctionCatalog)
async def list_functions(_actor: Client, session: DatabaseSession) -> FunctionCatalog:
    return FunctionCatalog(
        items=[
            FunctionOption.model_validate(item) for item in await service.function_catalog(session)
        ]
    )


@router.get("/pragmatic-features", response_model=PragmaticCatalog)
async def list_pragmatic_features(_actor: Client, session: DatabaseSession) -> PragmaticCatalog:
    return PragmaticCatalog(
        items=[
            PragmaticFeatureOption.model_validate(item)
            for item in await service.pragmatic_catalog(session)
        ]
    )


@router.get("/domains", response_model=DomainCatalog)
async def list_domains(_actor: Client, request: Request) -> DomainCatalog:
    policy = request.app.state.policy_bundle.vocabulary_import
    labels = policy.labels.domains
    return DomainCatalog(
        items=[
            DomainOption(code=code, label=labels.get(code, code), version=policy.version)
            for code in sorted(policy.domain_codes)
        ]
    )


@router.get("", response_model=AcademicPhrasePage)
async def list_phrases(
    actor: Client,
    session: DatabaseSession,
    request: Request,
    q: Annotated[str | None, Query(max_length=500)] = None,
    function: Annotated[str | None, Query(max_length=64)] = None,
    function_version: Annotated[str | None, Query(max_length=32)] = None,
    section: Annotated[str | None, Query(max_length=64)] = None,
    move: Annotated[str | None, Query(max_length=64)] = None,
    step: Annotated[str | None, Query(max_length=64)] = None,
    intent: Annotated[str | None, Query(max_length=64)] = None,
    genre: Annotated[str | None, Query(max_length=64)] = None,
    register: Annotated[str | None, Query(max_length=64)] = None,
    register_version: Annotated[str | None, Query(max_length=32)] = None,
    domain: Annotated[str | None, Query(max_length=128)] = None,
    stance: Annotated[str | None, Query(max_length=64)] = None,
    stance_version: Annotated[str | None, Query(max_length=32)] = None,
    pragmatic: Annotated[str | None, Query(max_length=64)] = None,
    pragmatic_version: Annotated[str | None, Query(max_length=32)] = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> AcademicPhrasePage:
    items, total = await service.list_phrases(
        session,
        q=q,
        function=function,
        function_version=function_version,
        section=section,
        move=move,
        step=step,
        intent=intent,
        genre=genre,
        register=register,
        register_version=register_version,
        domain=domain,
        stance=stance,
        stance_version=stance_version,
        pragmatic=pragmatic,
        pragmatic_version=pragmatic_version,
        include_unreviewed=actor.role in {"curator", "admin"},
        internal_use_codes=frozenset(request.app.state.policy_bundle.license.internal_use_codes),
        offset=offset,
        limit=limit,
    )
    return AcademicPhrasePage(
        items=[AcademicPhraseRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{pattern_id}", response_model=AcademicPhraseRead)
async def get_phrase(
    pattern_id: UUID,
    actor: Client,
    session: DatabaseSession,
    request: Request,
) -> AcademicPhraseRead:
    rows, _ = await service.list_phrases(
        session,
        include_unreviewed=actor.role in {"curator", "admin"},
        internal_use_codes=frozenset(request.app.state.policy_bundle.license.internal_use_codes),
        pattern_id=pattern_id,
        limit=1,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Academic phrase not found")
    return AcademicPhraseRead.model_validate(rows[0])


@admin_router.post(
    "/academic-phrases/versions/{version_id}/metadata",
    response_model=AcademicPhraseRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_phrase_metadata(
    version_id: UUID,
    payload: AcademicPhraseMetadataCreate,
    actor: Curator,
    session: DatabaseSession,
    request: Request,
) -> AcademicPhraseRead:
    result = await service.add_metadata(
        session,
        version_id=version_id,
        payload=payload,
        actor=actor,
        request_id=request.state.request_id,
        internal_use_codes=frozenset(request.app.state.policy_bundle.license.internal_use_codes),
        domain_codes=frozenset(request.app.state.policy_bundle.vocabulary_import.domain_codes),
    )
    return AcademicPhraseRead.model_validate(result)
