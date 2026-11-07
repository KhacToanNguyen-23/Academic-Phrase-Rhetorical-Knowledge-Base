"""Authored family fixtures and strict Tier 1 fallback behavior."""

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml

from aprkb.modules.mining.candidate_writer import CandidateDraft, CandidateWriter
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.modules.mining.stages.clusterer import Clusterer
from aprkb.modules.mining.stages.construction_matcher import (
    ConstructionMatcher,
    ReportingWithConstruction,
)
from aprkb.modules.mining.stages.hybrid_slot_engine import (
    HybridSlotEngine,
    _balance_parentheses,
    _drop_dangling_tail,
    _slot_cuts_modifier,
    _symbolic_slot,
    _unbalanced_slot,
)
from aprkb.modules.mining.stages.slot_abstractor import SlotAbstractor
from aprkb.nlp.features import SentenceAnalysis, TokenFeature
from aprkb.nlp.syntax import normalized_children_by_head, select_syntax_root
from aprkb.policies.loader import load_policy_bundle
from aprkb.policies.schemas import is_safe_hybrid_frame

_ROOT = Path(__file__).parents[2]
_FIXTURES = _ROOT / "fixtures" / "nlp_spike"
_PAYLOAD = yaml.safe_load((_FIXTURES / "sentences.yaml").read_text(encoding="utf-8"))
_SNAPSHOT = json.loads((_FIXTURES / "token_snapshots.json").read_text(encoding="utf-8"))
_ANALYSES = {case["text"]: case["analysis"] for case in _SNAPSHOT["cases"]}
_FAMILIES = {
    "hybrid_passive_academic": ((0, 1, 2), (3, 4, 5)),
    "hybrid_extraposed_it": ((6, 7, 8), (9, 10, 11)),
    "hybrid_copular_definitional": ((12, 13, 42), (15, 16, 17)),
    "hybrid_discourse_gap": ((18, 19, 20), (21, 22, 23)),
    "hybrid_participial_lead_in": ((24, 25, 26), (27, 28, 29)),
    "hybrid_comparative_correlation": ((30, 31, 32), (33, 34, 35)),
    "hybrid_reporting_spine": ((36, 37, 38), (39, 40, 41)),
    "hybrid_active_modified": ((51, 52, 53), (54, 55, 56)),
}
_EXPECTED_FRAMES = {
    0: "[X] were consistently and carefully preprocessed using [Y].",
    6: "It is practically necessary to inspect [X].",
    12: "The most important methodological limitation of [X] is [Y].",
    18: "However, remarkably little attention has been paid to [X].",
    24: "Motivated by [X], [Y] therefore propose [Z].",
    30: "[X] consistently and significantly outperforms [Y] in retrieval accuracy.",
    36: "[X] reveals that [Y].",
}


def _hybrid_policy(*, enable_all: bool = True):  # type: ignore[no-untyped-def]
    """Family logic is tested with every family on; the shipped policy may disable some."""
    # Authored family fixtures keep literal nouns; the noun gate has its own test.
    hybrid = load_policy_bundle().hybrid_constructions.model_copy(
        update={"max_literal_nouns": 99, "min_fixed_content_tokens": 1}
    )
    if enable_all:
        hybrid = hybrid.model_copy(
            update={"families": [f.model_copy(update={"enabled": True}) for f in hybrid.families]}
        )
    return hybrid


def _engine(*, enable_all: bool = True) -> HybridSlotEngine:
    policy = load_policy_bundle()
    return HybridSlotEngine(
        _hybrid_policy(enable_all=enable_all),
        policy.reporting_verbs,
        policy.slot_abstraction,
        policy.lead_ins.lead_ins,
    )


def _item(index: int) -> MiningItem:
    text = _PAYLOAD["hybrid_cases"][index]
    analysis = SentenceAnalysis.from_json(_ANALYSES[text])
    return MiningItem(
        text=text,
        source_sentence_ids=[uuid4()],
        tokens=analysis.tokens,
    )


