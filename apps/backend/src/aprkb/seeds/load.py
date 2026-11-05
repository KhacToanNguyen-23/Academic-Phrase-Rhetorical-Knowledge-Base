"""Load reference enums, draft taxonomy, and self-authored sample patterns."""

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Any, cast
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


def _find_seed_dir() -> Path | None:
    """Locate the local or packaged reference seed assets directory."""
    parents = Path(__file__).resolve().parents
    for parent in parents:
        candidate = parent / "data" / "seed"
        if candidate.is_dir():
            return candidate
    return None


SEED_DIR = _find_seed_dir()


def _read_json(name: str) -> Any:
    if SEED_DIR is None:
        raise RuntimeError(
            "Seed data is only available from a monorepo checkout, not a standalone "
            "backend build; seeding is a local/admin operation, not a runtime dependency."
        )
    with (SEED_DIR / name).open(encoding="utf-8") as seed_file:
        return json.load(seed_file)


def _read_phrasebank_basic() -> dict[str, Any]:
    """Read the packaged Online Phrasebank Basic source in local and deployed builds."""
    path = Path(__file__).with_name("phrasebank_basic.json")
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


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


async def _seed_taxonomy(
    session: AsyncSession, *, include_phrasebank_basic: bool = True
) -> dict[str, Any]:
    payload = _read_json("taxonomy.json")
    basic = _read_phrasebank_basic() if include_phrasebank_basic else None
    if basic is not None:
        payload["version"] = basic["taxonomy_version"]
        methods = next(section for section in payload["sections"] if section["code"] == "METHODS")
        move_data: dict[str, Any] = {
            "code": "METHODS_DESCRIBE",
            "name": basic["section_title"],
            "steps": [{"code": "METHODS_BASIC", "name": basic["section_title"], "intents": []}],
        }
        for category in basic["categories"]:
            slug = re.sub(r"[^A-Z0-9]+", "_", category["category_name"].upper()).strip("_")
            move_data["steps"][0]["intents"].append(
                {
                    "code": f"METHODS_{slug}"[:64],
                    "name": category["category_name"],
                    "description": basic["description"],
                }
            )
        existing_move = next(
            (item for item in methods["moves"] if item["code"] == move_data["code"]), None
        )
        if existing_move is None:
            methods["moves"].append(move_data)
        else:
            existing_move.update(move_data)
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
                id=_stable_id("section", f"{payload['version']}:{section_data['code']}"),
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
                    id=_stable_id("move", f"{payload['version']}:{move_data['code']}"),
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
                        id=_stable_id("step", f"{payload['version']}:{step_data['code']}"),
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
                            id=_stable_id("intent", f"{payload['version']}:{intent_data['code']}"),
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


def _phrasebank_frame(example: str) -> tuple[str, dict[str, dict[str, Any]]]:
    """Convert generic placeholders into the PatternVersion frame/slot contract."""
    frame = example.replace("X-ray", "\x00RAY\x00")
    slots: dict[str, dict[str, Any]] = {}

    def replace(
        pattern: str,
        name: str,
        label: str,
        instruction: str,
        slot_type: str = "text",
    ) -> None:
        nonlocal frame
        if re.search(pattern, frame, flags=re.IGNORECASE):
            frame = re.sub(pattern, f"{{{name}}}", frame, flags=re.IGNORECASE)
            slots[name] = {
                "type": slot_type,
                "label": label,
                "instruction": instruction,
                "required": True,
                "min_length": 1,
            }

    replace(r"(?<![A-Za-z])X(?=s\b)", "x", "X", "Replace X with a method, measure, or topic.")
    replace(r"(?<![A-Za-z])X(?![A-Za-z])", "x", "X", "Replace X with a method, measure, or topic.")
    replace(r"(?<![A-Za-z])Y(?![A-Za-z])", "y", "Y", "Replace Y with an outcome or variable.")
    replace(r"(?<![A-Za-z])Z(?![A-Za-z])", "z", "Z", "Replace Z with an outcome or variable.")
    replace(
        r"(?:…|\.{3,})",
        "details",
        "Completion",
        "Complete with details supported by your study.",
        "clause",
    )
    replace(
        r"\b(?:Smith|Jones)\b",
        "author",
        "Author",
        "Enter the author named in the source you cite.",
        "citation",
    )
    replace(r"\(\d{4}\)", "year", "Year", "Enter the source publication year.")
    return frame.replace("\x00RAY\x00", "X-ray"), slots


