"""Ingest selects NLP engines explicitly and keeps regex dependency-free."""

import pytest

from aprkb.core.config import settings
from aprkb.nlp import FEATURES_SCHEMA_VERSION
from aprkb.policies.loader import load_policy_bundle
from aprkb.worker import handlers


def test_regex_is_the_default_and_stores_no_token_features(monkeypatch) -> None:
    monkeypatch.setattr(settings, "nlp_engine", "regex")
    info, analyse = handlers._build_section_analyser(load_policy_bundle())

    rows = analyse("First sentence. Second sentence.")

    assert info.engine == "regex"
    assert info.boundary_policy_version == "0.1.0"
    assert [row[0] for row in rows] == ["First sentence.", "Second sentence."]
    assert all(row[3] is None for row in rows)
    assert FEATURES_SCHEMA_VERSION == 1


def test_spacy_selection_fails_clearly_when_model_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(settings, "nlp_engine", "spacy")
    monkeypatch.setattr(settings, "nlp_model", "en_core_web_sm_missing_for_test")
    handlers._SPACY_ENGINES.clear()

    with pytest.raises(RuntimeError, match="NLP_ENGINE=spacy requires spaCy and model"):
        handlers._build_section_analyser(load_policy_bundle())