@pytest.mark.parametrize(
    ("family", "index"),
    [(family, index) for family, (positive, _) in _FAMILIES.items() for index in positive],
)
def test_positive_authored_fixture_matches_its_family(family: str, index: int) -> None:
    policy = _hybrid_policy()
    result = _engine().match_item(_item(index))
    assert result is not None
    assert result.construction_id == family
    assert result.construction_version == policy.version
    source = _item(index).text
    rebuilt = source
    for name, (start, end) in sorted(
        result.occurrences[0].slot_spans.items(),
        key=lambda entry: entry[1],
        reverse=True,
    ):
        rebuilt = rebuilt[:start] + f"[{name}]" + rebuilt[end:]
    assert result.text in rebuilt  # the frame is a contiguous core of the source
    if index in _EXPECTED_FRAMES:
        assert result.text == _EXPECTED_FRAMES[index]
    assert is_safe_hybrid_frame(
        result.text, policy, f"construction={family}:{policy.version}:" + "a" * 64
    )


@pytest.mark.parametrize(
    ("family", "index"),
    [(family, index) for family, (_, negative) in _FAMILIES.items() for index in negative],
)
def test_negative_authored_fixture_does_not_match_named_family(family: str, index: int) -> None:
    engine = _engine()
    item = _item(index)
    assert item.tokens is not None
    selection = select_syntax_root(item.tokens)
    assert selection is not None
    assert (
        engine._match_family(
            family,
            item.text,
            item.tokens,
            normalized_children_by_head(item.tokens),
            selection.token.i,
        )
        is None
    )


def test_tier1_output_is_final_and_hybrid_only_runs_after_double_miss() -> None:
    policy = load_policy_bundle()

    class SpyHybrid:
        def __init__(self) -> None:
            self.calls: list[MiningItem] = []

        def match_item(self, item: MiningItem) -> None:
            self.calls.append(item)
            return None

    reporting = SlotAbstractor(
        policy.reporting_verbs, policy.slot_abstraction, policy.lead_ins.lead_ins
    )
    constructions = ConstructionMatcher(
        policy.constructions,
        policy.slot_abstraction,
        policy.construction_verb_groups,
    )
    spy = SpyHybrid()
    stage = ReportingWithConstruction(reporting, constructions, spy)  # type: ignore[arg-type]

    tier1_text = "These results suggest that the method is robust to noise."
    tier1_tokens = next(SentenceAnalysis.from_json(_ANALYSES[tier1_text]).tokens for _ in (0,))
    tier1 = MiningItem(text=tier1_text, source_sentence_ids=[uuid4()], tokens=tier1_tokens)
    assert stage.process([tier1])[0].text == reporting.process([tier1])[0].text
    assert spy.calls == []

    hybrid_miss = _item(0)
    assert stage.process([hybrid_miss]) == []
    assert spy.calls == [hybrid_miss]

    no_tokens = MiningItem(text="No matching family exists here.", source_sentence_ids=[uuid4()])
    assert stage.process([no_tokens]) == []
    assert spy.calls == [hybrid_miss]


def test_hybrid_safety_rejects_unknown_ids_adjacent_slots_and_sensitive_literals() -> None:
    policy = load_policy_bundle().hybrid_constructions
    assert not is_safe_hybrid_frame(
        "[X] reveals [Y].", policy, "construction=unknown_family:0.9.1:key"
    )
    assert not is_safe_hybrid_frame(
        "[X][Y] reveals. ", policy, "construction=hybrid_passive_academic:0.9.1:key"
    )
    assert not is_safe_hybrid_frame(
        "Samples from 2020 were processed using [X].",
        policy,
        "construction=hybrid_passive_academic:0.9.1:key",
    )
    valid_prefix = "construction=hybrid_passive_academic:0.9.1:"
    digest = "a" * 64
    assert is_safe_hybrid_frame("[X] reveals [Y].", policy, valid_prefix + digest)
    assert not is_safe_hybrid_frame("[X] reveals [Y].", policy, valid_prefix + "old:" + digest)
    assert not is_safe_hybrid_frame(
        "[X] reveals [Y].", policy, "construction=hybrid_passive_academic:0.1.0:" + digest
    )


