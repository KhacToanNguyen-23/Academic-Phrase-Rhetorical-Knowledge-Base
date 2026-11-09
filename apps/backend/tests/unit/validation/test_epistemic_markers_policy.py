"""Unit tests for V02 inflection metadata in the epistemic markers policy."""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from aprkb.modules.mining.stages.base import MiningItem
from aprkb.modules.mining.stages.epistemic_tagger import EpistemicTagger
from aprkb.modules.validation.context import ValidationContext
from aprkb.modules.validation.rules.base import Severity
from aprkb.modules.validation.rules.v02_claim_evidence import V02ClaimEvidenceRule
from aprkb.policies.schemas import EpistemicMarkersPolicy

MARKERS = {
    "low": ["may"],
    "moderate": ["suggest"],
    "high": ["find"],
    "absolute": ["prove"],
}


def make_policy(**overrides) -> EpistemicMarkersPolicy:
    values = {"version": "0.1.0", "markers": MARKERS}
    values.update(overrides)
    return EpistemicMarkersPolicy.model_validate(values)


def test_default_lexicon_declares_inflection_metadata(policy_bundle):
    markers = policy_bundle.epistemic_markers

    assert markers.irregular_forms["prove"] == ["proven"]
    assert markers.irregular_forms["show"] == ["shown"]
    assert set(markers.neutral_verbs) == {
        "show",
        "shows",
        "showed",
        "shown",
        "find",
        "finds",
        "found",
        "observe",
        "observes",
        "observed",
        "note",
        "notes",
        "noted",
        "assume",
        "assumes",
        "assumed",
    }
    assert "may" in markers.non_inflecting
    assert "always" in markers.non_inflecting


def test_irregular_forms_are_used_by_v02(evidence_policy):
    with_irregular = make_policy(irregular_forms={"find": ["found"]})
    without_irregular = make_policy()
    rule_with = V02ClaimEvidenceRule(
        evidence_policy=evidence_policy,
        lexicon=with_irregular,
        severity=Severity.BLOCK,
    )
    rule_without = V02ClaimEvidenceRule(
        evidence_policy=evidence_policy,
        lexicon=without_irregular,
        severity=Severity.BLOCK,
    )

    assert rule_with._contains_marker("The study found that X.", "find")
    assert not rule_without._contains_marker("The study found that X.", "find")


@pytest.mark.parametrize(
    "overrides",
    [
        {"non_inflecting": ["not_declared"]},
        {"non_inflecting": ["may", "may"]},
        {"non_inflecting": [""]},
        {"irregular_forms": {"find": []}},
        {"validator_only_markers": {"unknown": ["show"]}},
        {"validator_only_markers": {"high": []}},
        {"validator_only_markers": {"high": ["show", "show"]}},
        {"validator_only_markers": {"high": ["find"]}},
        {"mining_only_markers": {"low": ["may"]}},
        {"validator_only_markers": {"high": ["show"]}, "mining_only_markers": {"low": ["show"]}},
    ],
)
def test_policy_rejects_invalid_inflection_metadata(overrides):
    with pytest.raises(ValueError):
        make_policy(**overrides)


def test_policy_defaults_optional_inflection_metadata():
    policy = EpistemicMarkersPolicy.model_validate({"version": "0.1.0", "markers": MARKERS})

    assert policy.irregular_forms == {}
    assert policy.non_inflecting == []
    assert policy.validator_only_markers == {}
    assert policy.mining_only_markers == {}


def test_scoped_markers_reach_only_their_own_consumer(evidence_policy):
    policy = make_policy(
        validator_only_markers={"high": ["show"]},
        mining_only_markers={"high": ["establish"]},
        neutral_verbs=["show"],
    )
    rule = V02ClaimEvidenceRule(
        evidence_policy=evidence_policy, lexicon=policy, severity=Severity.BLOCK
    )
    tagger = EpistemicTagger(policy)
    context = ValidationContext(claim_type="causal", evidence_level="none")

    assert rule.evaluate("We show that X.", context).severity is Severity.BLOCK
    assert rule.evaluate("We establish that X.", context).severity is Severity.PASS
    results = tagger.process(
        [MiningItem("[X] show that [Y]", []), MiningItem("[X] establish that [Y]", [])]
    )
    assert [(item.epistemic_strength, item.epistemic_status) for item in results] == [
        (None, "neutral"),
        ("high", "assigned"),
    ]


