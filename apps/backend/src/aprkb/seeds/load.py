"""Load reference enums, draft taxonomy, and self-authored sample patterns."""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from aprkb.core.config import settings
from aprkb.modules.corpus.models import License
from aprkb.modules.patterns.models import (
    EvidenceProvenance,
    PatternVersion,
    PhrasePattern,
    UsageConstraint,
)
from aprkb.modules.taxonomy.models import ArticleGenre, Intent, Move, Section, Step, TaxonomyRelease
from aprkb.policies.loader import load_policy_bundle
from aprkb.shared.models import RefEnum

_MODULE_PARENTS = Path(__file__).resolve().parents
SEED_DIR = (
    (_MODULE_PARENTS[5] if len(_MODULE_PARENTS) > 5 else _MODULE_PARENTS[-2]) / "data" / "seed"
)


def _read_json(name: str) -> Any:
    with (SEED_DIR / name).open(encoding="utf-8") as seed_file:
        return json.load(seed_file)


def _stable_id(kind: str, key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"aprkb:seed:{kind}:{key}")


async def _seed_reference_enums(session: AsyncSession, *, include_dev_license: bool = True) -> None:
    for group, values in _read_json("reference_enums.json").items():
        for value in values:
            row = await session.scalar(
                select(RefEnum).where(RefEnum.group == group, RefEnum.code == value["code"])
            )
            if row is None:
                row = RefEnum(
                    group=group, code=value["code"], label=value["label"], order=value["order"]
                )
                session.add(row)
            else:
                row.label = value["label"]
                row.order = value["order"]
    for entry in load_policy_bundle().licenses.licenses:
        code, name = entry.code, entry.name
        if code == "DEV-UNVERIFIED" and not include_dev_license:
            continue
        allows_mining, allows_display = entry.allows_mining, entry.allows_display
        license_row = await session.scalar(select(License).where(License.code == code))
        if license_row is None:
            session.add(
                License(
                    id=_stable_id("license", code),
                    code=code,
                    name=name,
                    allows_mining=allows_mining,
                    allows_display=allows_display,
                )
            )
        else:
            license_row.name = name
            license_row.allows_mining = allows_mining
            license_row.allows_display = allows_display
    await session.flush()


async def _seed_taxonomy(session: AsyncSession) -> dict[str, Any]:
    payload = _read_json("taxonomy.json")
    release = await session.scalar(
        select(TaxonomyRelease).where(TaxonomyRelease.version == payload["version"])
    )
    if release is None:
        release = TaxonomyRelease(
            id=_stable_id("taxonomy-release", payload["version"]),
            version=payload["version"],
            status=payload["status"],
        )
        session.add(release)
    else:
        release.status = payload["status"]
    await session.flush()

    intents: dict[str, Intent] = {}
    for section_data in payload["sections"]:
        section = await session.scalar(
            select(Section).where(
                Section.release_id == release.id,
                Section.code == section_data["code"],
            )
        )
        if section is None:
            section = Section(
                id=_stable_id("section", section_data["code"]),
                code=section_data["code"],
                name=section_data["name"],
                order=section_data["order"],
                compatible_genres=section_data["compatible_genres"],
                release_id=release.id,
            )
            session.add(section)
        else:
            section.name = section_data["name"]
            section.order = section_data["order"]
            section.compatible_genres = section_data["compatible_genres"]
        await session.flush()
        for move_data in section_data["moves"]:
            move = await session.scalar(
                select(Move).where(Move.section_id == section.id, Move.code == move_data["code"])
            )
            if move is None:
                move = Move(
                    id=_stable_id("move", move_data["code"]),
                    code=move_data["code"],
                    name=move_data["name"],
                    section_id=section.id,
                )
                session.add(move)
            await session.flush()
            for step_data in move_data["steps"]:
                step = await session.scalar(
                    select(Step).where(Step.move_id == move.id, Step.code == step_data["code"])
                )
                if step is None:
                    step = Step(
                        id=_stable_id("step", step_data["code"]),
                        code=step_data["code"],
                        name=step_data["name"],
                        move_id=move.id,
                    )
                    session.add(step)
                await session.flush()
                for intent_data in step_data["intents"]:
                    intent = await session.scalar(
                        select(Intent).where(
                            Intent.step_id == step.id,
                            Intent.code == intent_data["code"],
                        )
                    )
                    if intent is None:
                        intent = Intent(
                            id=_stable_id("intent", intent_data["code"]),
                            code=intent_data["code"],
                            name=intent_data["name"],
                            description=intent_data.get("description"),
                            step_id=step.id,
                        )
                        session.add(intent)
                    intents[intent_data["code"]] = intent
    for genre_data in payload["article_genres"]:
        genre = await session.scalar(
            select(ArticleGenre).where(ArticleGenre.code == genre_data["code"])
        )
        if genre is None:
            session.add(
                ArticleGenre(
                    id=_stable_id("article-genre", genre_data["code"]),
                    code=genre_data["code"],
                    name=genre_data["name"],
                )
            )
    await session.flush()
    return intents


