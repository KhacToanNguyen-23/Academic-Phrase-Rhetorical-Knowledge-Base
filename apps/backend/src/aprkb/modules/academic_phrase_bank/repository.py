"""Deterministic APB browse queries and version metadata loading."""

from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import and_, exists, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.academic_phrase_bank.models import (
    CommunicativeFunction,
    FunctionFamily,
    PatternVersionFunction,
    PatternVersionMove,
    PatternVersionPragmaticTag,
    PatternVersionStep,
    PhraseCaveat,
    PhraseExample,
    PhraseUsageProfile,
    PragmaticFeature,
)
from aprkb.modules.corpus.models import License
from aprkb.modules.patterns.models import (
    DisciplineAffinity,
    EvidenceProvenance,
    PatternVersion,
    PhrasePattern,
    PhraseVariant,
    UsageConstraint,
)
from aprkb.modules.taxonomy.models import Intent, Move, Section, Step


async def function_catalog(session: AsyncSession) -> list[dict[str, object]]:
    rows = (
        await session.execute(
            select(CommunicativeFunction, FunctionFamily)
            .join(FunctionFamily, FunctionFamily.id == CommunicativeFunction.family_id)
            .order_by(FunctionFamily.code, CommunicativeFunction.code)
        )
    ).all()
    return [
        {
            "code": function.code,
            "label": function.label,
            "purpose": function.purpose,
            "version": function.version,
            "status": function.status,
            "family_code": family.code,
            "family_label": family.label,
        }
        for function, family in rows
    ]


async def pragmatic_catalog(session: AsyncSession) -> list[dict[str, object]]:
    rows = await session.scalars(
        select(PragmaticFeature).order_by(PragmaticFeature.facet, PragmaticFeature.code)
    )
    return [
        {
            "code": feature.code,
            "facet": feature.facet,
            "label": feature.label,
            "description": feature.description,
            "version": feature.version,
            "status": feature.status,
        }
        for feature in rows
    ]


