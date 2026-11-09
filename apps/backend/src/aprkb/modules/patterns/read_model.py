"""One database read contract for current pattern versions and recommendations."""

import re
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.corpus.models import Article, License
from aprkb.modules.patterns.models import (
    DisciplineAffinity,
    EvidenceProvenance,
    PatternVersion,
    PhrasePattern,
    PhraseVariant,
    UsageConstraint,
)
from aprkb.modules.taxonomy.models import Intent, Move, Step

BRACKET_SLOT = re.compile(r"\[([A-Za-z][A-Za-z0-9_]*)\]")
BRACE_SLOT = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*)\}")


def normalized_frame(frame: str, slots: dict[str, object]) -> str:
    """Accept mined bracket slots only when all markers match the declared schema."""
    bracket_names = set(BRACKET_SLOT.findall(frame))
    if bracket_names and bracket_names == set(slots) and not BRACE_SLOT.search(frame):
        return BRACKET_SLOT.sub(lambda match: "{" + match.group(1) + "}", frame)
    return frame


@dataclass(frozen=True)
class PatternRead:
    id: UUID
    status: str
    intent_code: str
    intent_name: str
    current_version_id: UUID
    version_no: int
    change_note: str | None
    canonical_frame: str
    slots: dict[str, object]
    epistemic_strength: str | None
    epistemic_strength_labelled: bool
    claim_type: str | None
    claim_type_labelled: bool
    variants: list[dict[str, str | None]]
    evidence_min: str | None
    forbidden_contexts: list[str]
    allowed_sections: list[str]
    allowed_genres: list[str]
    source_type: str
    license_code: str | None
    license_name: str | None
    license_allows_display: bool
    license_flag: bool
    article_id: UUID | None
    source_reference: str | None
    source_sentence_count: int
    provenance_count: int
    discipline_affinities: list[dict[str, str | float]]

    def as_response(self) -> dict[str, object]:
        return {
            "id": self.id,
            "status": self.status,
            "intent_code": self.intent_code,
            "intent_name": self.intent_name,
            "current_version_id": self.current_version_id,
            "version_no": self.version_no,
            "change_note": self.change_note,
            "canonical_frame": self.canonical_frame,
            "slots": self.slots,
            "epistemic_strength": self.epistemic_strength,
            "epistemic_strength_labelled": self.epistemic_strength_labelled,
            "claim_type": self.claim_type,
            "claim_type_labelled": self.claim_type_labelled,
            "variants": self.variants,
            "evidence_min": self.evidence_min,
            "forbidden_contexts": self.forbidden_contexts,
            "allowed_sections": self.allowed_sections,
            "allowed_genres": self.allowed_genres,
            "source_type": self.source_type,
            "license_code": self.license_code,
            "license_name": self.license_name,
            "license_allows_display": self.license_allows_display,
            "license_flag": self.license_flag,
            "article_id": self.article_id,
            "source_reference": self.source_reference,
            "source_sentence_count": self.source_sentence_count,
            "discipline_affinities": self.discipline_affinities,
        }


