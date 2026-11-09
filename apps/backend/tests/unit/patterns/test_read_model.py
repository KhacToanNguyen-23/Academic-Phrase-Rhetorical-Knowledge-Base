"""Read-time compatibility for invented mined-style frames."""

from dataclasses import asdict
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from aprkb.modules.composition.renderer import render_frame
from aprkb.modules.corpus.models import Article, License
from aprkb.modules.patterns.models import (
    DisciplineAffinity,
    EvidenceProvenance,
    PatternVersion,
    PhrasePattern,
    PhraseVariant,
    UsageConstraint,
)
from aprkb.modules.patterns.read_model import load_current_patterns, normalized_frame
from aprkb.modules.taxonomy.models import Intent


def test_mined_bracket_frame_renders_only_when_slot_names_match():
    slots: dict[str, object] = {"X": {"type": "topic"}, "Y": {"type": "claim"}}
    frame = "[X] demonstrate that [Y]"
    normalized = normalized_frame(frame, slots)
    assert normalized == "{X} demonstrate that {Y}"
    assert render_frame(
        normalized, slots, {"X": "The invented results", "Y": "the method works"}
    ) == (
        "The invented results demonstrate that the method works",
        [],
    )
    assert normalized_frame(frame, {"X": {"type": "topic"}}) == frame


@pytest.mark.parametrize(
    "stored_count,local_count,expected",
    [(12, 0, 12), (12, 2, 12), (None, 2, 2), (None, 0, 0), (0, 2, 0)],
)
async def test_online_sentence_count_uses_stored_count_or_local_ids(
    stored_count: int | None, local_count: int, expected: int
) -> None:
    version_id = uuid4()
    pattern = PhrasePattern(id=uuid4(), status="approved", current_version_id=version_id)
    version = PatternVersion(
        id=version_id,
        version_no=1,
        canonical_frame="An invented phrase",
        slots={},
        epistemic_strength="unknown",
        claim_type="unknown",
    )
    source = EvidenceProvenance(
        pattern_version_id=version_id,
        source_type="mined",
        sentence_ids=[uuid4() for _ in range(local_count)],
        source_sentence_count=stored_count,
    )
    session = AsyncMock()
    session.execute.side_effect = [
        Mock(
            all=Mock(
                return_value=[(pattern, Intent(code="TEST", name="Test"), version, None, "MOVE")]
            )
        ),
        Mock(all=Mock(return_value=[(source, None, None)])),
    ]
    session.scalars.side_effect = [[], []]

    rows = await load_current_patterns(session)

    assert len(rows) == 1
    assert rows[0].as_response()["source_sentence_count"] == expected
    assert rows[0].move_code == "MOVE"
    assert rows[0].as_response()["move_code"] == "MOVE"


@pytest.mark.parametrize(
    "source_type,allows_display,internal_codes,status,source_count,expected",
    [
        ("mined", False, {"INTERNAL"}, "approved", 1, True),
        ("mined", False, set(), "approved", 1, False),
        ("mined", True, set(), "approved", 1, True),
        ("authored", False, set(), "approved", 1, True),
        ("unknown", True, {"INTERNAL"}, "approved", 1, False),
        ("mined", False, {"INTERNAL"}, "draft", 1, False),
        ("mined", False, {"INTERNAL"}, "retired", 1, False),
        ("mined", False, {"INTERNAL"}, "approved", 0, False),
        ("mined", False, {"INTERNAL"}, "approved", 2, False),
    ],
)
async def test_internal_permission_does_not_bypass_other_renderability_checks(
    source_type, allows_display, internal_codes, status, source_count, expected
):
    version_id = uuid4()
    pattern = PhrasePattern(id=uuid4(), status=status, current_version_id=version_id)
    version = PatternVersion(
        id=version_id,
        version_no=1,
        canonical_frame="Invented phrase",
        slots={},
        epistemic_strength="low",
        claim_type="descriptive",
    )
    license_row = License(code="INTERNAL", name="Internal", allows_display=allows_display)
    sources = [
        (
            EvidenceProvenance(
                pattern_version_id=version_id, source_type=source_type, sentence_ids=[]
            ),
            license_row,
            None,
        )
        for _ in range(source_count)
    ]
    session = AsyncMock()
    session.execute.side_effect = [
        Mock(
            all=Mock(
                return_value=[(pattern, Intent(code="TEST", name="Test"), version, None, "MOVE")]
            )
        ),
        Mock(all=Mock(return_value=sources)),
    ]
    session.scalars.side_effect = [[], []]

    rows = await load_current_patterns(
        session, display_only=True, internal_use_codes=frozenset(internal_codes)
    )

    assert bool(rows) is expected
    if rows:
        assert rows[0].license_allows_display is allows_display
        assert rows[0].license_flag is ("INTERNAL" in internal_codes)


