"""Deterministic compositional epistemic scoring over a parsed spaCy sentence."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, cast

from aprkb.policies.schemas import EpistemicScoringPolicy

if TYPE_CHECKING:
    from spacy.tokens import Doc, Span

StrengthLabel = Literal["low", "moderate", "high", "absolute", "negative_refuted"]
SCORER_PROVENANCE = "spacy_dependency_scorer"
NO_SPACY_PROVENANCE = "unscored_no_spacy_doc"


class _Token(Protocol):
    text: str
    lemma_: str
    dep_: str
    pos_: str
    i: int
    head: _Token
    children: Iterable[_Token]


@dataclass(frozen=True)
class EpistemicResult:
    label: StrengthLabel
    score: float
    head_token: str
    detected_modifiers: list[dict[str, object]]


class EpistemicScorer:
    """Score one parsed sentence or span using its predicate and dependency modifiers."""

    def __init__(self, policy: EpistemicScoringPolicy) -> None:
        self._policy = policy
        self._baseline_scores = policy.baseline_scores
        self._baseline_terms = {
            tier: frozenset(term.casefold() for term in terms)
            for tier, terms in policy.baseline_terms.items()
        }
        self._modal_terms = {
            group: frozenset(term.casefold() for term in terms)
            for group, terms in policy.modal_terms.items()
        }
        self._adverb_terms = {
            group: frozenset(term.casefold() for term in terms)
            for group, terms in policy.adverb_terms.items()
        }
        self._negation_terms = frozenset(term.casefold() for term in policy.negation_terms)
        self._negative_control_lemmas = frozenset(
            term.casefold() for term in policy.negative_control_lemmas
        )
        self._doubt_quantifiers = frozenset(term.casefold() for term in policy.doubt_quantifiers)
        self._evidence_downtoners = frozenset(
            term.casefold() for term in policy.evidence_downtoners
        )
        self._strong_evidence_adjectives = frozenset(
            term.casefold() for term in policy.strong_evidence_adjectives
        )

    def score(self, parsed: Doc | Span) -> EpistemicResult:
        """Return the score, tier, assertion head, and applied modifier diagnostics."""
        root, input_tokens = _parsed_root(parsed)
        scope = _dependency_scope(root, input_tokens)
        head = _primary_predicate(root, scope, self._negative_control_lemmas)
        score = self._baseline(head, scope)
        modifiers: list[dict[str, object]] = []

        for token in scope:
            token_lemma = _lemma(token)
            token_text = token.text.casefold()
            if token is head:
                continue
            modal_group = _modal_group(token, token_lemma, self._modal_terms)
            if modal_group is not None:
                delta = self._policy.modal_deltas[modal_group]
                score += delta
                modifiers.append(
                    {"kind": f"modal_{modal_group}", "token": token.text, "delta": delta}
                )
                continue

            if token.dep_.casefold() == "advmod":
                for group in ("maximal", "strong", "downtoner"):
                    if (
                        token_lemma in self._adverb_terms[group]
                        or token_text in self._adverb_terms[group]
                    ):
                        delta = self._policy.adverb_deltas[group]
                        score += delta
                        modifiers.append(
                            {"kind": f"adverb_{group}", "token": token.text, "delta": delta}
                        )
                        break

        if any(_lemma(token) == "without" for token in scope) and any(
            _lemma(token) == "doubt" for token in scope
        ):
            delta = self._policy.doubt_context_delta
            score += delta
            modifiers.append({"kind": "certainty_phrase", "token": "without doubt", "delta": delta})

        for token in scope:
            token_lemma = _lemma(token)
            if token_lemma == "doubt" and any(
                child.text.casefold() in self._doubt_quantifiers
                or _lemma(child) in self._doubt_quantifiers
                for child in token.children
            ):
                score += self._policy.doubt_context_delta
                modifiers.append(
                    {
                        "kind": "quantified_doubt",
                        "token": token.text,
                        "delta": self._policy.doubt_context_delta,
                    }
                )
            if token_lemma == "evidence":
                for child in token.children:
                    child_lemma = _lemma(child)
                    if child_lemma in self._evidence_downtoners:
                        score += self._policy.evidence_context_delta
                        modifiers.append(
                            {
                                "kind": "qualified_evidence",
                                "token": child.text,
                                "delta": self._policy.evidence_context_delta,
                            }
                        )
                    elif child_lemma in self._strong_evidence_adjectives:
                        delta = (
                            0.0
                            if token is head
                            else self._baseline_scores["high"] - self._policy.default_score
                        )
                        score += delta
                        modifiers.append(
                            {"kind": "strong_evidence", "token": child.text, "delta": delta}
                        )

        possibility_modal = any(
            _modal_group(token, _lemma(token), self._modal_terms) == "possibility"
            for token in scope
        )
        if possibility_modal:
            score = min(score, self._policy.possibility_modal_cap)

        refuted = _is_refuted(
            root, head, scope, self._negation_terms, self._negative_control_lemmas
        )
        if refuted:
            score = -abs(score)
            modifiers.append({"kind": "negative_refutation", "token": head.text, "delta": None})
            label: StrengthLabel = "negative_refuted"
        elif possibility_modal:
            # The spec's 0.8 ceiling overlaps the moderate band; its acceptance example
            # requires possibility-modaled claims to remain in low.
            label = "low"
        else:
            label = self._classify(score)

        return EpistemicResult(
            label=label,
            score=round(score, 4),
            head_token=head.text,
            detected_modifiers=modifiers,
        )

    def _baseline(self, head: _Token, scope: list[_Token]) -> float:
        lemma = _lemma(head)
        scope_lemmas = {_lemma(token) for token in scope}
        if lemma == "establish" and {"beyond", "doubt"} <= scope_lemmas:
            return self._baseline_scores["absolute"]
        if lemma == "point" and "to" in scope_lemmas:
            return self._baseline_scores["moderate"]
        if lemma == "consistent" and "with" in scope_lemmas:
            return self._baseline_scores["moderate"]
        for tier in ("absolute", "high", "moderate", "low"):
            if lemma in self._baseline_terms[tier]:
                return self._baseline_scores[tier]
        return self._policy.default_score

    def _classify(self, score: float) -> StrengthLabel:
        if score >= self._policy.thresholds["absolute"]:
            return "absolute"
        if score >= self._policy.thresholds["high"]:
            return "high"
        if score >= self._policy.thresholds["moderate"]:
            return "moderate"
        return "low"


def _parsed_root(parsed: Doc | Span) -> tuple[_Token, set[int]]:
    """Require one parsed sentence so a Doc cannot silently mix assertions."""
    if hasattr(parsed, "root"):
        tokens = list(parsed)
        if not tokens:
            raise ValueError("EpistemicScorer requires a non-empty parsed span")
        return cast(_Token, parsed.root), {token.i for token in tokens}
    sentences = list(parsed.sents)
    if len(sentences) != 1:
        raise ValueError("EpistemicScorer requires a Doc containing exactly one sentence")
    tokens = list(sentences[0])
    if not tokens:
        raise ValueError("EpistemicScorer requires a non-empty parsed sentence")
    return cast(_Token, sentences[0].root), {token.i for token in tokens}


def _dependency_scope(root: _Token, input_tokens: set[int]) -> list[_Token]:
    scope: list[_Token] = []
    pending = [root]
    seen: set[int] = set()
    while pending:
        token = pending.pop()
        if token.i in seen or token.i not in input_tokens:
            continue
        seen.add(token.i)
        scope.append(token)
        pending.extend(sorted(token.children, key=lambda child: child.i, reverse=True))
    return scope


def _primary_predicate(
    root: _Token,
    scope: list[_Token],
    negative_control_lemmas: frozenset[str],
) -> _Token:
    """Choose a copular predicate or the complement of a negative control verb."""
    root_lemma = _lemma(root)
    if root_lemma in negative_control_lemmas:
        complement = next(
            (token for token in scope if token.dep_.casefold() in {"xcomp", "ccomp"}), None
        )
        if complement is not None:
            return complement
    if root_lemma in {"be", "remain"}:
        predicate = next(
            (token for token in scope if token.dep_.casefold() in {"acomp", "attr", "oprd"}),
            None,
        )
        if predicate is not None:
            return predicate
    return root


def _modal_group(
    token: _Token,
    lemma: str,
    modal_terms: dict[Literal["possibility", "assertive", "conditional"], frozenset[str]],
) -> Literal["possibility", "assertive", "conditional"] | None:
    if token.dep_.casefold() not in {"aux", "auxpass", "aux:pass"}:
        return None
    for group in ("possibility", "assertive", "conditional"):
        if lemma in modal_terms[group] or token.text.casefold() in modal_terms[group]:
            return group
    return None


def _is_refuted(
    root: _Token,
    head: _Token,
    scope: list[_Token],
    negation_terms: frozenset[str],
    negative_control_lemmas: frozenset[str],
) -> bool:
    matrix_path: set[int] = {head.i}
    ancestor = head
    while ancestor.i != root.i:
        ancestor = ancestor.head
        matrix_path.add(ancestor.i)

    if any(token.i in matrix_path and _lemma(token) in negative_control_lemmas for token in scope):
        return True
    for token in scope:
        lemma = _lemma(token)
        surface = token.text.casefold()
        governs_matrix = token.head.i in matrix_path
        if (
            governs_matrix
            and token.dep_.casefold() == "neg"
            and (lemma in negation_terms or surface in negation_terms)
        ):
            return True
        if governs_matrix and (lemma in negation_terms or surface in negation_terms):
            # "no doubt" is a positive certainty construction, not a refutation.
            if lemma == "no" and any(_lemma(child) == "doubt" for child in token.children):
                continue
            return True
    return False


def _lemma(token: _Token) -> str:
    return (token.lemma_ or token.text).casefold()
