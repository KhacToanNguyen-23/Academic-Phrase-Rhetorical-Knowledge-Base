"""Manifest errors must be rejected before database work."""

import json
from unittest.mock import AsyncMock

import pytest

from aprkb.modules.phrasebank.service import initialize_phrasebank


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": "2"},
        {"unknown": "field"},
        {"pattern_pack": "../outside"},
        {"reference_library": "../outside.json"},
        {"reference_mappings": "../outside.yaml"},
        {"pattern_pack": ""},
    ],
)
async def test_invalid_manifest_does_not_touch_database(tmp_path, change):
    document = {
        "schema_version": "1",
        "pattern_pack": "patterns",
        "reference_library": "collection.json",
        "reference_mappings": "mappings.yaml",
        **change,
    }
    path = tmp_path / "data_init.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    session = AsyncMock()

    with pytest.raises(ValueError):
        await initialize_phrasebank(session, path)

    session.execute.assert_not_called()
    session.get.assert_not_called()
    session.commit.assert_not_awaited()


async def test_absolute_path_is_not_a_portable_manifest_input(tmp_path):
    path = tmp_path / "data_init.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "pattern_pack": str(tmp_path.resolve()),
                "reference_library": "collection.json",
                "reference_mappings": "mappings.yaml",
            }
        ),
        encoding="utf-8",
    )
    session = AsyncMock()
    with pytest.raises(ValueError, match="inside the manifest directory"):
        await initialize_phrasebank(session, path)
    session.commit.assert_not_awaited()