@pytest.mark.parametrize("display_only", [False, True])
async def test_browsing_search_filters_beyond_old_cap_before_offset(display_only):
    database_rows = []
    sources = []
    matching_ids = []
    for index in range(203):
        version_id = uuid4()
        frame = "Ordinary invented phrase" if index < 200 else "Late NEEDLE phrase"
        database_rows.append(
            (
                PhrasePattern(id=uuid4(), status="approved", current_version_id=version_id),
                Intent(code="TEST", name="Test"),
                PatternVersion(
                    id=version_id,
                    version_no=1,
                    canonical_frame=frame,
                    slots={},
                    epistemic_strength="low",
                    claim_type="descriptive",
                ),
                None,
                "MOVE",
            )
        )
        sources.append(
            (
                EvidenceProvenance(
                    pattern_version_id=version_id, source_type="authored", sentence_ids=[]
                ),
                None,
                None,
            )
        )
        if index >= 200:
            matching_ids.append(version_id)
    session = AsyncMock()
    session.execute.side_effect = [
        Mock(all=Mock(return_value=database_rows)),
        Mock(all=Mock(return_value=sources)),
    ]
    session.scalars.side_effect = [[], []]

    rows = await load_current_patterns(
        session, browse_query="needle", offset=1, limit=1, display_only=display_only
    )

    assert [row.current_version_id for row in rows] == [matching_ids[1]]
    # A SQL LIMIT here would hide the late matches before the in-memory predicate runs.
    statement = session.execute.await_args_list[0].args[0]
    assert statement._limit_clause is None
    assert statement._offset_clause is None


