from __future__ import annotations

from collections.abc import Iterable

import pytest

from aprkb.modules.mining.stages.base import MiningItem
from aprkb.modules.mining.stages.epistemic_scorer import EpistemicScorer
from aprkb.modules.mining.stages.epistemic_tagger import EpistemicTagger
from aprkb.policies.loader import load_policy_bundle


class ParsedToken:
    def __init__(self, text: str, lemma: str, dep: str, index: int) -> None:
        self.text = text
        self.lemma_ = lemma
        self.dep_ = dep
        self.pos_ = "VERB"
        self.i = index
        self.head: ParsedToken = self
        self._children: list[ParsedToken] = []

    @property
    def children(self) -> Iterable[ParsedToken]:
        return iter(self._children)

    def add(self, child: ParsedToken) -> ParsedToken:
        child.head = self
        self._children.append(child)
        return child


class ParsedSpan:
    def __init__(self, root: ParsedToken, tokens: list[ParsedToken]) -> None:
        self.root = root
        self._tokens = tokens

    def __iter__(self):
        return iter(self._tokens)


class ParsedDoc:
    def __init__(self, sentence: ParsedSpan) -> None:
        self.sents = [sentence]


def _doc(root: ParsedToken, *tokens: ParsedToken) -> ParsedDoc:
    return ParsedDoc(ParsedSpan(root, [root, *tokens]))


@pytest.fixture
def scorer() -> EpistemicScorer:
    return EpistemicScorer(load_policy_bundle().epistemic_scoring)


def test_conclusively_proves_is_absolute(scorer: EpistemicScorer) -> None:
    root = ParsedToken("prove", "prove", "ROOT", 1)
    adverb = root.add(ParsedToken("conclusively", "conclusively", "advmod", 0))
    root.add(ParsedToken("holds", "hold", "ccomp", 3))

    result = scorer.score(_doc(root, adverb, *root._children[1:]))

    assert (result.label, result.score, result.head_token) == ("absolute", 4.5, "prove")
    assert result.detected_modifiers == [
        {"kind": "adverb_maximal", "token": "conclusively", "delta": 1.5}
    ]


def test_clearly_demonstrates_is_high(scorer: EpistemicScorer) -> None:
    root = ParsedToken("demonstrate", "demonstrate", "ROOT", 2)
    adverb = root.add(ParsedToken("clearly", "clearly", "advmod", 1))
    obj = root.add(ParsedToken("correlation", "correlation", "dobj", 4))
    modifier = obj.add(ParsedToken("substantial", "substantial", "amod", 3))

    result = scorer.score(_doc(root, adverb, obj, modifier))

    assert (result.label, result.score) == ("absolute", 3.0)


def test_possibility_modal_caps_score_and_forces_low(scorer: EpistemicScorer) -> None:
    root = ParsedToken("prove", "prove", "ROOT", 1)
    modal = root.add(ParsedToken("may", "may", "aux", 0))
    root.add(ParsedToken("hold", "hold", "ccomp", 3))

    result = scorer.score(_doc(root, modal, *root._children[1:]))

    assert (result.label, result.score) == ("low", 0.4)
    assert result.detected_modifiers[0] == {
        "kind": "modal_possibility",
        "token": "may",
        "delta": -2.0,
    }


def test_embedded_possibility_modal_has_light_penalty_without_matrix_cap(
    scorer: EpistemicScorer,
) -> None:
    root = ParsedToken("shows", "show", "ROOT", 1)
    complement = root.add(ParsedToken("improve", "improve", "ccomp", 5))
    modal = complement.add(ParsedToken("can", "can", "aux", 4))

    result = scorer.score(_doc(root, complement, modal))

    assert (result.label, result.score) == ("moderate", 1.5)
    assert result.detected_modifiers == [
        {
            "kind": "modal_possibility",
            "token": "can",
            "delta": -0.5,
            "scope": "embedded_clause",
        }
    ]


def test_embedded_modal_inside_nested_complement_does_not_cap_matrix_score(
    scorer: EpistemicScorer,
) -> None:
    root = ParsedToken("shows", "show", "ROOT", 1)
    complement = root.add(ParsedToken("report", "report", "ccomp", 4))
    nested = complement.add(ParsedToken("improve", "improve", "xcomp", 7))
    modal = nested.add(ParsedToken("can", "can", "aux", 6))

    result = scorer.score(_doc(root, complement, nested, modal))

    assert (result.label, result.score) == ("moderate", 1.5)
    assert result.detected_modifiers == [
        {
            "kind": "modal_possibility",
            "token": "can",
            "delta": -0.5,
            "scope": "embedded_clause",
        }
    ]


