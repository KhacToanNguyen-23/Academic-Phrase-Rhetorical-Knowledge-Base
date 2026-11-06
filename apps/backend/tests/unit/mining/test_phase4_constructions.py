"""Phase-4 construction matching and safety regressions on spaCy-free snapshots."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from aprkb.modules.mining.candidate_writer import CandidateDraft, CandidateWriter
from aprkb.modules.mining.pipeline import MiningPipeline
from aprkb.modules.mining.schemas import SlotDefinition, SlotType
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.modules.mining.stages.construction_matcher import (
    ConstructionMatcher,
    ReportingWithConstruction,
    match_construction,
)
from aprkb.modules.mining.stages.slot_abstractor import SlotAbstractor
from aprkb.nlp.features import TokenFeature
from aprkb.policies.loader import load_policy_bundle
from aprkb.policies.schemas import (
    ConstructionChild,
    ConstructionRule,
    ConstructionsPolicy,
    is_safe_construction_frame,
)

_FIXTURE = Path(__file__).parents[2] / "fixtures" / "nlp_spike" / "token_snapshots.json"
_SNAPSHOT = json.loads(_FIXTURE.read_text(encoding="utf-8"))
_TOKENS = {
    case["text"]: tuple(TokenFeature.from_json(token) for token in case["analysis"]["tokens"])
    for case in _SNAPSHOT["cases"]
}
_LOCATOR = f"syntax:{_SNAPSHOT['model_name']}:{_SNAPSHOT['model_version']}"


def _item(text: str) -> MiningItem:
    return MiningItem(
        text=text,
        source_sentence_ids=[uuid4()],
        tokens=_TOKENS[text],
        locator=_LOCATOR,
    )


def _frame_from_slot_spans(text: str, spans: dict[str, tuple[int, int]]) -> str:
    parts: list[str] = []
    position = 0
    for name, (start, end) in sorted(spans.items(), key=lambda slot: slot[1][0]):
        parts.extend((text[position:start], f"[{name}]"))
        position = end
    parts.append(text[position:])
    return "".join(parts)


@pytest.mark.parametrize(
    ("text", "frame", "construction_id", "slot"),
    [
        (
            "In this study, we propose a compact method.",
            "In this study, we propose [X].",
            "author_action",
            "a compact method",
        ),
        (
            "Our method plays a key role in reliable retrieval.",
            "[X] plays a key role in [Y].",
            "relation_role",
            "reliable retrieval",
        ),
        (
            "The new method significantly improves classification accuracy.",
            "[X] significantly improves [Y] accuracy.",
            "performance",
            "classification",
        ),
    ],
)
def test_each_construction_extracts_masked_slots_through_full_pipeline(
    text: str, frame: str, construction_id: str, slot: str
) -> None:
    stages = build_stages(policy_bundle=load_policy_bundle())
    [result] = MiningPipeline(stages=stages).process([_item(text)])

    # Phase 8 retains the approved literal lead-in to satisfy the whole-sentence frame invariant.
    assert result.text == frame
    assert result.construction_id == construction_id
    assert f"construction={construction_id}:0.3.0:" in (result.cluster_key or "")
    assert any(text[start:end] == slot for start, end in result.occurrences[0].slot_spans.values())


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("We discuss a compact method.", "no_anchor"),
        ("We carefully propose a useful method today.", "unsupported_adjunct"),
        ("Our method does not improve classification accuracy.", "unmatched_content"),
    ],
)
def test_construction_matcher_rejects_unreviewed_forms(text: str, reason: str) -> None:
    # The rejection taxonomy names unsupported predicate dependents explicitly.
    policy = load_policy_bundle().constructions

    assert match_construction(_TOKENS[text], text, policy) == reason


def test_registry_frame_validation_rejects_injected_bracketed_text() -> None:
    policy = load_policy_bundle().constructions
    matcher = ConstructionMatcher(policy)

    assert matcher.match_item(_item("In this study, we propose a compact method.")) is not None
    assert is_safe_construction_frame("we propose [X].", policy)
    assert not is_safe_construction_frame("we propose [X] [injected].", policy)


def test_registry_frame_validation_uses_closed_verb_group_policy() -> None:
    bundle = load_policy_bundle()
    policy = bundle.constructions
    groups = bundle.construction_verb_groups

    assert is_safe_construction_frame("we also use [X].", policy, verb_group_policy=groups)
    assert is_safe_construction_frame("we will use [X].", policy, verb_group_policy=groups)
    assert is_safe_construction_frame("we use [X].", policy, verb_group_policy=groups)
    assert not is_safe_construction_frame(
        "we surprisingly use [X].", policy, verb_group_policy=groups
    )
    assert not is_safe_construction_frame(
        "we use [X] [injected].", policy, verb_group_policy=groups
    )


def test_verb_group_policy_contains_only_the_reviewed_phase81_candidates() -> None:
    policy = load_policy_bundle().construction_verb_groups

    assert policy.version == "0.1.0"
    assert set(policy.modifier_positions) == {
        "also",
        "first",
        "then",
        "therefore",
        "additionally",
        "finally",
        "next",
        "here",
    }
    assert set(policy.auxiliary_lemmas) == {"have", "will"}


def test_registry_templates_escape_regex_metacharacters() -> None:
    rule = ConstructionRule(
        id="literal_template",
        function="author_action",
        anchor_lemmas=["suggest"],
        children=[ConstructionChild(path=[["dobj"]], mode="slot", slot="X")],
        frame_templates=["[X] .*"],
    )
    policy = ConstructionsPolicy(version="0.0.1", constructions=[rule])

    assert is_safe_construction_frame("[X] .*", policy)
    assert not is_safe_construction_frame("[X] anything", policy)

    with pytest.raises(ValueError):
        ConstructionRule(
            id="empty_alternative",
            function="author_action",
            anchor_lemmas=["suggest"],
            children=[ConstructionChild(path=[["dobj"]], mode="slot", slot="X")],
            frame_templates=["[X] {suggest|}"],
        )


def test_candidate_writer_accepts_registry_frame_and_rejects_injected_slot() -> None:
    class Repository:
        def create_candidate(self, draft):
            return draft

    bundle = load_policy_bundle()
    writer = CandidateWriter(
        Repository(),
        reporting_policy=bundle.reporting_verbs,
        constructions_policy=bundle.constructions,
    )
    draft = CandidateDraft(
        canonical_frame="we propose [X].",
        source_sentence_ids=[uuid4()],
        slots={"X": SlotDefinition(type=SlotType.NOUN_PHRASE)},
        construction_id="author_action",
    )

    assert writer.write(draft).construction_id == "author_action"
    adjunct_draft = CandidateDraft(
        canonical_frame="We use [X] for [Y].",
        source_sentence_ids=[uuid4()],
        slots={
            "X": SlotDefinition(type=SlotType.NOUN_PHRASE),
            "Y": SlotDefinition(type=SlotType.NOUN_PHRASE),
        },
        construction_id="author_action",
    )
    assert writer.write(adjunct_draft).construction_id == "author_action"
    with pytest.raises(ValueError, match="masked positional frame"):
        writer.write(
            CandidateDraft(
                canonical_frame="we propose [X] [injected].",
                source_sentence_ids=[uuid4()],
                construction_id="author_action",
            )
        )


def test_reporting_match_precedes_a_registry_pattern_that_also_matches() -> None:
    text = "These results suggest that the method is robust to noise."
    policy = ConstructionsPolicy(
        version="0.1.0",
        constructions=[
            ConstructionRule(
                id="reporting_overlap",
                function="author_action",
                anchor_lemmas=["suggest"],
                children=[
                    ConstructionChild(path=[["nsubj"]], mode="slot", slot="X"),
                    ConstructionChild(path=[["ccomp"]], mode="slot", slot="Y"),
                ],
                frame_templates=["[X] suggest [Y]."],
            )
        ],
    )
    bundle = load_policy_bundle()
    reporting = SlotAbstractor(bundle.reporting_verbs, bundle.slot_abstraction)
    construction = ConstructionMatcher(policy)
    stage = ReportingWithConstruction(reporting, construction)
    [result] = stage.process([_item(text)])

    # The listed Tier B subject now gets a separate determiner slot on the reporting path.
    assert result.text == "[X] [Y] suggest that [Z]."
    assert result.construction_id is None
    assert construction.match_counts == {}


@pytest.mark.parametrize(
    ("text", "frame"),
    [
        ("We use the proposed method.", "We use [X]."),
        ("We use the method for retrieval.", "We use [X]."),
        ("We use the method to estimate risk.", "We use [X] to [Y]."),
        (
            "We use the method in the lab for retrieval to reduce latency.",
            "We use [X] in [Y] to [Z].",
        ),
        ("We conduct experiments on three sets.", "We conduct [X]."),
        ("We compare the models with a baseline.", "We compare [X] with [Y]."),
        ("We present a model in this paper.", "We present [X] in this paper."),
        ("We present a model in the paper.", "We present [X]."),
        ("We evaluate the model as a baseline.", "We evaluate [X] as [Y]."),
        ("We provide results by email.", "We provide [X] by [Y]."),
        ("We consider the model with a baseline.", "We consider [X]."),
        ("We implement the model for retrieval.", "We implement [X]."),
        ("We use the method for retrieval to reduce latency.", "We use [X] to [Y]."),
        (
            "We use the method to estimate risk in this study.",
            "We use [X] to [Y] in this study.",
        ),
        (
            "In this study, we propose a compact method.",
            "In this study, we propose [X].",
        ),
    ],
)
def test_author_action_preserves_the_sentence_and_slots_adjuncts(text: str, frame: str) -> None:
    result = match_construction(_TOKENS[text], text, load_policy_bundle().constructions)

    assert not isinstance(result, str)
    assert result.frame == frame
    assert result.frame == _frame_from_slot_spans(text, result.slot_spans)
    assert result.ownership.value == "own"
    assert list(result.slots) == ["X", "Y", "Z"][: len(result.slots)]


@pytest.mark.parametrize(
    ("text", "frame"),
    [
        ("This paper proposes a compact method.", "This paper proposes [X]."),
        ("This study introduces a comparison protocol.", "This study introduces [X]."),
        ("This article presents a benchmark design.", "This article presents [X]."),
        (
            "This paper proposes a compact method for data routing.",
            "This paper proposes [X].",
        ),
    ],
)
def test_author_action_accepts_only_approved_self_reference_subjects(text: str, frame: str) -> None:
    bundle = load_policy_bundle()
    result = match_construction(_TOKENS[text], text, bundle.constructions, bundle.slot_abstraction)

    assert not isinstance(result, str)
    assert result.frame == frame
    assert result.frame == _frame_from_slot_spans(text, result.slot_spans)
    assert result.ownership.value == "own"


@pytest.mark.parametrize(
    ("text", "frame", "object_phrase"),
    [
        (
            "We provide a comparison of models and baselines.",
            "We provide [X].",
            "a comparison of models and baselines",
        ),
        (
            "We present a solution to sparse-data retrieval.",
            "We present [X].",
            "a solution to sparse-data retrieval",
        ),
        (
            "We introduce a dataset from multiple sources.",
            "We introduce [X].",
            "a dataset from multiple sources",
        ),
        (
            "We present a framework for analysis of sparse datasets from public repositories.",
            "We present [X].",
            "a framework for analysis of sparse datasets from public repositories",
        ),
        (
            "We compare a model from prior work with a baseline.",
            "We compare [X] with [Y].",
            "a model from prior work",
        ),
    ],
)
def test_object_internal_prepositions_stay_inside_x(
    text: str, frame: str, object_phrase: str
) -> None:
    result = match_construction(_TOKENS[text], text, load_policy_bundle().constructions)

    assert not isinstance(result, str)
    assert result.frame == frame
    assert result.frame == _frame_from_slot_spans(text, result.slot_spans)
    assert text[slice(*result.slot_spans["X"])] == object_phrase


@pytest.mark.parametrize(
    ("text", "frame"),
    [
        ("We also use the method.", "We also use [X]."),
        ("We first use the method.", "We first use [X]."),
        ("Then, we use the method.", "Then, we use [X]."),
        ("Therefore, we use the method.", "Therefore, we use [X]."),
        ("Additionally, we use the method.", "Additionally, we use [X]."),
        ("Finally, we use the method.", "Finally, we use [X]."),
        ("Next, we use the method.", "Next, we use [X]."),
        ("Here, we use the method.", "Here, we use [X]."),
        ("We have used the method.", "We have used [X]."),
        ("We will use the method.", "We will use [X]."),
    ],
)
def test_candidate_modifiers_and_auxiliaries_are_retained_only_in_approved_roles(
    text: str, frame: str
) -> None:
    bundle = load_policy_bundle()
    result = match_construction(
        _TOKENS[text],
        text,
        bundle.constructions,
        bundle.slot_abstraction,
        verb_group_policy=bundle.construction_verb_groups,
    )

    assert not isinstance(result, str)
    assert result.frame == frame
    assert result.frame == _frame_from_slot_spans(text, result.slot_spans)


@pytest.mark.parametrize(
    "text",
    [
        "We use the method also.",
        "We use the method first.",
        "We use the method then.",
        "We use the method therefore.",
        "We use the method additionally.",
        "We use the method finally.",
        "We use the method next.",
        "We use the method here.",
    ],
)
def test_candidate_modifiers_outside_observed_positions_are_rejected(text: str) -> None:
    bundle = load_policy_bundle()

    assert (
        match_construction(
            _TOKENS[text],
            text,
            bundle.constructions,
            bundle.slot_abstraction,
            verb_group_policy=bundle.construction_verb_groups,
        )
        == "unsupported_adjunct"
    )


def test_main_verb_have_is_not_accepted_as_an_auxiliary_anchor() -> None:
    text = "We have a method for retrieval."
    bundle = load_policy_bundle()

    assert (
        match_construction(
            _TOKENS[text],
            text,
            bundle.constructions,
            bundle.slot_abstraction,
            verb_group_policy=bundle.construction_verb_groups,
        )
        == "no_anchor"
    )


def test_auxiliary_lemma_used_as_object_is_not_consumed_as_a_verb_group_token() -> None:
    text = "We use will as a label."
    bundle = load_policy_bundle()
    result = match_construction(
        _TOKENS[text],
        text,
        bundle.constructions,
        bundle.slot_abstraction,
        verb_group_policy=bundle.construction_verb_groups,
    )

    assert not isinstance(result, str)
    assert result.frame == "We use [X] as [Y]."
    assert text[slice(*result.slot_spans["X"])] == "will"


@pytest.mark.parametrize(
    "text",
    [
        "This method proposes a compact method.",
        "This result proposes a compact method.",
        "This approach proposes a compact method.",
        "This work proposes a compact method.",
        "This conceptual paper proposes a compact method.",
    ],
)
def test_author_action_rejects_unapproved_self_reference_subjects(text: str) -> None:
    assert (
        match_construction(_TOKENS[text], text, load_policy_bundle().constructions)
        == "unsupported_subject"
    )


def test_author_action_does_not_match_copula_subject() -> None:
    text = "This paper is important."
    assert (
        match_construction(_TOKENS[text], text, load_policy_bundle().constructions) == "no_anchor"
    )


def test_author_action_purpose_advcl_and_xcomp_have_the_same_frame() -> None:
    from dataclasses import replace

    text = "We use the method to estimate risk."
    tokens = _TOKENS[text]
    [purpose] = [token for token in tokens if token.dep == "xcomp"]
    advcl_tokens = tuple(
        replace(token, dep="advcl") if token.i == purpose.i else token for token in tokens
    )
    policy = load_policy_bundle().constructions

    xcomp = match_construction(tokens, text, policy)
    advcl = match_construction(advcl_tokens, text, policy)

    assert not isinstance(xcomp, str) and not isinstance(advcl, str)
    assert xcomp.frame == advcl.frame == "We use [X] to [Y]."


def test_author_action_rejects_unlisted_or_unsupported_adjunct_shapes() -> None:
    policy = load_policy_bundle().constructions
    expected = {
        "We use the method at the lab.": "unsupported_adjunct",
        "We compare the model without the baseline.": "unsupported_adjunct",
        "We use the method because it reduces noise.": "ambiguous_dependency",
        "We use the method and compare the results.": "unsupported_coordination",
    }

    for text, reason in expected.items():
        assert match_construction(_TOKENS[text], text, policy) == reason


def test_author_action_does_not_match_passive_voice() -> None:
    text = "The method is used for retrieval."

    # Phase 9.1 names the unsupported voice explicitly instead of falling through to child lookup.
    assert (
        match_construction(_TOKENS[text], text, load_policy_bundle().constructions)
        == "unsupported_voice"
    )


def test_phase9_passive_self_reference_subject_is_rejected() -> None:
    text = "This paper is used for retrieval."
    assert (
        match_construction(_TOKENS[text], text, load_policy_bundle().constructions)
        == "unsupported_voice"
    )


def test_adjunct_rule_schema_rejects_duplicate_empty_and_unknown_entries() -> None:
    base = {
        "id": "test_author_action",
        "function": "author_action",
        "anchor_lemmas": ["use"],
        "subject_phrases": ["we"],
        "children": [
            ConstructionChild(path=[["nsubj"]], mode="literal", lemmas=["we"]),
            ConstructionChild(path=[["dobj"]], mode="slot", slot="X"),
        ],
    }
    valid = {
        "prepositions": ["in", "for", "with", "as", "on", "by"],
        "purpose_deps": ["advcl", "xcomp"],
        "max_count": 2,
        "literal_in_objects": ["paper", "study", "work", "article", "research"],
    }
    assert ConstructionRule(**base, adjuncts=valid).adjuncts is not None

    for invalid in (
        {**valid, "prepositions": ["in", "in"]},
        {**valid, "prepositions": []},
        {**valid, "prepositions": ["at"]},
        {**valid, "purpose_deps": ["advcl", "acl"]},
        {**valid, "literal_in_objects": ["study", "study"]},
    ):
        with pytest.raises(ValidationError):
            ConstructionRule(**base, adjuncts=invalid)


def test_author_action_subject_registry_is_closed_and_unique() -> None:
    policy = load_policy_bundle().constructions
    [rule] = [item for item in policy.constructions if item.id == "author_action"]

    assert rule.subject_phrases == ["we", "this paper", "this study", "this article"]
    payload = rule.model_dump()
    for invalid in (
        ["we", "we"],
        ["this paper", "This Paper"],
        ["this method"],
        [""],
    ):
        with pytest.raises(ValidationError):
            ConstructionRule.model_validate({**payload, "subject_phrases": invalid})

    policy_payload = policy.model_dump()
    for item in policy_payload["constructions"]:
        if item["id"] == "author_action":
            item["subject_phrases"] = []
    with pytest.raises(ValidationError):
        type(policy).model_validate(policy_payload)


def test_adjunct_frame_validator_is_closed_world_and_keeps_literal_in_phrase() -> None:
    policy = load_policy_bundle().constructions

    assert is_safe_construction_frame("we use [X].", policy, construction_id="author_action")
    assert is_safe_construction_frame(
        "We present [X] in this paper.", policy, construction_id="author_action"
    )
    assert is_safe_construction_frame(
        "We present [X] in this paper for [Y].", policy, construction_id="author_action"
    )
    assert is_safe_construction_frame(
        "This paper proposes [X].", policy, construction_id="author_action"
    )
    assert not is_safe_construction_frame(
        "This method proposes [X].", policy, construction_id="author_action"
    )
    assert not is_safe_construction_frame(
        "Recently, we use [X].", policy, construction_id="author_action"
    )
    assert not is_safe_construction_frame(
        "we use [X] at [Y].", policy, construction_id="author_action"
    )
    assert not is_safe_construction_frame(
        "we use [X] [injected].", policy, construction_id="author_action"
    )