async def search_versions(
    session: AsyncSession,
    *,
    q: str | None,
    function: str | None,
    function_version: str | None,
    section: str | None,
    move: str | None,
    step: str | None,
    intent: str | None,
    genre: str | None,
    register: str | None,
    register_version: str | None,
    domain: str | None,
    stance: str | None,
    stance_version: str | None,
    pragmatic: str | None,
    pragmatic_version: str | None,
    include_unreviewed: bool,
    internal_use_codes: frozenset[str],
    pattern_id: UUID | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[tuple[UUID, UUID]], int]:
    statement = select(PhrasePattern.id, PatternVersion.id).join(
        PatternVersion, PatternVersion.id == PhrasePattern.current_version_id
    )
    if pattern_id is not None:
        statement = statement.where(PhrasePattern.id == pattern_id)

    if not include_unreviewed:
        provenance_count = (
            select(func.count(EvidenceProvenance.id))
            .where(EvidenceProvenance.pattern_version_id == PatternVersion.id)
            .correlate(PatternVersion)
            .scalar_subquery()
        )
        eligible_source = exists(
            select(EvidenceProvenance.id)
            .outerjoin(License, License.id == EvidenceProvenance.license_id)
            .where(
                EvidenceProvenance.pattern_version_id == PatternVersion.id,
                or_(
                    EvidenceProvenance.source_type == "authored",
                    and_(
                        EvidenceProvenance.source_type == "mined",
                        or_(
                            License.allows_display.is_(True),
                            License.code.in_(internal_use_codes) if internal_use_codes else false(),
                        ),
                    ),
                ),
            )
        )
        statement = statement.where(
            PhrasePattern.status == "approved", provenance_count == 1, eligible_source
        )

    function_link_query = select(PatternVersionFunction.id).where(
        PatternVersionFunction.pattern_version_id == PatternVersion.id
    )
    if not include_unreviewed:
        function_link_query = function_link_query.where(PatternVersionFunction.status == "reviewed")
    if include_unreviewed:
        statement = statement.where(
            exists(
                select(PatternVersionFunction.id).where(
                    PatternVersionFunction.pattern_version_id == PatternVersion.id
                )
            )
        )
    else:
        statement = statement.where(exists(function_link_query))

    if function is not None:
        function_conditions = [
            PatternVersionFunction.pattern_version_id == PatternVersion.id,
            CommunicativeFunction.code == function,
        ]
        if function_version is not None:
            function_conditions.append(CommunicativeFunction.version == function_version)
        statement = statement.where(
            exists(
                select(PatternVersionFunction.id)
                .join(
                    CommunicativeFunction,
                    CommunicativeFunction.id == PatternVersionFunction.function_id,
                )
                .where(
                    *function_conditions,
                    *([] if include_unreviewed else [PatternVersionFunction.status == "reviewed"]),
                )
            )
        )

    if intent is not None:
        statement = statement.where(
            PhrasePattern.intent_id.in_(select(Intent.id).where(Intent.code == intent))
        )

    if section is not None:
        statement = statement.where(
            or_(
                exists(
                    select(PhraseUsageProfile.id)
                    .join(Section, Section.id == PhraseUsageProfile.section_id)
                    .where(
                        PhraseUsageProfile.pattern_version_id == PatternVersion.id,
                        Section.code == section,
                    )
                ),
                exists(
                    select(UsageConstraint.id).where(
                        UsageConstraint.pattern_version_id == PatternVersion.id,
                        UsageConstraint.allowed_sections.contains([section]),
                    )
                ),
            )
        )
    if genre is not None:
        statement = statement.where(
            or_(
                exists(
                    select(PhraseUsageProfile.id).where(
                        PhraseUsageProfile.pattern_version_id == PatternVersion.id,
                        PhraseUsageProfile.genre_code == genre,
                    )
                ),
                exists(
                    select(UsageConstraint.id).where(
                        UsageConstraint.pattern_version_id == PatternVersion.id,
                        or_(
                            UsageConstraint.allowed_genres.is_(None),
                            UsageConstraint.allowed_genres == [],
                            UsageConstraint.allowed_genres.contains([genre]),
                        ),
                    )
                ),
            )
        )
    if move is not None:
        statement = statement.where(
            exists(
                select(PatternVersionMove.id)
                .join(Move, Move.id == PatternVersionMove.move_id)
                .where(
                    PatternVersionMove.pattern_version_id == PatternVersion.id,
                    Move.code == move,
                )
            )
        )
    if step is not None:
        statement = statement.where(
            exists(
                select(PatternVersionStep.id)
                .join(Step, Step.id == PatternVersionStep.step_id)
                .where(
                    PatternVersionStep.pattern_version_id == PatternVersion.id,
                    Step.code == step,
                )
            )
        )
    if register is not None:
        register_matches = [
            exists(
                select(PhraseUsageProfile.id).where(
                    PhraseUsageProfile.pattern_version_id == PatternVersion.id,
                    PhraseUsageProfile.register_code == register,
                    *(
                        [PhraseUsageProfile.register_version == register_version]
                        if register_version is not None
                        else []
                    ),
                )
            )
        ]
        if register_version is None:
            register_matches.append(
                exists(
                    select(PhraseVariant.id).where(
                        PhraseVariant.pattern_version_id == PatternVersion.id,
                        PhraseVariant.register == register,
                    )
                )
            )
        statement = statement.where(or_(*register_matches))
    if domain is not None:
        statement = statement.where(
            or_(
                exists(
                    select(DisciplineAffinity.id).where(
                        DisciplineAffinity.pattern_version_id == PatternVersion.id,
                        DisciplineAffinity.discipline_code == domain,
                    )
                ),
                exists(
                    select(PhraseUsageProfile.id).where(
                        PhraseUsageProfile.pattern_version_id == PatternVersion.id,
                        PhraseUsageProfile.discipline_code == domain,
                    )
                ),
            )
        )
    for feature_code, feature_version, facet in (
        (stance, stance_version, "stance_type"),
        (pragmatic, pragmatic_version, None),
    ):
        if feature_code is None:
            continue
        conditions = [
            PatternVersionPragmaticTag.pattern_version_id == PatternVersion.id,
            PragmaticFeature.code == feature_code,
        ]
        if facet is not None:
            conditions.append(PragmaticFeature.facet == facet)
        if feature_version is not None:
            conditions.append(PragmaticFeature.version == feature_version)
        statement = statement.where(
            exists(
                select(PatternVersionPragmaticTag.id)
                .join(
                    PragmaticFeature, PragmaticFeature.id == PatternVersionPragmaticTag.feature_id
                )
                .where(*conditions)
            )
        )
    if q:
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        search_pattern = f"%{escaped}%"
        statement = statement.where(
            or_(
                PatternVersion.canonical_frame.ilike(search_pattern, escape="\\"),
                exists(
                    select(PatternVersionFunction.id)
                    .join(
                        CommunicativeFunction,
                        CommunicativeFunction.id == PatternVersionFunction.function_id,
                    )
                    .where(
                        PatternVersionFunction.pattern_version_id == PatternVersion.id,
                        or_(
                            CommunicativeFunction.code.ilike(search_pattern, escape="\\"),
                            CommunicativeFunction.label.ilike(search_pattern, escape="\\"),
                        ),
                    )
                ),
            )
        )

    total = await session.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    )
    rows = (
        await session.execute(
            statement.order_by(PhrasePattern.created_at, PhrasePattern.id)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return [(pattern_id, version_id) for pattern_id, version_id in rows], total or 0


async def version_metadata(
    session: AsyncSession, version_ids: Sequence[UUID]
) -> dict[UUID, dict[str, list[dict[str, object]]]]:
    result: dict[UUID, dict[str, list[dict[str, object]]]] = defaultdict(
        lambda: {
            "communicative_functions": [],
            "move_links": [],
            "step_links": [],
            "usage_profiles": [],
            "pragmatic_tags": [],
            "examples": [],
            "caveats": [],
        }
    )
    if not version_ids:
        return result

    function_rows = (
        await session.execute(
            select(PatternVersionFunction, CommunicativeFunction, FunctionFamily)
            .join(
                CommunicativeFunction,
                CommunicativeFunction.id == PatternVersionFunction.function_id,
            )
            .join(FunctionFamily, FunctionFamily.id == CommunicativeFunction.family_id)
            .where(PatternVersionFunction.pattern_version_id.in_(version_ids))
            .order_by(FunctionFamily.code, CommunicativeFunction.code)
        )
    ).all()
    for function_link, function, family in function_rows:
        result[function_link.pattern_version_id]["communicative_functions"].append(
            {
                "code": function.code,
                "label": function.label,
                "purpose": function.purpose,
                "version": function.version,
                "family_code": family.code,
                "family_label": family.label,
                "status": function_link.status,
                "context_note": function_link.context_note,
            }
        )

    move_rows = (
        await session.execute(
            select(PatternVersionMove, Move, Section)
            .join(Move, Move.id == PatternVersionMove.move_id)
            .join(Section, Section.id == Move.section_id)
            .where(PatternVersionMove.pattern_version_id.in_(version_ids))
            .order_by(Section.code, Move.code)
        )
    ).all()
    for move_link, move, section in move_rows:
        result[move_link.pattern_version_id]["move_links"].append(
            {
                "code": move.code,
                "label": move.name,
                "section_code": section.code,
                "relation": move_link.relation,
            }
        )

    step_rows = (
        await session.execute(
            select(PatternVersionStep, Step, Move)
            .join(Step, Step.id == PatternVersionStep.step_id)
            .join(Move, Move.id == Step.move_id)
            .where(PatternVersionStep.pattern_version_id.in_(version_ids))
            .order_by(Move.code, Step.code)
        )
    ).all()
    for step_link, step, move in step_rows:
        result[step_link.pattern_version_id]["step_links"].append(
            {
                "code": step.code,
                "label": step.name,
                "move_code": move.code,
                "relation": step_link.relation,
            }
        )

    profile_rows = (
        await session.execute(
            select(PhraseUsageProfile, Section)
            .outerjoin(Section, Section.id == PhraseUsageProfile.section_id)
            .where(PhraseUsageProfile.pattern_version_id.in_(version_ids))
            .order_by(PhraseUsageProfile.pattern_version_id, Section.code)
        )
    ).all()
    for profile, section in profile_rows:
        result[profile.pattern_version_id]["usage_profiles"].append(
            {
                "section_code": section.code if section else None,
                "section_label": section.name if section else None,
                "genre_code": profile.genre_code,
                "language_code": profile.language_code,
                "register_code": profile.register_code,
                "register_version": profile.register_version,
                "discipline_code": profile.discipline_code,
                "audience": profile.audience,
                "preferred_usage": profile.preferred_usage,
            }
        )

    tag_rows = (
        await session.execute(
            select(PatternVersionPragmaticTag, PragmaticFeature)
            .join(PragmaticFeature, PragmaticFeature.id == PatternVersionPragmaticTag.feature_id)
            .where(PatternVersionPragmaticTag.pattern_version_id.in_(version_ids))
            .order_by(PragmaticFeature.facet, PragmaticFeature.code)
        )
    ).all()
    for tag, feature in tag_rows:
        result[tag.pattern_version_id]["pragmatic_tags"].append(
            {
                "code": feature.code,
                "version": feature.version,
                "facet": feature.facet,
                "label": feature.label,
                "strength_note": tag.strength_note,
                "context_note": tag.context_note,
            }
        )

    examples = (
        await session.execute(
            select(PhraseExample, License)
            .outerjoin(License, License.id == PhraseExample.license_id)
            .where(PhraseExample.pattern_version_id.in_(version_ids))
            .where(
                or_(
                    PhraseExample.origin_kind != "licensed",
                    License.allows_display.is_(True),
                )
            )
            .order_by(PhraseExample.pattern_version_id, PhraseExample.created_at, PhraseExample.id)
        )
    ).all()
    for example, license_row in examples:
        result[example.pattern_version_id]["examples"].append(
            {
                "kind": example.example_kind,
                "text": example.text,
                "explanation": example.explanation,
                "origin_kind": example.origin_kind,
                "source_ref": example.source_ref,
                "license_id": example.license_id,
                "license_code": license_row.code if license_row else None,
                "license_allows_display": license_row.allows_display if license_row else None,
            }
        )

    caveats = await session.scalars(
        select(PhraseCaveat)
        .where(PhraseCaveat.pattern_version_id.in_(version_ids))
        .order_by(PhraseCaveat.pattern_version_id, PhraseCaveat.code)
    )
    for caveat in caveats:
        result[caveat.pattern_version_id]["caveats"].append(
            {"code": caveat.code, "severity": caveat.severity, "message": caveat.message}
        )
    return result
