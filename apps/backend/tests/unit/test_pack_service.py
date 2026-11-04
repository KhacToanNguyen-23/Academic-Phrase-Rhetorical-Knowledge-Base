"""Export projection and exclusion checks using invented, content-free metadata."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest

from aprkb.modules.corpus.models import Article, License
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.pack import service
from aprkb.modules.pack.validator import load_references, validate_pack
from aprkb.modules.patterns.models import (
    EvidenceProvenance,
    PatternVersion,
    PhrasePattern,
    ReviewDecision,
    UsageConstraint,
)

NOW = datetime(2026, 11, 4, tzinfo=UTC)
SAMPLE = Path(__file__).resolve().parents[4] / "data/packs/sample-demo/patterns.json"


@pytest.mark.parametrize("version_no", [1, 2])
async def test_native_projection_uses_candidate_reviews_only_for_first_version(version_no):
    version = PatternVersion(
        id=uuid4(),
        pattern_id=uuid4(),
        version_no=version_no,
        canonical_frame="[X] suggest that [Y].",
        slots={"X": {"type": "noun_phrase", "signals": []}, "Y": {"type": "clause"}},
        claim_type="descriptive",
        epistemic_strength="moderate",
    )
    source = EvidenceProvenance(
        source_type="mined",
        article_id=uuid4(),
        license_id=uuid4(),
        sentence_ids=[uuid4(), uuid4()],
        source_sentence_count=None,
    )
    reviews = [
        ReviewDecision(
            candidate_id=uuid4(),
            round=round_no,
            decision="approve",
            reviewer_id=uuid4(),
            created_at=NOW,
            comment="Private article text must not transfer",
        )
        for round_no in (1, 2)
    ]
    session = AsyncMock()
    session.scalar.return_value = UsageConstraint(
        allowed_sections=["RESULTS"],
        allowed_genres=[],
        forbidden_contexts=[],
    )
    session.scalars.side_effect = (
        [[source], [], [], [uuid4()], reviews] if version_no == 1 else [[source], [], []]
    )
    session.get.side_effect = [
        License(code="CC-BY"),
        Article(doi="10.0000/invented"),
        ApiClient(name="Reviewer one", role="reviewer"),
        ApiClient(name="Reviewer two", role="reviewer"),
    ]

    projected = await service._stored_version(session, version)

    assert projected["canonical_frame"] == "{X} suggest that {Y}."
    assert projected["provenance"]["source_sentence_count"] == 2
    assert projected["provenance"]["article"] == {"doi": "10.0000/invented"}
    assert projected["slots"]["X"] == {"type": "noun_phrase"}
    assert len(projected["reviews"]) == (2 if version_no == 1 else 0)
    assert "Private article text" not in json.dumps(projected)
    assert "sentence_ids" not in json.dumps(projected)
    if version_no == 1:
        assert [review["reviewer"] for review in projected["reviews"]] == [
            "Reviewer one",
            "Reviewer two",
        ]
        assert all(
            review["decided_at"] == "2026-11-04T00:00:00Z" for review in projected["reviews"]
        )


async def test_imported_review_metadata_survives_reexport():
    version = PatternVersion(
        id=uuid4(),
        pattern_id=uuid4(),
        version_no=1,
        canonical_frame="An invented phrase",
        slots={},
        claim_type="descriptive",
        epistemic_strength="low",
    )
    review = ReviewDecision(
        pattern_version_id=version.id,
        round=1,
        decision="approve",
        reviewer_id=uuid4(),
        decided_at=NOW,
        comment="[reviewer: Offline reviewer (reviewer)] Reviewed metadata",
    )
    session = AsyncMock()
    session.scalar.return_value = UsageConstraint(
        allowed_sections=["RESULTS"],
        allowed_genres=[],
        forbidden_contexts=[],
    )
    session.scalars.side_effect = [
        [EvidenceProvenance(source_type="authored", sentence_ids=[])],
        [],
        [review],
    ]
    session.get.return_value = ApiClient(name="pack-importer", role="curator", is_active=False)

    projected = await service._stored_version(session, version)

    assert projected["reviews"][0]["reviewer"] == "Offline reviewer"
    assert projected["reviews"][0]["comment"] == "Reviewed metadata"


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("unknown", "E05"),
        ("license", "E12"),
        ("reviews", "E13"),
        ("frame", "E09"),
    ],
)
async def test_export_reports_excluded_graphs_and_writes_valid_deterministic_pack(
    tmp_path,
    monkeypatch,
    mutation,
    code,
):
    graph = json.loads(SAMPLE.read_text(encoding="utf-8"))[0]
    valid = graph["versions"][0]
    invalid = copy.deepcopy(valid)
    if mutation == "unknown":
        invalid["claim_type"] = "unknown"
    elif mutation == "frame":
        invalid["canonical_frame"] = "Invalid {missing}"
    else:
        invalid["provenance"] = {
            "source_type": "mined",
            "license_code": "DEV-UNVERIFIED" if mutation == "license" else "CC-BY",
            "article": {"doi": "10.0000/invented"},
            "source_sentence_count": 1,
        }
        invalid["reviews"] = []
    refs = load_references()
    monkeypatch.setattr(service, "database_references", AsyncMock(return_value=(refs, {}, {}, {})))
    monkeypatch.setattr(
        service, "_stored_version", AsyncMock(side_effect=[valid, invalid, valid, invalid])
    )
    version = PatternVersion(id=UUID(valid["version_id"]), version_no=1)
    rows = [
        PhrasePattern(
            id=uuid4(),
            intent_id=uuid4(),
            status="approved",
            current_version_id=version.id,
            created_at=NOW,
        )
        for _ in range(2)
    ]
    session = AsyncMock()
    session.scalars.side_effect = [rows, [version], [version], rows, [version], [version]]
    session.execute.return_value = Mock(
        one_or_none=Mock(return_value=tuple(graph["intent"].values()))
    )
    # JSON key order in the sample is alphabetical; use the relational path order.
    session.execute.return_value.one_or_none.return_value = tuple(
        graph["intent"][key] for key in ("taxonomy_version", "section", "move", "step", "intent")
    )

    report = await service.export_pack(session, tmp_path / "first")
    repeated = await service.export_pack(session, tmp_path / "second")

    assert report == repeated
    assert report["patterns"] == report["versions"] == 1
    assert report["excluded"][0]["pattern_id"] == str(rows[1].id)
    assert code in {finding["code"] for finding in report["excluded"][0]["findings"]}
    assert not validate_pack(tmp_path / "first", refs).has_errors
    for name in ("manifest.json", "patterns.json"):
        assert (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes()