def test_participial_ownership_uses_the_dependency_subject() -> None:
    item = _item(24)
    result = _engine().match_item(item)
    assert result is not None
    assert (
        result.ownership.value == "unclear"
    )  # “earlier failures” would be prior; subject “researchers” is unclear.


def test_meta_np_complement_keeps_its_attached_relative_clause() -> None:
    item = _item(43)
    assert item.tokens is not None
    selection = select_syntax_root(item.tokens)
    assert selection is not None
    spans = _engine()._match_family(
        "hybrid_copular_definitional",
        item.text,
        item.tokens,
        normalized_children_by_head(item.tokens),
        selection.token.i,
    )
    assert spans is not None
    start, end = spans["X"]
    assert item.text[start:end] == "the method, which the team carefully evaluated"


def test_candidate_writer_and_review_rechecks_accept_known_hybrid_frames() -> None:
    from aprkb.modules.extraction.service import _is_safe as extraction_is_safe
    from aprkb.modules.review.service import _candidate_is_safe_to_promote

    policies = load_policy_bundle()
    extracted = _engine().match_item(_item(0))
    assert extracted is not None
    clustered = Clusterer(policies).process([extracted])[0]
    assert clustered.cluster_key is not None

    class Sink:
        draft: CandidateDraft | None = None

        def create_candidate(self, draft: CandidateDraft) -> object:
            self.draft = draft
            return draft

    sink = Sink()
    writer = CandidateWriter(
        sink,
        reporting_policy=policies.reporting_verbs,
        constructions_policy=policies.constructions,
        verb_group_policy=policies.construction_verb_groups,
        lead_ins_policy=policies.lead_ins,
        hybrid_policy=policies.hybrid_constructions,
    )
    draft = CandidateDraft(
        canonical_frame=clustered.text,
        source_sentence_ids=clustered.source_sentence_ids,
        slots=clustered.slots,
        cluster_key=clustered.cluster_key,
        construction_id=clustered.construction_id,
    )
    written = writer.write(draft)
    assert written is sink.draft
    assert sink.draft is not None
    assert sink.draft.canonical_frame == draft.canonical_frame

    candidate = SimpleNamespace(
        canonical_frame=clustered.text,
        cluster_key=clustered.cluster_key,
        slots={name: slot.model_dump(mode="json") for name, slot in clustered.slots.items()},
    )
    assert _candidate_is_safe_to_promote(candidate)
    assert extraction_is_safe(candidate)
    candidate.cluster_key = "construction=unregistered_hybrid:0.9.1:fixture"
    assert not _candidate_is_safe_to_promote(candidate)
    assert not extraction_is_safe(candidate)


# Round 1 frame-core fixtures (self-authored): indices follow the hybrid_cases list.
_CORE_FRAMES = {
    44: "[X] were preprocessed using [Y]",
    45: "[X] were preprocessed using [Y].",
    46: "However, [X] were preprocessed using [Y].",
}


@pytest.mark.parametrize(("index", "expected"), sorted(_CORE_FRAMES.items()))
def test_frame_keeps_the_pattern_core_not_the_whole_sentence(index: int, expected: str) -> None:
    result = _engine().match_item(_item(index))
    assert result is not None
    assert result.text == expected
    assert result.construction_id == "hybrid_passive_academic"
    policy = load_policy_bundle().hybrid_constructions
    assert is_safe_hybrid_frame(
        result.text, policy, f"construction={result.construction_id}:{policy.version}:" + "a" * 64
    )


def test_slot_made_only_of_function_words_is_rejected() -> None:
    engine = _engine()
    assert engine.match_item(_item(47)) is None
    assert engine.rejection_counts["purity_empty_slot"] >= 1


def test_family_trigger_word_must_survive_trimming() -> None:
    engine = _engine()
    result = engine.match_item(_item(48))
    # The active-clause family may legitimately take this sentence; the gap family must not.
    assert result is None or result.construction_id != "hybrid_discourse_gap"
    assert engine.rejection_counts["trigger_outside_core"] >= 1


