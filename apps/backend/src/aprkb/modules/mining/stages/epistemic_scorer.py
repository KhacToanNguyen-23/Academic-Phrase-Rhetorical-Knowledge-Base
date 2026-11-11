"""Deterministic compositional epistemic scoring over a parsed spaCy sentence."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, cast

from aprkb.policies.schemas import EpistemicScoringPolicy

if TYPE_CHECKING:
    from spacy.tokens import Doc, Span

StrengthLabel = Literal["low", "moderate", "high", "absolute", "negative_refuted", "not_applicable"]
SCORER_PROVENANCE = "spacy_dependency_scorer"
POLICY_PROVENANCE = "epistemic_policy"
AI_LEXICON_PROVENANCE = "epistemic_ai_lexicon"
OOV_PROVENANCE = "syntax_gate_oov_default"
NO_SPACY_PROVENANCE = "unscored_no_spacy_doc"
SCORED_PROVENANCES = frozenset(
    {SCORER_PROVENANCE, POLICY_PROVENANCE, AI_LEXICON_PROVENANCE, OOV_PROVENANCE}
)

RELATIONAL_OBJECTS = frozenset(
    {
        "link",
        "correlation",
        "difference",
        "gap",
        "improvement",
        "reduction",
        "effect",
        "evidence",
        "trend",
        "relationship",
        "association",
        "result",
        "finding",
        "pattern",
        "performance",
        "accuracy",
        "validity",
        "reliability",
        "increase",
        "decrease",
        "impact",
        "implication",
        "connection",
        "outcome",
    }
)
LOCATIVE_ARTIFACTS = frozenset(
    {
        "table",
        "tabel",
        "figure",
        "fig",
        "section",
        "appendix",
        "algorithm",
        "equation",
        "paper",
        "literature",
        "dataset",
    }
)


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
    score: float | None
    head_token: str
    detected_modifiers: list[dict[str, object]]
    provenance: str = SCORER_PROVENANCE
    lemma: str | None = None
    pos: str | None = None
    construction_family: str | None = None
    lexicon_revision: str | None = None


class EpistemicScorer:
    """Score one parsed sentence or span using its predicate and dependency modifiers."""

    def __init__(
        self,
        policy: EpistemicScoringPolicy,
        *,
        active_lexicon: Mapping[tuple[str, str, str], float] | None = None,
        lexicon_revision: str | None = None,
    ) -> None:
        self._policy = policy
        self._baseline_scores = policy.baseline_scores
        self._baseline_terms = {
            tier: frozenset(term.casefold() for term in terms)
            for tier, terms in policy.baseline_terms.items()
        }
        self._claim_complement_nouns = frozenset(
            term.casefold() for term in policy.claim_complement_nouns
        )
        self._active_lexicon = {
            (lemma.casefold(), pos.casefold(), family.casefold()): score
            for (lemma, pos, family), score in (active_lexicon or {}).items()
        }
        self._lexicon_revision = lexicon_revision
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
        matrix_scope = _matrix_clause_scope(root, scope)
        matrix_token_ids = {token.i for token in matrix_scope}
        head = _primary_predicate(root, scope, self._negative_control_lemmas)
        claim_structure = _claim_structure(head, self._claim_complement_nouns)
        if claim_structure is None and head is not root:
            claim_structure = _claim_structure(root, self._claim_complement_nouns)
        if claim_structure is None or _is_locative_artifact_passive(root, LOCATIVE_ARTIFACTS):
            return EpistemicResult(
                label="not_applicable",
                score=None,
                head_token=head.text,
                detected_modifiers=[],
                provenance=SCORER_PROVENANCE,
                lemma=_lemma(head),
                pos=head.pos_.casefold(),
            )
        construction_family = claim_structure
        lemma = _lemma(head)
        pos = head.pos_.casefold()
        configured_lemma = any(lemma in terms for terms in self._baseline_terms.values())
        if not configured_lemma and pos not in {"verb", "aux"}:
            return EpistemicResult(
                label="not_applicable",
                score=None,
                head_token=head.text,
                detected_modifiers=[],
                provenance=SCORER_PROVENANCE,
                lemma=lemma,
                pos=pos,
                construction_family=construction_family,
            )
        active_key = (lemma, pos, construction_family.casefold())
        active_score = self._active_lexicon.get(active_key)
        if configured_lemma:
            score = self._baseline(head, scope)
            provenance = POLICY_PROVENANCE
        elif active_score is not None:
            score = active_score
            provenance = AI_LEXICON_PROVENANCE
        else:
            score = self._policy.oov_fallback_score
            provenance = OOV_PROVENANCE
        modifiers: list[dict[str, object]] = []

        for token in scope:
            token_lemma = _lemma(token)
            token_text = token.text.casefold()
            if token is head:
                continue
            modal_group = _modal_group(token, token_lemma, self._modal_terms)
            if modal_group is not None:
                embedded_clause_modal = token.i not in matrix_token_ids
                delta = (
                    self._policy.embedded_possibility_modal_delta
                    if modal_group == "possibility" and embedded_clause_modal
                    else self._policy.modal_deltas[modal_group]
                )
                score += delta
                modifiers.append(
                    {
                        "kind": f"modal_{modal_group}",
                        "token": token.text,
                        "delta": delta,
                        **({"scope": "embedded_clause"} if embedded_clause_modal else {}),
                    }
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

        matrix_possibility_modal = any(
            _modal_group(token, _lemma(token), self._modal_terms) == "possibility"
            and token.i in matrix_token_ids
            for token in scope
        )
        if matrix_possibility_modal:
            score = min(score, self._policy.possibility_modal_cap)

        refuted = _is_refuted(
            root, head, scope, self._negation_terms, self._negative_control_lemmas
        )
        if refuted:
            score = -abs(score)
            modifiers.append({"kind": "negative_refutation", "token": head.text, "delta": None})
            label: StrengthLabel = "negative_refuted"
        elif matrix_possibility_modal:
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
            provenance=provenance,
            lemma=lemma,
            pos=pos,
            construction_family=construction_family,
            lexicon_revision=(
                self._lexicon_revision if provenance == AI_LEXICON_PROVENANCE else None
            ),
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


def _matrix_clause_scope(root: _Token, scope: list[_Token]) -> list[_Token]:
    clause_boundaries = {"acl", "advcl", "ccomp", "relcl", "xcomp"}
    matrix_scope: list[_Token] = []
    for token in scope:
        ancestor = token
        crosses_clause_boundary = False
        while ancestor.i != root.i:
            if ancestor.dep_.casefold() in clause_boundaries:
                crosses_clause_boundary = True
                break
            ancestor = ancestor.head
        if not crosses_clause_boundary:
            matrix_scope.append(token)
    return matrix_scope


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


def _claim_structure(head: _Token, claim_nouns: frozenset[str]) -> str | None:
    """Return a stable construction key only when the predicate governs claim content."""
    for child in head.children:
        dependency = child.dep_.casefold()
        if dependency in {"ccomp", "xcomp"}:
            return dependency
        if dependency in {"dobj", "obj"} and _lemma(child) in claim_nouns | RELATIONAL_OBJECTS:
            return f"object:{_lemma(child)}"
    return None


def _is_locative_artifact_passive(head: _Token, artifact_nouns: frozenset[str]) -> bool:
    """Reject passive artifact references such as 'shown in Figure 1'."""
    children = list(head.children)
    passive = any(
        child.dep_.casefold() in {"auxpass", "aux:pass", "nsubjpass", "nsubj:pass"}
        for child in children
    )
    if not passive or any(child.dep_.casefold() in {"ccomp", "xcomp"} for child in children):
        return False
    for prep in children:
        if prep.dep_.casefold() != "prep" or _lemma(prep) not in {"in", "at", "on", "within"}:
            continue
        for pobj in prep.children:
            if _lemma(pobj) in artifact_nouns:
                return True
            if any(_lemma(child) in artifact_nouns for child in pobj.children):
                return True
    return False


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