async def load_current_patterns(
    session: AsyncSession,
    *,
    intent_code: str | None = None,
    pattern_id: UUID | None = None,
    version_id: UUID | None = None,
    section_code: str | None = None,
    genre_code: str | None = None,
    status: str | None = None,
    query: str | None = None,
    browse_query: str | None = None,
    has_slots: bool | None = None,
    move_code: str | None = None,
    claim_type: str | None = None,
    offset: int = 0,
    limit: int | None = None,
    display_only: bool = False,
    internal_use_codes: frozenset[str] = frozenset(),
) -> list[PatternRead]:
    statement = (
        select(PhrasePattern, Intent, PatternVersion, UsageConstraint)
        .join(Intent, Intent.id == PhrasePattern.intent_id)
        .join(PatternVersion, PatternVersion.id == PhrasePattern.current_version_id)
        .outerjoin(UsageConstraint, UsageConstraint.pattern_version_id == PatternVersion.id)
    )
    if intent_code:
        statement = statement.where(Intent.code == intent_code)
    if pattern_id:
        statement = statement.where(PhrasePattern.id == pattern_id)
    if version_id:
        statement = statement.where(PatternVersion.id == version_id)
    if section_code:
        statement = statement.where(UsageConstraint.allowed_sections.contains([section_code]))
    if status:
        statement = statement.where(PhrasePattern.status == status)
    if has_slots is not None:
        empty_slots = PatternVersion.slots == {}
        statement = statement.where(~empty_slots if has_slots else empty_slots)
    if genre_code:
        statement = statement.where(
            or_(
                UsageConstraint.allowed_genres.is_(None),
                UsageConstraint.allowed_genres == [],
                UsageConstraint.allowed_genres.contains([genre_code]),
            )
        )
    if claim_type:
        statement = statement.where(PatternVersion.claim_type == claim_type)
    if move_code:
        statement = (
            statement.join(Step, Step.id == Intent.step_id)
            .join(Move, Move.id == Step.move_id)
            .where(Move.code == move_code)
        )
    if query:
        terms = set(re.findall(r"[^\W_]+", query.casefold(), flags=re.UNICODE))
        if not terms:
            return []
        clauses = []
        for term in sorted(terms):
            escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            clauses.append(PatternVersion.canonical_frame.ilike(f"%{escaped}%", escape="\\"))
        statement = statement.where(or_(*clauses))
    statement = statement.order_by(PhrasePattern.created_at, PhrasePattern.id)
    if not display_only and not browse_query:
        statement = statement.offset(offset)
        if limit is not None:
            statement = statement.limit(limit)
    rows = (await session.execute(statement)).all()
    if not rows:
        return []
    version_ids = [version.id for _, _, version, _ in rows]
    variants = list(
        await session.scalars(
            select(PhraseVariant)
            .where(PhraseVariant.pattern_version_id.in_(version_ids))
            .order_by(PhraseVariant.created_at, PhraseVariant.id)
        )
    )
    sources = (
        await session.execute(
            select(EvidenceProvenance, License, Article)
            .outerjoin(License, License.id == EvidenceProvenance.license_id)
            .outerjoin(Article, Article.id == EvidenceProvenance.article_id)
            .where(EvidenceProvenance.pattern_version_id.in_(version_ids))
            .order_by(EvidenceProvenance.created_at, EvidenceProvenance.id)
        )
    ).all()
    affinities = list(
        await session.scalars(
            select(DisciplineAffinity)
            .where(DisciplineAffinity.pattern_version_id.in_(version_ids))
            .order_by(DisciplineAffinity.discipline_code)
        )
    )
    sources_by_version: defaultdict[
        UUID, list[tuple[EvidenceProvenance, License | None, Article | None]]
    ] = defaultdict(list)
    for grouped_source, grouped_license, grouped_article in sources:
        sources_by_version[grouped_source.pattern_version_id].append(
            (grouped_source, grouped_license, grouped_article)
        )
    variants_by_version: defaultdict[UUID, list[PhraseVariant]] = defaultdict(list)
    for variant in variants:
        variants_by_version[variant.pattern_version_id].append(variant)
    affinities_by_version: defaultdict[UUID, list[DisciplineAffinity]] = defaultdict(list)
    for affinity in affinities:
        affinities_by_version[affinity.pattern_version_id].append(affinity)

    result: list[PatternRead] = []
    for pattern, intent, version, usage in rows:
        provenance = sources_by_version[version.id]
        source, license_row, article = provenance[0] if len(provenance) == 1 else (None, None, None)
        source_type = source.source_type if source else "unknown"
        license_flag = bool(license_row and license_row.code in internal_use_codes)
        allows_display = bool(license_row and license_row.allows_display)
        if display_only and (
            pattern.status != "approved"
            or len(provenance) != 1
            or not (
                source_type == "authored"
                or (source_type == "mined" and (allows_display or license_flag))
            )
        ):
            continue
        if (
            browse_query
            and browse_query.strip().casefold()
            not in (
                f"{normalized_frame(version.canonical_frame, version.slots)} "
                f"{intent.code} {' '.join(usage.allowed_sections if usage else [])}"
            ).casefold()
        ):
            continue
        result.append(
            PatternRead(
                id=pattern.id,
                status=pattern.status,
                intent_code=intent.code,
                intent_name=intent.name,
                current_version_id=version.id,
                version_no=version.version_no,
                change_note=version.change_note,
                canonical_frame=normalized_frame(version.canonical_frame, version.slots),
                slots=version.slots,
                epistemic_strength=version.epistemic_strength
                if version.epistemic_strength != "unknown"
                else None,
                epistemic_strength_labelled=version.epistemic_strength != "unknown",
                claim_type=version.claim_type if version.claim_type != "unknown" else None,
                claim_type_labelled=version.claim_type != "unknown",
                variants=[
                    {"text": item.text, "register": item.register}
                    for item in variants_by_version[version.id]
                ],
                evidence_min=usage.evidence_min if usage else None,
                forbidden_contexts=usage.forbidden_contexts if usage else [],
                allowed_sections=usage.allowed_sections if usage else [],
                allowed_genres=(usage.allowed_genres or []) if usage else [],
                source_type=source_type,
                license_code=license_row.code if license_row else None,
                license_name=license_row.name if license_row else None,
                license_allows_display=allows_display,
                license_flag=license_flag,
                article_id=source.article_id if source else None,
                source_reference=article.doi if article else None,
                source_sentence_count=(
                    source.source_sentence_count
                    if source.source_sentence_count is not None
                    else len(source.sentence_ids or [])
                )
                if source
                else 0,
                provenance_count=len(provenance),
                discipline_affinities=[
                    {"discipline_code": item.discipline_code, "score": item.score}
                    for item in affinities_by_version[version.id]
                ],
            )
        )
    return (
        result[offset : offset + limit if limit is not None else None]
        if display_only or browse_query
        else result
    )