def test_hybrid_safety_rejects_long_clause_joined_and_bracketed_frames() -> None:
    policy = load_policy_bundle().hybrid_constructions
    key = f"construction=hybrid_passive_academic:{policy.version}:" + "a" * 64
    assert is_safe_hybrid_frame("[X] were preprocessed using [Y]", policy, key)
    too_long = "[X] " + " ".join(["word"] * (policy.max_literal_words + 1)) + " [Y]"
    assert not is_safe_hybrid_frame(too_long, policy, key)
    assert not is_safe_hybrid_frame("[X] were preprocessed; [Y] followed", policy, key)
    assert not is_safe_hybrid_frame("[X]] were preprocessed using [Y]", policy, key)


def test_agent_is_never_taken_from_inside_the_subject() -> None:
    result = _engine().match_item(_item(49))
    assert result is not None
    assert result.construction_id == "hybrid_passive_academic"
    assert result.text == "[X] was measured using [Y]."


def test_comparative_trigger_inside_a_slot_does_not_count() -> None:
    engine = _engine()
    assert engine.match_item(_item(50)) is None
    assert engine.rejection_counts["trigger_outside_core"] >= 1


def test_active_modified_frames_keep_their_modifier() -> None:
    engine = _engine()
    assert engine.match_item(_item(51)).text == "[X] significantly improves [Y]."  # type: ignore[union-attr]


def test_hybrid_safety_rejects_punctuation_glued_to_a_slot() -> None:
    policy = load_policy_bundle().hybrid_constructions
    key = f"construction=hybrid_active_modified:{policy.version}:" + "a" * 64
    assert is_safe_hybrid_frame("[X] selects [Y] within [Z].", policy, key)
    assert not is_safe_hybrid_frame("[X] selects per-iteration,[Y] within [Z]", policy, key)
    assert not is_safe_hybrid_frame("[X] reduces time-to-[Y] efficiency", policy, key)
    assert not is_safe_hybrid_frame("[X] uses [Y]ing within [Z]", policy, key)


def test_disabled_family_is_not_mined_and_its_frames_are_not_accepted() -> None:
    policy = load_policy_bundle().hybrid_constructions
    assert not next(f for f in policy.families if f.id == "hybrid_discourse_gap").enabled
    shipped = _engine(enable_all=False)
    result = shipped.match_item(_item(18))
    assert result is None or result.construction_id != "hybrid_discourse_gap"
    key = f"construction=hybrid_discourse_gap:{policy.version}:" + "a" * 64
    assert not is_safe_hybrid_frame("However, little attention has been paid to [X].", policy, key)
    assert _engine().match_item(_item(18)) is not None  # the family logic itself still works


def _tail_tokens(text: str, tagged: list[tuple[str, str, str, str]]) -> tuple[TokenFeature, ...]:
    tokens = []
    cursor = 0
    for index, (surface, pos, tag, dep) in enumerate(tagged):
        start = text.index(surface, cursor)
        cursor = start + len(surface)
        tokens.append(
            TokenFeature(index, start, cursor, pos, tag, dep, 0, surface.lower(), "", False)
        )
    return tuple(tokens)


def test_trailing_prepositions_are_cut_back_to_the_last_kept_word() -> None:
    text = "It improves accuracy, by"
    tokens = _tail_tokens(
        text,
        [
            ("It", "PRON", "PRP", "nsubj"),
            ("improves", "VERB", "VBZ", "ROOT"),
            ("accuracy", "NOUN", "NN", "dobj"),
            (",", "PUNCT", ",", "punct"),
            ("by", "ADP", "IN", "prep"),
        ],
    )
    assert text[: _drop_dangling_tail(text, tokens, 20, len(text))] == "It improves accuracy"


def test_two_word_prepositions_are_cut_together() -> None:
    text = "It fails due to"
    tokens = _tail_tokens(
        text,
        [
            ("It", "PRON", "PRP", "nsubj"),
            ("fails", "VERB", "VBZ", "ROOT"),
            ("due", "ADP", "IN", "prep"),
            ("to", "ADP", "IN", "pcomp"),
        ],
    )
    assert text[: _drop_dangling_tail(text, tokens, 8, len(text))] == "It fails"