@pytest.mark.parametrize("form", ["show", "shows", "showed", "shown"])
def test_mining_keeps_show_neutral_while_v02_enforces_it(policy_bundle, form):
    tagger = EpistemicTagger(policy_bundle.epistemic_markers)

    [item] = tagger.process([MiningItem(f"[X] {form} that [Y]", [])])

    assert (item.epistemic_strength, item.epistemic_status) == (None, "neutral")


def test_epistemic_tagger_inherits_strength_for_irregular_forms(policy_bundle):
    tagger = EpistemicTagger(policy_bundle.epistemic_markers)
    results = tagger.process(
        [
            MiningItem("The baseline has been shown to improve.", []),
            MiningItem("The baseline had shown no improvement.", []),
            MiningItem("The baseline was proven to improve.", []),
        ]
    )

    assert [item.epistemic_strength for item in results] == [None, None, "absolute"]
    assert [item.epistemic_status for item in results] == ["neutral", "neutral", "assigned"]


def test_epistemic_tagger_reports_neutral_assigned_ambiguous_and_unknown(policy_bundle):
    tagger = EpistemicTagger(policy_bundle.epistemic_markers)
    inputs = [
        MiningItem("[X] show that [Y]", []),
        MiningItem("[X] established that [Y]", []),
        MiningItem("[X] may suggest that [Y]", []),
        MiningItem("[X] argue that [Y]", []),
        MiningItem("[X] [Y] that [Z]", []),
    ]
    results = tagger.process(inputs)

    assert [(item.epistemic_strength, item.epistemic_status) for item in results] == [
        (None, "neutral"),
        ("high", "assigned"),
        (None, "ambiguous"),
        (None, "unknown"),
        (None, "unknown"),
    ]


@pytest.mark.parametrize(
    "verb",
    [
        "show",
        "shows",
        "showed",
        "shown",
        "find",
        "finds",
        "found",
        "observe",
        "observes",
        "observed",
        "note",
        "notes",
        "noted",
        "assume",
        "assumes",
        "assumed",
    ],
)
def test_every_reviewed_neutral_verb_has_no_strength(policy_bundle, verb):
    tagger = EpistemicTagger(policy_bundle.epistemic_markers)

    [item] = tagger.process([MiningItem(f"[X] {verb} that [Y]", [])])

    assert item.epistemic_strength is None
    assert item.epistemic_status == "neutral"


def test_epistemic_tagger_reads_only_the_masked_verb_group_in_pipeline(policy_bundle):
    from aprkb.modules.mining.pipeline import MiningPipeline
    from aprkb.modules.mining.stages import build_stages
    from aprkb.nlp.features import TokenFeature

    pipeline = MiningPipeline(stages=build_stages(policy_bundle=policy_bundle))
    find_text = "The authors find that prior studies may suggest an improvement."
    snapshot_path = Path(__file__).parents[2] / "fixtures" / "nlp_spike" / "token_snapshots.json"
    snapshot = next(
        case
        for case in json.loads(snapshot_path.read_text(encoding="utf-8"))["cases"]
        if case["text"] == find_text
    )
    find_tokens = tuple(TokenFeature.from_json(token) for token in snapshot["analysis"]["tokens"])
    items = [
        MiningItem(
            "The authors observe that prior studies may suggest an improvement.",
            [uuid4()],
        ),
        MiningItem("The authors establish that the method improves retrieval quality.", [uuid4()]),
        MiningItem(
            "The authors may suggest that the method improves retrieval quality.", [uuid4()]
        ),
        MiningItem(
            find_text,
            [uuid4()],
            tokens=find_tokens,
            locator="syntax:en_core_web_sm:3.8.0",
        ),
        MiningItem("The authors assume that the method improves retrieval quality.", [uuid4()]),
    ]

    results = pipeline.process(items)

    assert [(item.text, item.epistemic_strength, item.epistemic_status) for item in results] == [
        ("[X] observe that [Y].", None, "neutral"),
        ("[X] establish that [Y].", "high", "assigned"),
        ("[X] may suggest that [Y].", None, "ambiguous"),
        ("[X] find that [Y].", None, "neutral"),
        ("[X] assume that [Y].", None, "neutral"),
    ]
