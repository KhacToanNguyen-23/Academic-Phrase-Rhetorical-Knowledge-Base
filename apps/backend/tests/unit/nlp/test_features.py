"""TODO(owner, FR-06.2): spike only; not wired into ingest or mining."""

import json

from aprkb.nlp.features import FEATURES_SCHEMA_VERSION, SentenceAnalysis, TokenFeature


def _analysis() -> SentenceAnalysis:
    return SentenceAnalysis(
        char_start=4,
        char_end=9,
        tokens=(
            TokenFeature(0, 0, 4, "NOUN", "NN", "ROOT", 0, "test", "", False),
            TokenFeature(1, 4, 5, "PUNCT", ".", "punct", 0, ".", "", False),
        ),
    )


def test_sentence_analysis_has_lossless_json_round_trip() -> None:
    original = _analysis()
    encoded = json.dumps(original.to_json(), ensure_ascii=False)
    assert SentenceAnalysis.from_json(encoded) == original


def test_sentence_analysis_converts_to_existing_sentence_span() -> None:
    analysis = _analysis()
    span = analysis.to_sentence_span("xxx test. tail")
    assert span.text == "test."
    assert span.char_start == 4
    assert span.char_end == 9


def test_sentence_analysis_contains_schema_version() -> None:
    assert _analysis().to_json()["schema_version"] == FEATURES_SCHEMA_VERSION == 1