def test_verb_particles_and_material_inside_the_floor_are_kept() -> None:
    text = "It was carried out"
    tokens = _tail_tokens(
        text,
        [
            ("It", "PRON", "PRP", "nsubjpass"),
            ("was", "AUX", "VBD", "auxpass"),
            ("carried", "VERB", "VBN", "ROOT"),
            ("out", "ADP", "IN", "prt"),
        ],
    )
    assert _drop_dangling_tail(text, tokens, 14, len(text)) == len(text)
    text = "It relies on"
    tokens = _tail_tokens(
        text,
        [
            ("It", "PRON", "PRP", "nsubj"),
            ("relies", "VERB", "VBZ", "ROOT"),
            ("on", "ADP", "IN", "prep"),
        ],
    )
    assert _drop_dangling_tail(text, tokens, len(text), len(text)) == len(text)


def test_final_period_stays_visible_but_out_of_the_cluster_material() -> None:
    result = _engine().match_item(_item(0))
    assert result is not None
    assert result.text.endswith(".")
    assert result.canonical_skeleton is not None
    assert not result.canonical_skeleton.endswith(".")


@pytest.mark.parametrize(
    "text",
    ["= e -b", "x \N{LESS-THAN OR EQUAL TO} 3", "\N{MATHEMATICAL ITALIC SMALL E} value"],
)
def test_formula_slots_are_symbolic(text: str) -> None:
    assert _symbolic_slot(text)


@pytest.mark.parametrize(
    "text", ["the proposed filter", "CNN+LSTM", "128 \N{MULTIPLICATION SIGN} 128"]
)
def test_ordinary_slots_are_not_symbolic(text: str) -> None:
    assert not _symbolic_slot(text)


@pytest.mark.parametrize(
    "frame",
    [
        "[X] achieves [Y] by",
        "[X] achieves [Y] by.",
        "[X] avoids [Y] due",
        "[X] , then reveals [Y].",
        "[X] reveals [Y] , then improves [Z].",
        "[X] encourages [Y] to balance costs, e.g.",
        "[X] reveals [Y], i.e., another result.",
    ],
)
def test_safety_rejects_dangling_spaced_and_abbreviated_frames(frame: str) -> None:
    policy = load_policy_bundle().hybrid_constructions
    key = "construction=hybrid_passive_academic:0.9.1:" + "a" * 64
    assert not is_safe_hybrid_frame(frame, policy, key)


def test_literal_noun_gate_uses_the_shipped_policy() -> None:
    policy = load_policy_bundle()
    engine = HybridSlotEngine(
        policy.hybrid_constructions,
        policy.reporting_verbs,
        policy.slot_abstraction,
        policy.lead_ins.lead_ins,
    )
    # Topic nouns left in literal text block frames; the relaxed test policy keeps them.
    shipped = sum(
        engine.match_item(_item(i)) is not None for i in range(len(_PAYLOAD["hybrid_cases"]))
    )
    relaxed_engine = _engine()
    relaxed = sum(
        relaxed_engine.match_item(_item(i)) is not None
        for i in range(len(_PAYLOAD["hybrid_cases"]))
    )
    assert shipped < relaxed
    assert engine.rejection_counts["purity_literal_noun"] >= 1
    # Meta-NP heads stay allowed, so a definitional frame survives.
    assert engine.match_item(_item(12)) is not None


def test_fronted_slot_is_named_by_reading_order_and_passes_the_writer_check() -> None:
    policy = _hybrid_policy()
    index = _PAYLOAD["hybrid_cases"].index("In the proposed design, the samples are stored.")
    result = _engine().match_item(_item(index))
    assert result is not None
    assert result.text.startswith("In [X], [Y] ")
    key = f"construction={result.construction_id}:{policy.version}:" + "a" * 64
    assert is_safe_hybrid_frame(result.text, policy, key)


