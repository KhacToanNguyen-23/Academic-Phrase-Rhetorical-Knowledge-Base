"""Load reference enums, draft taxonomy, and self-authored sample patterns."""

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Any, cast
from uuid import NAMESPACE_URL, UUID, uuid5

import yaml  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from aprkb.core.config import settings
from aprkb.modules.academic_phrase_bank.models import (
    CommunicativeFunction,
    FunctionFamily,
    PatternVersionFunction,
    PatternVersionPragmaticTag,
    PhraseUsageProfile,
    PragmaticFeature,
)
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


POLICY_DIR = Path(__file__).resolve().parents[1] / "policies"


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


def _read_academic_phrase_policy() -> dict[str, Any]:
    with (POLICY_DIR / "academic_phrase_bank.yaml").open(encoding="utf-8") as policy_file:
        payload = yaml.safe_load(policy_file)
    if not isinstance(payload, dict):
        raise ValueError("Invalid academic phrase bank policy")
    return payload


async def _seed_academic_phrase_reference(session: AsyncSession) -> None:
    """Load the versioned APB option catalogs without overwriting curator state."""
    payload = _read_academic_phrase_policy()
    version = payload["version"]
    family_ids: dict[str, UUID] = {}
    for family_data in payload["function_families"]:
        family = await session.scalar(
            select(FunctionFamily).where(
                FunctionFamily.code == family_data["code"], FunctionFamily.version == version
            )
        )
        if family is None:
            family = FunctionFamily(
                id=_stable_id("apb-function-family", f"{version}:{family_data['code']}"),
                code=family_data["code"],
                label=family_data["label"],
                version=version,
                status="proposed",
            )
            session.add(family)
            await session.flush()
        family_ids[family_data["code"]] = family.id
        for function_code, label, purpose in family_data["functions"]:
            function = await session.scalar(
                select(CommunicativeFunction).where(
                    CommunicativeFunction.code == function_code,
                    CommunicativeFunction.version == version,
                )
            )
            if function is None:
                session.add(
                    CommunicativeFunction(
                        id=_stable_id("apb-communicative-function", f"{version}:{function_code}"),
                        family_id=family_ids[family_data["code"]],
                        code=function_code,
                        label=label,
                        purpose=purpose,
                        version=version,
                        status="proposed",
                    )
                )

    for feature_code, facet, label, description in payload["pragmatic_features"]:
        feature = await session.scalar(
            select(PragmaticFeature).where(
                PragmaticFeature.code == feature_code, PragmaticFeature.version == version
            )
        )
        if feature is None:
            session.add(
                PragmaticFeature(
                    id=_stable_id("apb-pragmatic-feature", f"{version}:{feature_code}"),
                    code=feature_code,
                    facet=facet,
                    label=label,
                    description=description,
                    version=version,
                    status="proposed",
                )
            )
    await session.flush()


async def _seed_patterns(
    session: AsyncSession,
    intents: dict[str, Intent],
    *,
    records: list[dict[str, Any]] | None = None,
) -> tuple[int, int]:
    licenses = {row.code: row for row in await session.scalars(select(License))}
    created_patterns = 0
    created_versions = 0
    for pattern_data in records if records is not None else _read_json("patterns.json"):
        intent = intents[pattern_data["intent_code"]]
        pattern_id = _stable_id("phrase-pattern", pattern_data["seed_key"])
        pattern = await session.get(PhrasePattern, pattern_id)
        if pattern is None:
            created_patterns += 1
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
            created_versions += 1
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
            license_row = licenses.get(pattern_data.get("license_code") or "")
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
    return created_patterns, created_versions