def test_unmodified_suggests_is_moderate(scorer: EpistemicScorer) -> None:
    root = ParsedToken("suggests", "suggest", "ROOT", 0)
    complement = root.add(ParsedToken("holds", "hold", "ccomp", 2))

    result = scorer.score(_doc(root, complement))

    assert (result.label, result.score) == ("moderate", 1.0)


def test_hedged_complement_is_low(scorer: EpistemicScorer) -> None:
    root = ParsedToken("hypothesize", "hypothesize", "ROOT", 0)
    complement = root.add(ParsedToken("influence", "influence", "ccomp", 5))
    modal = complement.add(ParsedToken("could", "could", "aux", 4))
    downtoner = complement.add(ParsedToken("partially", "partially", "advmod", 6))

    result = scorer.score(_doc(root, complement, modal, downtoner))

    assert (result.label, result.score) == ("low", -2.5)


def test_fails_to_confirm_is_negative_refuted(scorer: EpistemicScorer) -> None:
    root = ParsedToken("fails", "fail", "ROOT", 0)
    complement = root.add(ParsedToken("confirm", "confirm", "xcomp", 2))
    root.add(ParsedToken("to", "to", "aux", 1))

    result = scorer.score(_doc(root, complement, *root._children[1:]))

    assert (result.label, result.score, result.head_token) == (
        "negative_refuted",
        -2.0,
        "confirm",
    )


def test_cannot_be_concluded_is_negative_refuted(scorer: EpistemicScorer) -> None:
    root = ParsedToken("concluded", "conclude", "ROOT", 3)
    root.add(ParsedToken("cannot", "cannot", "auxpass", 1))
    root.add(ParsedToken("hold", "hold", "ccomp", 5))
    result = scorer.score(_doc(root, *root._children))

    assert result.label == "negative_refuted"


def test_negated_complement_does_not_refute_matrix_assertion(scorer: EpistemicScorer) -> None:
    root = ParsedToken("confirms", "confirm", "ROOT", 1)
    complement = root.add(ParsedToken("reduce", "reduce", "ccomp", 5))
    negation = complement.add(ParsedToken("not", "not", "neg", 4))

    result = scorer.score(_doc(root, complement, negation))

    assert (result.label, result.score, result.head_token) == ("high", 2.0, "confirms")


def test_nested_negative_control_does_not_refute_matrix_assertion(
    scorer: EpistemicScorer,
) -> None:
    root = ParsedToken("confirms", "confirm", "ROOT", 1)
    complement = root.add(ParsedToken("fail", "fail", "ccomp", 5))

    result = scorer.score(_doc(root, complement))

    assert (result.label, result.score, result.head_token) == ("high", 2.0, "confirms")


def test_copular_predicate_and_doubt_quantification(scorer: EpistemicScorer) -> None:
    root = ParsedToken("evident", "evident", "ROOT", 2)
    root.add(ParsedToken("is", "be", "cop", 1))
    root.add(ParsedToken("holds", "hold", "ccomp", 4))
    assert scorer.score(_doc(root, *root._children)).label == "high"

    doubt = ParsedToken("doubt", "doubt", "ROOT", 3)
    doubt.add(ParsedToken("no", "no", "det", 2))
    doubt.add(ParsedToken("holds", "hold", "ccomp", 5))
    result = scorer.score(_doc(doubt, *doubt._children))
    assert (result.label, result.score) == ("absolute", 3.5)

    without_doubt = ParsedToken("doubt", "doubt", "ROOT", 3)
    without_doubt.add(ParsedToken("remains", "remain", "ccomp", 5))
    without = without_doubt.add(ParsedToken("without", "without", "prep", 1))
    result = scorer.score(_doc(without_doubt, without))
    assert (result.label, result.score) == ("absolute", 3.5)


def test_default_mining_tag_is_null_without_a_parsed_doc() -> None:
    tagger = EpistemicTagger(load_policy_bundle().epistemic_scoring)
    [item] = tagger.process([MiningItem(text="[X] suggests that [Y]", source_sentence_ids=[])])

    assert item.epistemic_strength is None
    assert item.epistemic_status == "unknown"
    assert item.epistemic_score is None
    assert item.epistemic_provenance == "unscored_no_spacy_doc"