@pytest.mark.parametrize(
    ("family", "index"),
    [(family, index) for family, (positive, _) in _FAMILIES.items() for index in positive],
)
def test_every_positive_fixture_passes_the_writer_safety_check(family: str, index: int) -> None:
    policy = _hybrid_policy()
    result = _engine().match_item(_item(index))
    assert result is not None
    key = f"construction={family}:{policy.version}:" + "a" * 64
    assert is_safe_hybrid_frame(result.text, policy, key)


@pytest.mark.parametrize("lead", ["For example", "In contrast", "In this paper"])
def test_approved_fixed_lead_remains_literal(lead: str) -> None:
    text = f"{lead}, the proposed models are evaluated using controlled inputs."
    index = _PAYLOAD["hybrid_cases"].index(text)
    result = _engine().match_item(_item(index))
    assert result is not None
    assert result.text.startswith(f"{lead}, [X]")
    assert f"{lead} [X]" not in result.text


def test_hybrid_rejects_capitalized_sentence_join_after_a_slot() -> None:
    text = "The method is useful As discussed in earlier work."
    item = _item(_PAYLOAD["hybrid_cases"].index(text))
    assert item.tokens is not None
    root = select_syntax_root(item.tokens)
    assert root is not None
    engine = _engine()
    result = engine._build(
        item,
        "hybrid_copular_definitional",
        {
            "X": (0, text.index("method") + len("method")),
            "Y": (text.index("earlier"), text.index("work") + len("work")),
        },
        root.token.i,
        normalized_children_by_head(item.tokens),
    )
    assert result is None
    assert engine.rejection_counts["purity_heading_join"] == 1


def test_hybrid_requires_policy_minimum_fixed_content() -> None:
    policies = load_policy_bundle()
    # The shipped value is 1 (owner decision 2026-11-07: 2 removed 7 of 11 GOOD frames).
    # The mechanism is checked with an explicit stricter value.
    assert policies.hybrid_constructions.min_fixed_content_tokens == 1
    strict = policies.hybrid_constructions.model_copy(update={"min_fixed_content_tokens": 2})
    engine = HybridSlotEngine(
        strict,
        policies.reporting_verbs,
        policies.slot_abstraction,
        policies.lead_ins.lead_ins,
    )
    text = "Samples were measured by teams."
    assert engine.match_item(_item(_PAYLOAD["hybrid_cases"].index(text))) is None
    assert engine.rejection_counts["purity_content_minimum"] == 1


def test_slot_boundary_cannot_separate_modifier_from_its_head() -> None:
    tokens = (
        TokenFeature(0, 0, 4, "ADJ", "JJ", "amod", 1, "near", "", False),
        TokenFeature(1, 5, 11, "NOUN", "NN", "ROOT", 1, "privacy", "", False),
    )
    assert _slot_cuts_modifier(tokens, [("X", (5, 11))])


# Hedging and limitation phrasing handled inside the existing families (policy v0.9.0).
_CLOSED_VERB_FRAMES = {
    "The proposed method fails to handle missing labels.": "[X] fails to handle [Y].",
    "The baseline tends to overfit.": "[X] tends to [Y].",
    "This approach suffers from high latency.": "[X] suffers from [Y].",
    "The gap stems from limited supervision.": "[X] stems from [Y].",
    "It is unclear whether the effect generalizes.": "It is unclear whether [X].",
    "It is impractical to scale the pipeline.": "It is impractical to scale [X].",
    "Another drawback is that training is slow.": "Another drawback is that [X].",
}


@pytest.mark.parametrize(("text", "frame"), list(_CLOSED_VERB_FRAMES.items()))
def test_closed_verb_and_limitation_frames(text: str, frame: str) -> None:
    policy = load_policy_bundle()
    engine = HybridSlotEngine(
        policy.hybrid_constructions,
        policy.reporting_verbs,
        policy.slot_abstraction,
        policy.lead_ins.lead_ins,
    )
    result = engine.match_item(_item(_PAYLOAD["hybrid_cases"].index(text)))
    assert result is not None
    assert result.text == frame
    key = f"construction={result.construction_id}:{policy.hybrid_constructions.version}:" + "a" * 64
    assert is_safe_hybrid_frame(result.text, policy.hybrid_constructions, key)