async def _seed_academic_phrases(
    session: AsyncSession,
    *,
    taxonomy_intents: dict[str, tuple[Intent, str]],
    payload: dict[str, Any] | None = None,
) -> None:
    """Seed authored phrases with explicit APB and optional taxonomy mappings."""
    # Mock facet labels apply only to the bundled development seed, never to imported sources.
    facet_defaults: dict[str, Any] = {} if payload else _read_json("academic_phrase_facets.json")
    payload = payload or _read_json("academic_phrases.json")
    category_counts: dict[str, int] = {}
    section_codes = {row["label"]: row["section_code"] for row in payload["section_mappings"]}
    function_codes = {
        (row["section"], row["category"]): row["function_code"]
        for row in payload["category_mappings"]
    }
    intent_codes = {
        (row["section"], row["category"]): row["intent_code"]
        for row in payload["category_mappings"]
    }
    taxonomy = {"version": _read_phrasebank_basic()["taxonomy_version"]}
    release = await session.scalar(
        select(TaxonomyRelease).where(TaxonomyRelease.version == taxonomy["version"])
    )
    if release is None:
        raise ValueError(f"Taxonomy release {taxonomy['version']} is not initialized")
    apb_version = _read_academic_phrase_policy()["version"]
    functions = {
        row.code: row
        for row in await session.scalars(
            select(CommunicativeFunction).where(CommunicativeFunction.version == apb_version)
        )
    }
    sections = {
        row.code: row
        for row in await session.scalars(select(Section).where(Section.release_id == release.id))
    }
    mock_features = {
        row.code: row
        for row in await session.scalars(
            select(PragmaticFeature).where(PragmaticFeature.version == apb_version)
        )
    }
    for record in payload["records"]:
        category_index = category_counts.get(record["Category"], 0)
        category_counts[record["Category"]] = category_index + 1
        mock = facet_defaults.get("by_category", {}).get(record["Category"], {})
        section_code = section_codes.get(record["Section"])
        function_code = function_codes.get((record["Section"], record["Category"]))
        intent_code = intent_codes.get((record["Section"], record["Category"]))
        section = sections.get(section_code or "")
        function = functions.get(function_code or "")
        intent_entry = taxonomy_intents.get(intent_code or "")
        if section is None or function is None or intent_entry is None:
            raise ValueError(
                "Unmapped APB classification or existing Intent: "
                f"{record['Section']}/{record['Category']} (intent={intent_code})"
            )
        intent, intent_section_code = intent_entry
        if intent_section_code != section_code:
            raise ValueError(
                f"Intent {intent.code} belongs to {intent_section_code}, not {section_code}"
            )
        phrase = record["Phrase"]
        identity = f"{section_code}:{function_code}:{phrase}"
        pattern_id = _stable_id("authored-academic-phrase", identity)
        pattern = await session.get(PhrasePattern, pattern_id)
        if pattern is None:
            pattern = PhrasePattern(
                id=pattern_id,
                intent_id=intent.id,
                status="draft",
            )
            session.add(pattern)
            await session.flush()
        elif pattern.intent_id != intent.id:
            pattern.intent_id = intent.id
        version = await session.scalar(
            select(PatternVersion).where(
                PatternVersion.pattern_id == pattern.id, PatternVersion.version_no == 1
            )
        )
        if version is None:
            version = PatternVersion(
                id=_stable_id("authored-academic-phrase-version", identity),
                pattern_id=pattern.id,
                version_no=1,
                canonical_frame=phrase,
                slots={},
                epistemic_strength="unknown",
                claim_type="unknown",
                change_note="User-authored Phrasebank seed; unreviewed classification.",
            )
            session.add(version)
            await session.flush()
        if pattern.current_version_id is None:
            pattern.current_version_id = version.id
        if (
            await session.scalar(
                select(PatternVersionFunction.id).where(
                    PatternVersionFunction.pattern_version_id == version.id,
                    PatternVersionFunction.function_id == function.id,
                )
            )
            is None
        ):
            session.add(
                PatternVersionFunction(
                    id=_stable_id("authored-academic-phrase-function", identity),
                    pattern_version_id=version.id,
                    function_id=function.id,
                    status="proposed",
                )
            )
        profile_id = _stable_id("authored-academic-phrase-profile", identity)
        profile = await session.get(PhraseUsageProfile, profile_id)
        mock_domain = mock["domains"][category_index % len(mock["domains"])] if mock else None
        if profile is None:
            profile = PhraseUsageProfile(
                id=profile_id,
                pattern_version_id=version.id,
                section_id=section.id,
                genre_code="RESEARCH_ARTICLE",
                language_code="en",
            )
            session.add(profile)
        if mock and profile.register_code is None:
            profile.register_code = mock["register"]
            profile.register_version = apb_version
            profile.discipline_code = mock_domain
        if mock:
            stance_code = mock["stances"][category_index % len(mock["stances"])]
            stance = mock_features.get(stance_code)
            tag_id = _stable_id("authored-academic-phrase-stance", identity)
            if stance is not None and await session.get(PatternVersionPragmaticTag, tag_id) is None:
                session.add(
                    PatternVersionPragmaticTag(
                        id=tag_id,
                        pattern_version_id=version.id,
                        feature_id=stance.id,
                        context_note="DEV MOCK stance label; unreviewed. TODO(owner)",
                    )
                )
        if (
            await session.scalar(
                select(UsageConstraint.id).where(UsageConstraint.pattern_version_id == version.id)
            )
            is None
        ):
            session.add(
                UsageConstraint(
                    id=_stable_id("authored-academic-phrase-usage", identity),
                    pattern_version_id=version.id,
                    allowed_sections=[section_code],
                    allowed_genres=["RESEARCH_ARTICLE"],
                )
            )
        if (
            await session.scalar(
                select(EvidenceProvenance.id).where(
                    EvidenceProvenance.pattern_version_id == version.id
                )
            )
            is None
        ):
            session.add(
                EvidenceProvenance(
                    id=_stable_id("authored-academic-phrase-provenance", identity),
                    pattern_version_id=version.id,
                    source_type="authored",
                    sentence_ids=[],
                )
            )
    await session.flush()