async def _seed_patterns(session: AsyncSession, intents: dict[str, Intent]) -> None:
    licenses = {row.code: row for row in await session.scalars(select(License))}
    for pattern_data in _read_json("patterns.json"):
        intent = intents[pattern_data["intent_code"]]
        pattern_id = _stable_id("phrase-pattern", pattern_data["seed_key"])
        pattern = await session.get(PhrasePattern, pattern_id)
        if pattern is None:
            pattern = PhrasePattern(
                id=pattern_id,
                intent_id=intent.id,
                status=pattern_data["status"],
            )
            session.add(pattern)
        else:
            pattern.status = pattern_data["status"]
            pattern.intent_id = intent.id
        await session.flush()

        version = await session.scalar(
            select(PatternVersion).where(
                PatternVersion.pattern_id == pattern.id,
                PatternVersion.version_no == 1,
            )
        )
        if version is None:
            version = PatternVersion(
                id=_stable_id("pattern-version", pattern_data["seed_key"]),
                pattern_id=pattern.id,
                version_no=1,
                canonical_frame=pattern_data["canonical_frame"],
                slots=pattern_data["slots"],
                epistemic_strength=pattern_data["epistemic_strength"],
                claim_type=pattern_data["claim_type"],
                change_note=(
                    "Self-authored development seed; "
                    "TODO(owner, PRD-9): replace with approved examples."
                ),
            )
            session.add(version)
            await session.flush()
        if pattern.current_version_id is None:
            pattern.current_version_id = version.id

        usage = await session.scalar(
            select(UsageConstraint).where(UsageConstraint.pattern_version_id == version.id)
        )
        if usage is None:
            session.add(
                UsageConstraint(
                    id=_stable_id("usage-constraint", pattern_data["seed_key"]),
                    pattern_version_id=version.id,
                    allowed_sections=pattern_data["allowed_sections"],
                    allowed_genres=["RESEARCH_ARTICLE"],
                )
            )
        provenance = await session.scalar(
            select(EvidenceProvenance).where(EvidenceProvenance.pattern_version_id == version.id)
        )
        if provenance is None:
            license_row = licenses.get(pattern_data.get("license_code"))
            session.add(
                EvidenceProvenance(
                    id=_stable_id("evidence-provenance", pattern_data["seed_key"]),
                    pattern_version_id=version.id,
                    source_type=pattern_data["source_type"],
                    sentence_ids=[],
                    license_id=license_row.id if license_row is not None else None,
                )
            )
    await session.flush()


async def run_seed(session: AsyncSession) -> None:
    """Seed reference data in the PRD order; caller controls commit/rollback."""
    await _seed_reference_enums(session)
    intents = await _seed_taxonomy(session)
    await _seed_patterns(session, intents)


async def init_reference(session: AsyncSession) -> None:
    """Production reference profile: no content or development-only license."""
    await _seed_reference_enums(session, include_dev_license=False)
    await _seed_taxonomy(session)


async def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-only", action="store_true")
    args = parser.parse_args()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            if args.reference_only:
                await init_reference(session)
            else:
                await run_seed(session)
            await session.commit()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
