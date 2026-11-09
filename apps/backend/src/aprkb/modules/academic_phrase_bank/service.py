"""APB browsing and curator-authored metadata services."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.academic_phrase_bank import repository
from aprkb.modules.academic_phrase_bank.models import (
    CommunicativeFunction,
    PatternVersionFunction,
    PatternVersionMove,
    PatternVersionPragmaticTag,
    PatternVersionStep,
    PhraseCaveat,
    PhraseExample,
    PhraseUsageProfile,
    PragmaticFeature,
)
from aprkb.modules.academic_phrase_bank.schemas import AcademicPhraseMetadataCreate
from aprkb.modules.audit.service import record_event
from aprkb.modules.corpus.models import License
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.patterns import read_model
from aprkb.modules.patterns.models import PatternVersion, PhrasePattern
from aprkb.modules.taxonomy.models import ArticleGenre, Move, Section, Step, TaxonomyRelease


async def function_catalog(session: AsyncSession) -> list[dict[str, object]]:
    return await repository.function_catalog(session)


async def pragmatic_catalog(session: AsyncSession) -> list[dict[str, object]]:
    return await repository.pragmatic_catalog(session)


async def list_phrases(
    session: AsyncSession,
    *,
    q: str | None = None,
    function: str | None = None,
    function_version: str | None = None,
    section: str | None = None,
    move: str | None = None,
    step: str | None = None,
    intent: str | None = None,
    genre: str | None = None,
    register: str | None = None,
    register_version: str | None = None,
    domain: str | None = None,
    stance: str | None = None,
    stance_version: str | None = None,
    pragmatic: str | None = None,
    pragmatic_version: str | None = None,
    include_unreviewed: bool = False,
    internal_use_codes: frozenset[str] = frozenset(),
    pattern_id: UUID | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict[str, object]], int]:
    if function is not None:
        function_versions = set(
            await session.scalars(
                select(CommunicativeFunction.version).where(CommunicativeFunction.code == function)
            )
        )
        if not function_versions:
            raise HTTPException(status_code=422, detail=f"Unknown APB function code: {function}")
        if function_version is None and len(function_versions) > 1:
            raise HTTPException(
                status_code=422,
                detail=(
                    "function_version is required when a function code exists in multiple versions"
                ),
            )
        if function_version is not None and function_version not in function_versions:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown APB function version for code: {function}",
            )
    for feature_code, feature_version, facet in (
        (register, register_version, "register"),
        (stance, stance_version, "stance_type"),
        (pragmatic, pragmatic_version, None),
    ):
        if feature_code is None:
            continue
        feature_query = select(PragmaticFeature.version).where(
            PragmaticFeature.code == feature_code
        )
        if facet is not None:
            feature_query = feature_query.where(PragmaticFeature.facet == facet)
        feature_versions = set(await session.scalars(feature_query))
        if not feature_versions:
            raise HTTPException(
                status_code=422, detail=f"Unknown pragmatic feature code: {feature_code}"
            )
        if feature_version is None and len(feature_versions) > 1:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"A version is required when pragmatic feature {feature_code} "
                    "exists in multiple versions"
                ),
            )
        if feature_version is not None and feature_version not in feature_versions:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown pragmatic feature version for code: {feature_code}",
            )
    selected, total = await repository.search_versions(
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
        include_unreviewed=include_unreviewed,
        internal_use_codes=internal_use_codes,
        pattern_id=pattern_id,
        offset=offset,
        limit=limit,
    )
    pattern_ids = [pattern_id for pattern_id, _ in selected]
    patterns = await read_model.load_current_patterns(
        session,
        pattern_ids=pattern_ids,
        display_only=not include_unreviewed,
        internal_use_codes=internal_use_codes,
    )
    version_ids = [pattern.current_version_id for pattern in patterns]
    metadata = await repository.version_metadata(session, version_ids)
    results: list[dict[str, object]] = []
    for pattern in patterns:
        results.append(
            {
                **pattern.as_response(),
                **metadata.get(pattern.current_version_id, {}),
            }
        )
    return results, total


async def add_metadata(
    session: AsyncSession,
    *,
    version_id: UUID,
    payload: AcademicPhraseMetadataCreate,
    actor: ApiClient,
    request_id: str,
    internal_use_codes: frozenset[str] = frozenset(),
    domain_codes: frozenset[str] = frozenset(),
) -> dict[str, object]:
    version = await session.get(PatternVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Pattern version not found")
    pattern = await session.get(PhrasePattern, version.pattern_id)
    if pattern is None:
        raise HTTPException(status_code=404, detail="Pattern not found")
    if pattern.current_version_id != version.id:
        raise HTTPException(status_code=409, detail="APB metadata must target the current version")

    existing_function = await session.scalar(
        select(PatternVersionFunction.id)
        .where(PatternVersionFunction.pattern_version_id == version.id)
        .limit(1)
    )
    if existing_function is not None:
        raise HTTPException(status_code=409, detail="APB metadata already exists for this version")

    function_rows = list(
        await session.scalars(
            select(CommunicativeFunction).where(
                CommunicativeFunction.code.in_(payload.function_codes),
                *(
                    [CommunicativeFunction.version == payload.function_version]
                    if payload.function_version
                    else []
                ),
            )
        )
    )
    functions_by_code: dict[str, CommunicativeFunction] = {}
    for function_row in function_rows:
        if function_row.code in functions_by_code:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"function_version is required because {function_row.code} exists "
                    "in multiple versions"
                ),
            )
        functions_by_code[function_row.code] = function_row
    if set(functions_by_code) != set(payload.function_codes):
        missing = sorted(set(payload.function_codes) - set(functions_by_code))
        raise HTTPException(
            status_code=422, detail=f"Unknown APB function code(s): {', '.join(missing)}"
        )

    release = await session.scalar(
        select(TaxonomyRelease)
        .where(TaxonomyRelease.status == "published")
        .order_by(TaxonomyRelease.published_at.desc(), TaxonomyRelease.version.desc())
        .limit(1)
    )
    if release is None and (
        any(profile.section_code for profile in payload.usage_profiles)
        or payload.move_links
        or payload.step_links
    ):
        raise HTTPException(status_code=409, detail="No published taxonomy release is available")

    section_rows: dict[str, Section] = {}
    section_codes = {
        profile.section_code
        for profile in payload.usage_profiles
        if profile.section_code is not None
    }
    section_codes.update(link.section_code for link in payload.move_links)
    section_codes.update(link.section_code for link in payload.step_links)
    if section_codes and release is not None:
        sections = list(
            await session.scalars(
                select(Section).where(
                    Section.release_id == release.id,
                    Section.code.in_(section_codes),
                )
            )
        )
        section_rows = {section.code: section for section in sections}
        if set(section_rows) != section_codes:
            missing = sorted(section_codes - set(section_rows))
            raise HTTPException(
                status_code=422, detail=f"Unknown section code(s): {', '.join(missing)}"
            )

    genre_codes = {profile.genre_code for profile in payload.usage_profiles if profile.genre_code}
    if genre_codes:
        genres = set(
            await session.scalars(
                select(ArticleGenre.code).where(ArticleGenre.code.in_(genre_codes))
            )
        )
        if genres != genre_codes:
            missing = sorted(genre_codes - genres)
            raise HTTPException(
                status_code=422, detail=f"Unknown genre code(s): {', '.join(missing)}"
            )

    register_versions: list[str | None] = []
    for profile in payload.usage_profiles:
        if profile.register_code is None:
            register_versions.append(None)
            continue
        register_query = select(PragmaticFeature).where(
            PragmaticFeature.code == profile.register_code,
            PragmaticFeature.facet == "register",
        )
        if profile.register_version is not None:
            register_query = register_query.where(
                PragmaticFeature.version == profile.register_version
            )
        register_options = list(await session.scalars(register_query))
        if len(register_options) != 1:
            if not register_options:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown register code/version: {profile.register_code}",
                )
            raise HTTPException(
                status_code=422,
                detail=f"register_version is required for {profile.register_code}",
            )
        register_versions.append(register_options[0].version)

    requested_domains = {
        profile.discipline_code for profile in payload.usage_profiles if profile.discipline_code
    }
    if requested_domains - domain_codes:
        missing = sorted(requested_domains - domain_codes)
        raise HTTPException(status_code=422, detail=f"Unknown domain code(s): {', '.join(missing)}")

    move_rows: dict[tuple[str, str], Move] = {}
    for move_link in payload.move_links:
        section = section_rows[move_link.section_code]
        move = await session.scalar(
            select(Move).where(Move.section_id == section.id, Move.code == move_link.move_code)
        )
        if move is None:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown Move path: {move_link.section_code}/{move_link.move_code}",
            )
        move_rows[(move_link.section_code, move_link.move_code)] = move

    step_rows: dict[tuple[str, str, str], Step] = {}
    for step_link in payload.step_links:
        section = section_rows[step_link.section_code]
        move = move_rows.get((step_link.section_code, step_link.move_code))
        if move is None:
            move = await session.scalar(
                select(Move).where(Move.section_id == section.id, Move.code == step_link.move_code)
            )
        if move is None:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown Move path: {step_link.section_code}/{step_link.move_code}",
            )
        step = await session.scalar(
            select(Step).where(Step.move_id == move.id, Step.code == step_link.step_code)
        )
        if step is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Unknown Step path: {step_link.section_code}/"
                    f"{step_link.move_code}/{step_link.step_code}"
                ),
            )
        step_rows[(step_link.section_code, step_link.move_code, step_link.step_code)] = step

    feature_keys = {(tag.code, tag.version) for tag in payload.pragmatic_tags}
    features = []
    for feature_code, feature_version in sorted(feature_keys):
        feature = await session.scalar(
            select(PragmaticFeature).where(
                PragmaticFeature.code == feature_code,
                PragmaticFeature.version == feature_version,
            )
        )
        if feature is not None:
            features.append(feature)
    features_by_key = {(feature.code, feature.version): feature for feature in features}
    if set(features_by_key) != feature_keys:
        missing_feature_keys = feature_keys - set(features_by_key)
        raise HTTPException(
            status_code=422,
            detail=(
                "Unknown pragmatic feature code/version(s): "
                + ", ".join(sorted({code for code, _ in missing_feature_keys}))
            ),
        )

    licenses: dict[str, License] = {}
    license_codes = {example.license_code for example in payload.examples if example.license_code}
    if license_codes:
        license_rows = list(
            await session.scalars(select(License).where(License.code.in_(license_codes)))
        )
        licenses = {license_row.code: license_row for license_row in license_rows}
        if set(licenses) != license_codes:
            missing = sorted(license_codes - set(licenses))
            raise HTTPException(
                status_code=422, detail=f"Unknown license code(s): {', '.join(missing)}"
            )
    for example in payload.examples:
        if example.origin_kind == "licensed":
            license_row = licenses.get(example.license_code or "")
            if not example.source_ref or license_row is None or not license_row.allows_display:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Licensed examples require a source reference and a "
                        "license that permits display"
                    ),
                )

    for function_code in payload.function_codes:
        session.add(
            PatternVersionFunction(
                pattern_version_id=version.id,
                function_id=functions_by_code[function_code].id,
                status="reviewed",
                created_by=actor.id,
            )
        )
    for move_link in payload.move_links:
        session.add(
            PatternVersionMove(
                pattern_version_id=version.id,
                move_id=move_rows[(move_link.section_code, move_link.move_code)].id,
                relation=move_link.relation,
                created_by=actor.id,
            )
        )
    for step_link in payload.step_links:
        session.add(
            PatternVersionStep(
                pattern_version_id=version.id,
                step_id=step_rows[
                    (step_link.section_code, step_link.move_code, step_link.step_code)
                ].id,
                relation=step_link.relation,
                created_by=actor.id,
            )
        )
    for profile_index, profile in enumerate(payload.usage_profiles):
        session.add(
            PhraseUsageProfile(
                pattern_version_id=version.id,
                section_id=(
                    section_rows[profile.section_code].id if profile.section_code else None
                ),
                genre_code=profile.genre_code,
                language_code=profile.language_code,
                register_code=profile.register_code,
                register_version=register_versions[profile_index],
                discipline_code=profile.discipline_code,
                audience=profile.audience,
                preferred_usage=profile.preferred_usage,
                created_by=actor.id,
            )
        )
    for tag in payload.pragmatic_tags:
        session.add(
            PatternVersionPragmaticTag(
                pattern_version_id=version.id,
                feature_id=features_by_key[(tag.code, tag.version)].id,
                strength_note=tag.strength_note,
                context_note=tag.context_note,
                created_by=actor.id,
            )
        )
    for example in payload.examples:
        license_row = licenses.get(example.license_code or "")
        session.add(
            PhraseExample(
                pattern_version_id=version.id,
                example_kind=example.kind,
                text=example.text,
                explanation=example.explanation,
                origin_kind=example.origin_kind,
                source_ref=example.source_ref,
                license_id=license_row.id if license_row else None,
                created_by=actor.id,
            )
        )
    for caveat in payload.caveats:
        session.add(
            PhraseCaveat(
                pattern_version_id=version.id,
                code=caveat.code,
                severity=caveat.severity,
                message=caveat.message,
                created_by=actor.id,
            )
        )
    try:
        await session.flush()
        await record_event(
            session,
            actor_id=actor.id,
            action="academic_phrase.metadata.create",
            entity_type="pattern_version",
            entity_id=version.id,
            after={
                "function_codes": sorted(payload.function_codes),
                "move_link_count": len(payload.move_links),
                "step_link_count": len(payload.step_links),
                "usage_profile_count": len(payload.usage_profiles),
                "pragmatic_tag_codes": sorted(
                    f"{code}@{tag_version}" for code, tag_version in feature_keys
                ),
                "example_count": len(payload.examples),
                "caveat_count": len(payload.caveats),
            },
            request_id=request_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    rows, _ = await list_phrases(
        session,
        include_unreviewed=True,
        internal_use_codes=internal_use_codes,
        pattern_id=pattern.id,
        limit=1,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Academic phrase not found")
    return rows[0]
