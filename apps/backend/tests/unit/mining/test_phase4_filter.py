"""Phase-4 syntax filter regressions with hand-built dependency features."""

import re

import pytest

from aprkb.modules.mining.stages.base import MiningItem
from aprkb.modules.mining.stages.sentence_filter import SentenceFilter
from aprkb.nlp.features import TokenFeature
from aprkb.policies.loader import load_policy_bundle
from aprkb.policies.schemas import SyntaxFilterSettings


def _imperative_tokens(
    text: str, root_index: int, complement_index: int
) -> tuple[TokenFeature, ...]:
    matches = list(re.finditer(r"\w+|[^\w\s]", text))
    tokens = []
    for index, match in enumerate(matches):
        is_root = index == root_index
        is_complement = index == complement_index
        tokens.append(
            TokenFeature(
                i=index,
                start=match.start(),
                end=match.end(),
                pos="VERB" if is_root else "PUNCT" if not match.group().isalnum() else "NOUN",
                tag="VB" if is_root else "NN" if match.group().isalnum() else ".",
                dep="ROOT" if is_root else "dobj" if is_complement else "punct",
                head=index if is_root else root_index,
                lemma=match.group().casefold(),
                morph="",
                is_space=False,
            )
        )
    return tuple(tokens)


@pytest.mark.parametrize(
    ("text", "root_index", "complement_index"),
    [
        ("Let x be a real number in the interval considered here.", 0, 1),
        ("Consider the case of two nodes connected by a single edge.", 0, 2),
    ],
)
def test_supported_bare_imperatives_pass_filter(
    text: str, root_index: int, complement_index: int
) -> None:
    policy = load_policy_bundle().mining_filter
    item = MiningItem(
        text=text,
        source_sentence_ids=[],
        tokens=_imperative_tokens(text, root_index, complement_index),
    )
    stage = SentenceFilter(
        min_words=1,
        max_words=60,
        noise=policy.noise_filter,
        syntax=policy.syntax_filter,
    )

    assert stage.reject_reason(item) is None
    assert stage.accepted_as_imperative(item)


def test_imperative_requires_complement_and_flag() -> None:
    text = "Introduction"
    tokens = _imperative_tokens(text, 0, -1)
    enabled = SentenceFilter(
        min_words=1,
        max_words=10,
        syntax=SyntaxFilterSettings(allow_imperatives=True),
    )
    disabled = SentenceFilter(
        min_words=1,
        max_words=10,
        syntax=SyntaxFilterSettings(allow_imperatives=False),
    )
    item = MiningItem(text=text, source_sentence_ids=[], tokens=tokens)

    assert enabled.reject_reason(item) == "no_finite_verb"
    assert disabled.reject_reason(item) == "no_finite_verb"


def test_imperative_with_a_finite_subjectless_clause_stays_on_regular_path() -> None:
    text = "Consider the result that matters."
    tokens = list(_imperative_tokens(text, 0, 2))
    finite = tokens[4]
    tokens[4] = TokenFeature(
        i=finite.i,
        start=finite.start,
        end=finite.end,
        pos="VERB",
        tag="VBZ",
        dep=finite.dep,
        head=finite.head,
        lemma=finite.lemma,
        morph="VerbForm=Fin|Tense=Pres",
        is_space=finite.is_space,
    )
    item = MiningItem(text=text, source_sentence_ids=[], tokens=tuple(tokens))
    stage = SentenceFilter(
        min_words=1,
        max_words=20,
        syntax=SyntaxFilterSettings(allow_imperatives=True),
    )

    assert stage.reject_reason(item) is None
    assert not stage.accepted_as_imperative(item)
