"""Read-time compatibility for invented mined-style frames."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from aprkb.modules.composition.renderer import render_frame
from aprkb.modules.corpus.models import License
from aprkb.modules.patterns.models import EvidenceProvenance, PatternVersion, PhrasePattern
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
        Mock(all=Mock(return_value=[(pattern, Intent(code="TEST", name="Test"), version, None)])),
        Mock(all=Mock(return_value=[(source, None, None)])),
    ]
    session.scalars.side_effect = [[], []]

    rows = await load_current_patterns(session)

    assert len(rows) == 1
    assert rows[0].as_response()["source_sentence_count"] == expected


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
        Mock(all=Mock(return_value=[(pattern, Intent(code="TEST", name="Test"), version, None)])),
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