@pytest.mark.parametrize("display_only", [False, True])
async def test_association_groups_preserve_full_read_mapping_and_child_order(display_only):
    """Interleaved query rows must retain their per-version order and provenance rules."""
    version_ids = [uuid4() for _ in range(3)]
    pattern_ids = [uuid4() for _ in range(3)]
    article_id = uuid4()
    slots = {"X": {"type": "topic"}}
    database_rows = [
        (
            PhrasePattern(id=pattern_ids[index], status="approved", current_version_id=version_id),
            Intent(code="TEST", name="Test intent"),
            PatternVersion(
                id=version_id,
                version_no=index + 1,
                change_note="Reviewed" if index == 0 else None,
                canonical_frame="[X] suggests a link" if index == 0 else f"Frame {index}",
                slots=slots if index == 0 else {},
                epistemic_strength="moderate" if index == 0 else "unknown",
                claim_type="descriptive" if index == 0 else "unknown",
            ),
            UsageConstraint(
                pattern_version_id=version_id,
                evidence_min="single_study",
                forbidden_contexts=["DISCUSSION"],
                allowed_sections=["INTRO"],
                allowed_genres=["RESEARCH_ARTICLE"],
            )
            if index == 0
            else None,
            "MOVE",
        )
        for index, version_id in enumerate(version_ids)
    ]
    license_row = License(code="INTERNAL", name="Internal", allows_display=False)
    article = Article(id=article_id, doi="10.0000/invented")

    def source(version_index, source_type):
        return EvidenceProvenance(
            pattern_version_id=version_ids[version_index],
            source_type=source_type,
            article_id=article_id,
            sentence_ids=[uuid4()],
            source_sentence_count=17,
        )

    # Version 1 has two sources. Neither may be selected as its authoritative source.
    sources = [
        (source(1, "authored"), license_row, article),
        (source(0, "mined"), license_row, article),
        (source(1, "mined"), license_row, article),
    ]
    variants = [
        PhraseVariant(pattern_version_id=version_ids[0], text="First A", register="formal"),
        PhraseVariant(pattern_version_id=version_ids[1], text="First B", register=None),
        PhraseVariant(pattern_version_id=version_ids[0], text="Second A", register=None),
    ]
    affinities = [
        DisciplineAffinity(pattern_version_id=version_ids[1], discipline_code="A", score=0.1),
        DisciplineAffinity(pattern_version_id=version_ids[0], discipline_code="B", score=0.2),
        DisciplineAffinity(pattern_version_id=version_ids[1], discipline_code="C", score=0.3),
        DisciplineAffinity(pattern_version_id=version_ids[0], discipline_code="D", score=0.4),
    ]
    session = AsyncMock()
    session.execute.side_effect = [
        Mock(all=Mock(return_value=database_rows)),
        Mock(all=Mock(return_value=sources)),
    ]
    session.scalars.side_effect = [variants, affinities]

    rows = await load_current_patterns(
        session, display_only=display_only, internal_use_codes=frozenset({"INTERNAL"})
    )

    # Explicit full snapshots catch accidental field/mapping changes, not just grouping counts.
    expected = {
        "id": pattern_ids[0],
        "status": "approved",
        "intent_code": "TEST",
        "intent_name": "Test intent",
        "move_code": "MOVE",
        "current_version_id": version_ids[0],
        "version_no": 1,
        "change_note": "Reviewed",
        "canonical_frame": "{X} suggests a link",
        "slots": slots,
        "epistemic_strength": "moderate",
        "epistemic_strength_labelled": True,
        "claim_type": "descriptive",
        "claim_type_labelled": True,
        "variants": [
            {"text": "First A", "register": "formal"},
            {"text": "Second A", "register": None},
        ],
        "evidence_min": "single_study",
        "forbidden_contexts": ["DISCUSSION"],
        "allowed_sections": ["INTRO"],
        "allowed_genres": ["RESEARCH_ARTICLE"],
        "source_type": "mined",
        "license_code": "INTERNAL",
        "license_name": "Internal",
        "license_allows_display": False,
        "license_flag": True,
        "article_id": article_id,
        "source_reference": "10.0000/invented",
        "source_sentence_count": 17,
        "provenance_count": 1,
        "discipline_affinities": [
            {"discipline_code": "B", "score": 0.2},
            {"discipline_code": "D", "score": 0.4},
        ],
    }
    snapshots = [expected]
    if not display_only:
        empty = {
            **expected,
            "id": pattern_ids[2],
            "current_version_id": version_ids[2],
            "version_no": 3,
            "change_note": None,
            "canonical_frame": "Frame 2",
            "slots": {},
            "epistemic_strength": None,
            "epistemic_strength_labelled": False,
            "claim_type": None,
            "claim_type_labelled": False,
            "variants": [],
            "evidence_min": None,
            "forbidden_contexts": [],
            "allowed_sections": [],
            "allowed_genres": [],
            "source_type": "unknown",
            "license_code": None,
            "license_name": None,
            "license_flag": False,
            "article_id": None,
            "source_reference": None,
            "source_sentence_count": 0,
            "provenance_count": 0,
            "discipline_affinities": [],
        }
        multiple_sources = {
            **empty,
            "id": pattern_ids[1],
            "current_version_id": version_ids[1],
            "version_no": 2,
            "canonical_frame": "Frame 1",
            "variants": [{"text": "First B", "register": None}],
            "provenance_count": 2,
            "discipline_affinities": [
                {"discipline_code": "A", "score": 0.1},
                {"discipline_code": "C", "score": 0.3},
            ],
        }
        snapshots.extend([multiple_sources, empty])
    assert [asdict(row) for row in rows] == snapshots


@pytest.mark.parametrize("move", [None, "REPORT"])
@pytest.mark.parametrize("normalize_query,expected", [(True, "%suggest%"), (False, "%suggests%")])
async def test_move_join_always_selected_once_and_retrieval_normalization_is_opt_in(
    move, normalize_query, expected
):
    session = AsyncMock()
    session.execute.return_value = Mock(all=Mock(return_value=[]))
    assert (
        await load_current_patterns(
            session, move_code=move, query="suggests", normalize_query=normalize_query
        )
        == []
    )
    statement = session.execute.await_args.args[0]
    compiled = statement.compile()
    sql = str(compiled)
    assert sql.count("JOIN steps") == 1
    assert sql.count("JOIN moves") == 1
    assert "moves.code" in sql.split("FROM")[0]
    assert expected in compiled.params.values()
