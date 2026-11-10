"""Test-only legacy pattern fixtures; never loaded by the Online initializer."""

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.corpus.models import License
from aprkb.modules.patterns.models import (
    EvidenceProvenance,
    PatternVersion,
    PhrasePattern,
    UsageConstraint,
)
from aprkb.modules.patterns.repository import get_intent


async def seed_legacy_pattern_fixtures(session: AsyncSession) -> None:
    """Add old generic frames explicitly for tests of unrelated pattern behavior."""
    path = Path(__file__).resolve().parents[3] / "data" / "seed" / "patterns.json"
    fixture_rows: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    licenses = {row.code: row for row in await session.scalars(select(License))}
    for row in fixture_rows:
        intent = await get_intent(session, row["intent_code"])
        if intent is None:
            raise AssertionError(f"Missing test fixture intent: {row['intent_code']}")
        pattern = PhrasePattern(intent_id=intent.id, status=row["status"])
        session.add(pattern)
        await session.flush()
        version = PatternVersion(
            pattern_id=pattern.id,
            version_no=1,
            canonical_frame=row["canonical_frame"],
            slots=row["slots"],
            epistemic_strength=row["epistemic_strength"],
            claim_type=row["claim_type"],
            change_note="Test-only legacy pattern fixture.",
        )
        session.add(version)
        await session.flush()
        pattern.current_version_id = version.id
        session.add(
            UsageConstraint(
                pattern_version_id=version.id,
                allowed_sections=row["allowed_sections"],
                allowed_genres=["RESEARCH_ARTICLE"],
            )
        )
        license_row = licenses.get(row.get("license_code"))
        session.add(
            EvidenceProvenance(
                pattern_version_id=version.id,
                source_type=row["source_type"],
                sentence_ids=[],
                license_id=license_row.id if license_row else None,
            )
        )
    await session.flush()
