"""Read-time compatibility for invented mined-style frames."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from aprkb.modules.composition.renderer import render_frame
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
