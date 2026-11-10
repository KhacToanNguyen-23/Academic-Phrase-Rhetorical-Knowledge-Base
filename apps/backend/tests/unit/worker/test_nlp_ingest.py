"""Ingest selects NLP engines explicitly and keeps regex dependency-free."""

from aprkb.core.config import settings
from aprkb.modules.mining.stages.epistemic_scorer import EpistemicScorer
from aprkb.nlp import FEATURES_SCHEMA_VERSION, SpacyEngine
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


def test_spacy_selection_falls_back_when_model_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(settings, "nlp_engine", "spacy")
    monkeypatch.setattr(settings, "nlp_model", "en_core_web_sm_missing_for_test")
    handlers._SPACY_ENGINES.clear()
    runtime = handlers.WorkerNlpRuntime(
        spacy_engine=None,
        epistemic_scorer=EpistemicScorer(load_policy_bundle().epistemic_scoring),
    )

    info, analyse = handlers._build_section_analyser(load_policy_bundle(), runtime)

    assert info.engine == "regex"
    assert [row[0] for row in analyse("One sentence. Two sentences.")] == [
        "One sentence.",
        "Two sentences.",
    ]


def test_worker_nlp_runtime_keeps_scorer_when_spacy_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        handlers,
        "_get_spacy_engine",
        lambda _model: (_ for _ in ()).throw(RuntimeError("model unavailable")),
    )

    runtime = handlers.initialize_worker_nlp_runtime(load_policy_bundle())

    assert runtime.spacy_engine is None
    assert runtime.epistemic_scorer is not None


def test_worker_nlp_runtime_loads_spacy_once_at_boot(monkeypatch) -> None:
    calls: list[str] = []
    engine = object()

    def get_engine(model_name: str):
        calls.append(model_name)
        return engine

    monkeypatch.setattr(handlers, "_get_spacy_engine", get_engine)

    runtime = handlers.initialize_worker_nlp_runtime(load_policy_bundle())

    assert runtime.spacy_engine is engine
    assert runtime.epistemic_scorer is not None
    assert calls == [settings.nlp_model]


def test_spacy_doc_reaches_the_compositional_scorer() -> None:
    import pytest

    pytest.importorskip("spacy")
    pytest.importorskip("en_core_web_sm")

    engine = SpacyEngine()
    scorer = EpistemicScorer(load_policy_bundle().epistemic_scoring)

    result = scorer.score(engine.parse("The results conclusively prove the claim."))

    assert (result.label, result.score) == ("absolute", 4.5)