async def import_academic_phrases(session: AsyncSession, path: Path) -> int:
    """Import a self-authored APB JSON source into an already initialized taxonomy."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValueError("Academic Phrase Bank source must contain a records array")
    taxonomy_intents = await _taxonomy_intent_map(session)
    await _seed_academic_phrases(session, taxonomy_intents=taxonomy_intents, payload=payload)
    return len(payload["records"])


async def _taxonomy_intent_map(session: AsyncSession) -> dict[str, tuple[Intent, str]]:
    # Idempotent: guarantees the Online taxonomy release (structure only, no phrases) exists.
    await _seed_taxonomy(session)
    taxonomy = {"version": _read_phrasebank_basic()["taxonomy_version"]}
    release = await session.scalar(
        select(TaxonomyRelease).where(TaxonomyRelease.version == taxonomy["version"])
    )
    if release is None:
        raise ValueError(f"Taxonomy release {taxonomy['version']} is not initialized")
    intent_paths = (
        await session.execute(
            select(Intent, Section.code)
            .join(Step, Step.id == Intent.step_id)
            .join(Move, Move.id == Step.move_id)
            .join(Section, Section.id == Move.section_id)
            .where(Section.release_id == release.id)
        )
    ).all()
    return {intent.code: (intent, section_code) for intent, section_code in intent_paths}


async def import_pattern_seed(session: AsyncSession, path: Path) -> dict[str, int]:
    """Import self-authored AP-RKB seed records using the standard idempotent seeder."""
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("AP-RKB pattern seed must be a JSON array")
    taxonomy_intents = await _taxonomy_intent_map(session)
    intents = {code: intent for code, (intent, _section) in taxonomy_intents.items()}
    patterns, versions = await _seed_patterns(session, intents, records=records)
    return {"patterns": patterns, "versions": versions}


async def run_seed(session: AsyncSession) -> None:
    """Seed Online reference data and lab-authored Phrasebank Basic content."""
    await _seed_reference_enums(session, include_dev_license=settings.app_env in {"local", "test"})
    await _seed_taxonomy(session, include_phrasebank_basic=False)
    intents = await _seed_taxonomy(session)
    await _retire_legacy_online_patterns(session)
    await _seed_phrasebank_basic(session, intents)
    # Academic Phrase Bank: option catalogs, then the authored APB phrases (draft, unreviewed).
    await _seed_academic_phrase_reference(session)
    taxonomy_intents = await _taxonomy_intent_map(session)
    await _seed_academic_phrases(session, taxonomy_intents=taxonomy_intents)


async def init_reference(session: AsyncSession) -> None:
    """Production reference profile: no content or development-only license."""
    await _seed_reference_enums(session, include_dev_license=False)
    await _seed_taxonomy(session, include_phrasebank_basic=False)
    await _seed_academic_phrase_reference(session)


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
