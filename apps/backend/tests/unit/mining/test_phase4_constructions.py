"""Phase-4 construction matching and safety regressions on spaCy-free snapshots."""

import json
from pathlib import Path
from uuid import uuid4

import pytest

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


@pytest.mark.parametrize(
    ("text", "frame", "construction_id", "slot"),
    [
        (
            "In this study, we propose a compact method.",
            "we propose [X].",
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

    assert result.text == frame
    assert result.construction_id == construction_id
    assert f"construction={construction_id}:0.1.0:" in (result.cluster_key or "")
    assert any(text[start:end] == slot for start, end in result.occurrences[0].slot_spans.values())


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("We discuss a compact method.", "no_anchor"),
        ("We carefully propose a useful method today.", "unmatched_content"),
        ("Our method does not improve classification accuracy.", "unmatched_content"),
    ],
)
def test_construction_matcher_rejects_unreviewed_forms(text: str, reason: str) -> None:
    policy = load_policy_bundle().constructions

    assert match_construction(_TOKENS[text], text, policy) == reason


def test_registry_frame_validation_rejects_injected_bracketed_text() -> None:
    policy = load_policy_bundle().constructions
    matcher = ConstructionMatcher(policy)

    assert matcher.match_item(_item("In this study, we propose a compact method.")) is not None
    assert is_safe_construction_frame("we propose [X].", policy)
    assert not is_safe_construction_frame("we propose [X] [injected].", policy)


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

    assert result.text == "[X] [Y] suggest that [Z]."
    assert result.construction_id is None
    assert construction.match_counts == {}
