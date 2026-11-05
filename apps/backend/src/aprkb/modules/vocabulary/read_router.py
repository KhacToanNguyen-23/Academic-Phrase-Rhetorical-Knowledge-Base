"""Public dictionary routes for the Academic Vocabulary List."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.vocabulary.read_schemas import (
    FamilyPage,
    LemmaDetail,
    LemmaPage,
    LetterCount,
    VocabularyPolicyLabels,
)
from aprkb.modules.vocabulary.read_service import (
    get_lemma_detail,
    list_family_page,
    list_lemma_page,
    list_letter_counts,
)

router = APIRouter(tags=["vocabulary"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Client = Annotated[ApiClient, Depends(require_role("client"))]


@router.get("/vocabulary/families", response_model=FamilyPage)
async def vocabulary_families(
    request: Request,
    _actor: Client,
    session: DatabaseSession,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> FamilyPage:
    if q is not None and not q.strip():
        raise HTTPException(status_code=422, detail="q must contain at least one character")
    labels = VocabularyPolicyLabels.from_policy(
        request.app.state.policy_bundle.vocabulary_import.labels
    )
    items, total = await list_family_page(session, q=q, limit=limit, offset=offset, labels=labels)
    return FamilyPage(items=items, total=total)


@router.get("/vocabulary/lemmas", response_model=LemmaPage)
async def vocabulary_lemmas(
    request: Request,
    _actor: Client,
    session: DatabaseSession,
    q: str | None = None,
    letter: str | None = Query(default=None, pattern=r"^(?:[a-zA-Z]|#)$"),
    core_only: bool = False,
    sort: Literal["alpha", "rank"] = "alpha",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> LemmaPage:
    if q is not None and not q.strip():
        raise HTTPException(status_code=422, detail="q must contain at least one character")
    labels = VocabularyPolicyLabels.from_policy(
        request.app.state.policy_bundle.vocabulary_import.labels
    )
    items, total = await list_lemma_page(
        session,
        q=q,
        letter=letter.lower() if letter else None,
        core_only=core_only,
        sort=sort,
        limit=limit,
        offset=offset,
        labels=labels,
    )
    return LemmaPage(items=items, total=total)


@router.get("/vocabulary/letters", response_model=list[LetterCount])
async def vocabulary_letters(
    _actor: Client,
    session: DatabaseSession,
    core_only: bool = False,
) -> list[LetterCount]:
    counts = await list_letter_counts(session, core_only=core_only)
    return [
        LetterCount(letter=letter, count=counts[letter])
        for letter in [*"abcdefghijklmnopqrstuvwxyz", "#"]
    ]


@router.get("/vocabulary/lemmas/{lemma_id}", response_model=LemmaDetail)
async def vocabulary_lemma(
    request: Request,
    lemma_id: UUID,
    _actor: Client,
    session: DatabaseSession,
) -> LemmaDetail:
    policy = request.app.state.policy_bundle.vocabulary_import
    labels = VocabularyPolicyLabels.from_policy(policy.labels)
    detail = await get_lemma_detail(
        session, lemma_id, labels=labels, domain_codes=policy.domain_codes
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Vocabulary lemma not found")
    return detail