async def _seed_phrasebank_basic(session: AsyncSession, intents: dict[str, Intent]) -> None:
    """Seed the team-authored Phrasebank Basic into the Online pattern tables."""
    payload = _read_phrasebank_basic()
    desired_ids = {
        _stable_id("phrase-pattern", f"phrasebank-basic:{slug}:{index:03d}")
        for category in payload["categories"]
        for slug in [re.sub(r"[^a-z0-9]+", "-", category["category_name"].casefold()).strip("-")]
        for index, _ in enumerate(category["examples"], start=1)
    }
    existing_basic = await session.scalars(
        select(PhrasePattern)
        .join(PatternVersion, PatternVersion.id == PhrasePattern.current_version_id)
        .where(PatternVersion.change_note.like("%Phrasebank Basic v%"))
    )
    for existing_pattern in existing_basic:
        if existing_pattern.id not in desired_ids:
            existing_pattern.status = "retired"

    for category in payload["categories"]:
        slug = re.sub(r"[^a-z0-9]+", "-", category["category_name"].casefold()).strip("-")
        intent_code = "METHODS_" + re.sub(
            r"[^A-Z0-9]+", "_", category["category_name"].upper()
        ).strip("_")
        intent = intents[intent_code[:64]]
        for index, example in enumerate(category["examples"], start=1):
            seed_key = f"phrasebank-basic:{slug}:{index:03d}"
            pattern_id = _stable_id("phrase-pattern", seed_key)
            pattern = await session.get(PhrasePattern, pattern_id)
            if pattern is None:
                pattern = PhrasePattern(id=pattern_id, intent_id=intent.id, status="approved")
                session.add(pattern)
            else:
                pattern.intent_id = intent.id
                pattern.status = "approved"
            await session.flush()

            frame, slots = _phrasebank_frame(example)
            version = await session.scalar(
                select(PatternVersion)
                .where(PatternVersion.pattern_id == pattern.id)
                .order_by(PatternVersion.version_no.desc())
                .limit(1)
            )
            if version is None or (
                version.canonical_frame != frame
                or version.slots != slots
                or version.claim_type != "descriptive"
                or version.epistemic_strength != "low"
            ):
                version_no = 1 if version is None else version.version_no + 1
                version = PatternVersion(
                    id=_stable_id("pattern-version", f"{seed_key}:v{version_no}"),
                    pattern_id=pattern.id,
                    version_no=version_no,
                    canonical_frame=frame,
                    slots=slots,
                    epistemic_strength="low",
                    claim_type="descriptive",
                    change_note=(
                        f"{payload['source']['name']} Phrasebank Basic v"
                        f"{payload['content_version']}; internal use."
                    ),
                )
                session.add(version)
                await session.flush()
            pattern.current_version_id = version.id

            usage = await session.scalar(
                select(UsageConstraint).where(UsageConstraint.pattern_version_id == version.id)
            )
            if usage is None:
                session.add(
                    UsageConstraint(
                        pattern_version_id=version.id,
                        allowed_sections=["METHODS"],
                        allowed_genres=["RESEARCH_ARTICLE"],
                    )
                )
            provenance = await session.scalar(
                select(EvidenceProvenance).where(
                    EvidenceProvenance.pattern_version_id == version.id
                )
            )
            if provenance is None:
                session.add(
                    EvidenceProvenance(
                        pattern_version_id=version.id,
                        source_type=payload["source"]["type"],
                        sentence_ids=[],
                    )
                )
    await session.flush()


async def _retire_legacy_online_patterns(session: AsyncSession) -> None:
    """Hide prior development fixtures that were superseded by the canonical JSON."""
    legacy = await session.scalars(
        select(PhrasePattern)
        .join(PatternVersion, PatternVersion.id == PhrasePattern.current_version_id)
        .where(
            PatternVersion.change_note
            == "Self-authored development seed; TODO(owner, PRD-9): replace with approved examples."
        )
    )
    for pattern in legacy:
        pattern.status = "retired"


async def run_seed(session: AsyncSession) -> None:
    """Seed Online reference data and lab-authored Phrasebank Basic content."""
    await _seed_reference_enums(session, include_dev_license=settings.app_env in {"local", "test"})
    await _seed_taxonomy(session, include_phrasebank_basic=False)
    intents = await _seed_taxonomy(session)
    await _retire_legacy_online_patterns(session)
    await _seed_phrasebank_basic(session, intents)


async def init_reference(session: AsyncSession) -> None:
    """Production reference profile: no content or development-only license."""
    await _seed_reference_enums(session, include_dev_license=False)
    await _seed_taxonomy(session, include_phrasebank_basic=False)


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
