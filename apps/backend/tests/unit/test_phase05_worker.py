"""Phase 05 tests are written before the ingestion and worker implementation."""

from pathlib import Path

import pytest

from aprkb.modules.corpus.blobstore import LocalBlobStore
from aprkb.modules.corpus.sentence_splitter import split_sentences


def test_local_blob_store_round_trip_and_rejects_unsafe_keys(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path)
    key = "articles/0123456789abcdef0123456789abcdef.txt"

    store.put(key, b"A minimal article.")

    assert store.get(key) == b"A minimal article."
    with pytest.raises(ValueError):
        store.put("../outside.txt", b"unsafe")
    store.delete(key)
    assert not (tmp_path / key).exists()


def test_sentence_splitter_preserves_original_character_offsets() -> None:
    source = "  First sentence.\nSecond sentence has Ω.  "

    spans = split_sentences(source)

    assert [(span.text, span.char_start, span.char_end) for span in spans] == [
        ("First sentence.", 2, 17),
        ("Second sentence has Ω.", 18, 40),
    ]
    assert all(source[span.char_start : span.char_end] == span.text for span in spans)