def test_tagger_uses_parsed_doc_and_exposes_score() -> None:
    root = ParsedToken("suggests", "suggest", "ROOT", 0)
    root.add(ParsedToken("holds", "hold", "ccomp", 3))
    tagger = EpistemicTagger(load_policy_bundle().epistemic_scoring)
    item = MiningItem(
        text="[X] suggests that [Y]",
        source_sentence_ids=[],
        epistemic_doc=_doc(root),  # type: ignore[arg-type]
    )

    [result] = tagger.process([item])

    assert result.epistemic_strength == "moderate"
    assert result.epistemic_status == "assigned"
    assert result.epistemic_score == 1.0
    assert result.epistemic_provenance == "epistemic_policy"


def test_unfamiliar_predicate_with_clausal_complement_uses_moderate_oov_fallback(
    scorer: EpistemicScorer,
) -> None:
    root = ParsedToken("records", "record", "ROOT", 1)
    root.add(ParsedToken("holds", "hold", "ccomp", 4))

    result = scorer.score(_doc(root, *root._children))

    assert (result.label, result.score, result.provenance) == (
        "moderate",
        1.0,
        "syntax_gate_oov_default",
    )
    assert result.construction_family == "ccomp"


def test_active_ai_lexicon_entry_overrides_oov_fallback() -> None:
    policy = load_policy_bundle().epistemic_scoring
    scorer = EpistemicScorer(
        policy,
        active_lexicon={("record", "verb", "ccomp"): 2.0},
        lexicon_revision="lex:test-revision",
    )
    root = ParsedToken("records", "record", "ROOT", 1)
    root.add(ParsedToken("holds", "hold", "ccomp", 4))

    result = scorer.score(_doc(root, *root._children))

    assert (result.label, result.score) == ("high", 2.0)
    assert result.provenance == "epistemic_ai_lexicon"
    assert result.lexicon_revision == "lex:test-revision"


def test_matrix_possibility_modal_on_claim_predicate_hits_low_ceiling(
    scorer: EpistemicScorer,
) -> None:
    root = ParsedToken("observe", "observe", "ROOT", 2)
    root.add(ParsedToken("can", "can", "aux", 1))
    root.add(ParsedToken("holds", "hold", "ccomp", 5))

    result = scorer.score(_doc(root, *root._children))

    assert (result.label, result.score) == ("low", 0.0)


def test_predicate_without_claim_complement_is_not_applicable(scorer: EpistemicScorer) -> None:
    root = ParsedToken("observes", "observe", "ROOT", 1)

    result = scorer.score(_doc(root))

    assert (result.label, result.score) == ("not_applicable", None)


def test_direct_relational_object_passes_syntax_gate(scorer: EpistemicScorer) -> None:
    root = ParsedToken("show", "show", "ROOT", 1)
    root.add(ParsedToken("correlation", "correlation", "obj", 2))

    result = scorer.score(_doc(root, *root._children))

    assert (result.label, result.score) == ("high", 2.0)


def test_passive_artifact_location_is_rejected_but_claim_complement_is_kept(
    scorer: EpistemicScorer,
) -> None:
    root = ParsedToken("shown", "show", "ROOT", 2)
    root.add(ParsedToken("is", "be", "auxpass", 1))
    prep = root.add(ParsedToken("in", "in", "prep", 3))
    prep.add(ParsedToken("Figure", "figure", "pobj", 4))

    rejected = scorer.score(_doc(root, *root._children, *prep._children))
    assert (rejected.label, rejected.score) == ("not_applicable", None)

    root.add(ParsedToken("holds", "hold", "ccomp", 6))
    accepted = scorer.score(_doc(root, *root._children, *prep._children))
    assert (accepted.label, accepted.score) == ("high", 2.0)


def test_tagger_keeps_refutation_out_of_the_four_strength_tiers() -> None:
    root = ParsedToken("fails", "fail", "ROOT", 0)
    root.add(ParsedToken("confirm", "confirm", "xcomp", 2))
    tagger = EpistemicTagger(load_policy_bundle().epistemic_scoring)
    item = MiningItem(
        text="[X] fails to confirm [Y]",
        source_sentence_ids=[],
        epistemic_doc=_doc(root, *root._children),  # type: ignore[arg-type]
    )

    [result] = tagger.process([item])

    assert result.epistemic_strength is None
    assert result.epistemic_status == "refuted"
    assert result.epistemic_score == -2.0
