"""Mapping helpers for public vocabulary API responses."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.vocabulary.models import VocabFamily, VocabLemma
from aprkb.modules.vocabulary.read_schemas import (
    DomainStatRead,
    FamilyMemberRead,
    FamilyRead,
    LemmaDetail,
    LemmaSummary,
    VocabularyPolicyLabels,
)
from aprkb.modules.vocabulary.repository import (
    get_lemma,
    letter_counts,
    list_families,
    list_lemmas,
)


def _label(values: dict[str, str], code: str | None) -> str:
    return values.get(code or "", code or "")


def to_summary(lemma: VocabLemma, labels: VocabularyPolicyLabels) -> LemmaSummary:
    return LemmaSummary(
        id=lemma.id,
        word=lemma.word,
        pos=lemma.pos,
        pos_label=_label(labels.pos, lemma.pos),
        rank=lemma.rank,
        band=lemma.band,
        status=lemma.status,
        status_label=_label(labels.status, lemma.status),
        is_core=lemma.is_core,
    )


def _family_read(family: VocabFamily, labels: VocabularyPolicyLabels) -> FamilyRead:
    members = sorted(
        family.members,
        key=lambda member: (-member.freq, member.lemma.word, member.lemma.pos),
    )
    return FamilyRead(
        id=family.id,
        headword=family.headword,
        rank=family.rank,
        family_freq=family.family_freq,
        members=[
            FamilyMemberRead(
                lemma_id=member.lemma.id,
                word=member.lemma.word,
                pos=member.lemma.pos,
                pos_label=_label(labels.pos, member.lemma.pos),
                freq=member.freq,
                category=member.category,
                category_label=_label(labels.category, member.category),
                domains=member.lemma.domains,
            )
            for member in members
        ],
    )


def to_detail(
    lemma: VocabLemma,
    labels: VocabularyPolicyLabels,
    domain_codes: list[str],
) -> LemmaDetail:
    stats_by_domain = {stat.domain: stat for stat in lemma.domain_stats}
    families_by_id = {member.family.id: member.family for member in lemma.family_members}
    families = sorted(families_by_id.values(), key=lambda family: (family.rank, family.headword))
    return LemmaDetail(
        **to_summary(lemma, labels).model_dump(),
        coca_all=lemma.coca_all,
        coca_acad=lemma.coca_acad,
        ratio=lemma.ratio,
        disp=lemma.disp,
        range=lemma.domain_range,
        domains=lemma.domains,
        domain_stats=[
            DomainStatRead(
                domain=domain,
                domain_label=_label(labels.domains, domain),
                freq=stats_by_domain[domain].freq,
                relative_ratio=stats_by_domain[domain].relative_ratio,
            )
            for domain in domain_codes
            if domain in stats_by_domain
        ],
        families=[_family_read(family, labels) for family in families],
    )


async def list_lemma_page(
    session: AsyncSession,
    *,
    q: str | None,
    letter: str | None,
    core_only: bool,
    sort: str,
    limit: int,
    offset: int,
    labels: VocabularyPolicyLabels,
) -> tuple[list[LemmaSummary], int]:
    items, total = await list_lemmas(
        session,
        q=q,
        letter=letter,
        core_only=core_only,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return [to_summary(item, labels) for item in items], total


async def list_letter_counts(session: AsyncSession, *, core_only: bool) -> dict[str, int]:
    return await letter_counts(session, core_only=core_only)


async def list_family_page(
    session: AsyncSession,
    *,
    q: str | None,
    limit: int,
    offset: int,
    labels: VocabularyPolicyLabels,
) -> tuple[list[FamilyRead], int]:
    families, total = await list_families(session, q=q, limit=limit, offset=offset)
    return [_family_read(family, labels) for family in families], total


async def get_lemma_detail(
    session: AsyncSession,
    lemma_id: UUID,
    *,
    labels: VocabularyPolicyLabels,
    domain_codes: list[str],
) -> LemmaDetail | None:
    lemma = await get_lemma(session, lemma_id)
    return to_detail(lemma, labels, domain_codes) if lemma is not None else None