@pytest.mark.parametrize(
    "text", ["The method suffers.", "The learner succeeds in reducing latency."]
)
def test_closed_verb_frames_need_their_structure(text: str) -> None:
    policy = load_policy_bundle()
    engine = HybridSlotEngine(
        policy.hybrid_constructions,
        policy.reporting_verbs,
        policy.slot_abstraction,
        policy.lead_ins.lead_ins,
    )
    assert engine.match_item(_item(_PAYLOAD["hybrid_cases"].index(text))) is None


def test_slot_with_a_lone_parenthesis_is_unbalanced() -> None:
    assert _unbalanced_slot("the condition (20")
    assert _unbalanced_slot("Table 2)")
    assert not _unbalanced_slot("the condition (see Eq. 2)")
    assert not _unbalanced_slot("a plain noun phrase")


# Policy v0.9.1: worth + V-ing, idioms, goal clauses, fragments, parenthesis balance.
_V091_FRAMES = {
    "It is worth noting that the method generalizes.": "It is worth noting that [X].",
    "It is worth summarizing the results.": "It is worth summarizing [X].",
    "The proposed design sheds light on resource limits.": "[X] sheds light on [Y].",
    "The study provides insights into user behavior.": "[X] provides insights into [Y].",
    "Careful tuning plays a key role in stable training.": "[X] plays a key role in [Y].",
    "The scheduler serves as a coordinator.": "[X] serves as [Y].",
    "The goal of this work is to improve robustness.": "The goal of [X] is to [Y].",
    "Our goal is to reduce latency.": "Our goal is to [X].",
}


def _shipped_engine() -> tuple[HybridSlotEngine, str]:
    policy = load_policy_bundle()
    engine = HybridSlotEngine(
        policy.hybrid_constructions,
        policy.reporting_verbs,
        policy.slot_abstraction,
        policy.lead_ins.lead_ins,
    )
    return engine, policy.hybrid_constructions.version


@pytest.mark.parametrize(("text", "frame"), list(_V091_FRAMES.items()))
def test_v091_frames(text: str, frame: str) -> None:
    engine, version = _shipped_engine()
    result = engine.match_item(_item(_PAYLOAD["hybrid_cases"].index(text)))
    assert result is not None
    assert result.text == frame
    policy = load_policy_bundle().hybrid_constructions
    key = f"construction={result.construction_id}:{version}:" + "a" * 64
    assert is_safe_hybrid_frame(result.text, policy, key)


def test_referential_it_with_a_gerund_is_not_an_extraposed_pattern() -> None:
    engine, _ = _shipped_engine()
    text = "It was busy modelling the system."
    assert engine.match_item(_item(_PAYLOAD["hybrid_cases"].index(text))) is None


def test_subordinate_clause_without_a_main_clause_is_rejected() -> None:
    engine, _ = _shipped_engine()
    text = "Although the method works."
    assert engine.match_item(_item(_PAYLOAD["hybrid_cases"].index(text))) is None
    assert engine.rejection_counts["subordinate_fragment"] == 1


def test_idiom_noun_does_not_become_a_slot() -> None:
    engine, _ = _shipped_engine()
    text = "The proposed design sheds light on resource limits."
    result = engine.match_item(_item(_PAYLOAD["hybrid_cases"].index(text)))
    assert result is not None
    assert "light" in result.text
    assert result.text.count("[") == 2


def test_closing_parenthesis_stays_with_its_slot() -> None:
    text = "the condition (20). Next"
    assert _balance_parentheses(text, (0, 17)) == (0, 18)
    text = "a term (i.i.d.) here"
    assert _balance_parentheses(text, (0, 13)) == (0, 15)
    assert _balance_parentheses("no brackets", (0, 5)) == (0, 5)
    assert _balance_parentheses("x (y z", (0, 6)) == (0, 6)
