"""Small dependency-tree helpers shared by mining and the spike probe."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from aprkb.nlp.features import SentenceAnalysis, TokenFeature


def usable_tokens(analysis: SentenceAnalysis | None) -> tuple[TokenFeature, ...] | None:
    """Expose syntax tokens only when ingest did not have to repair the parse."""
    if analysis is None or analysis.repaired:
        return None
    return analysis.tokens


def validate_token_features(text: str, tokens: Sequence[TokenFeature]) -> bool:
    """Validate the structural contract needed by the syntax mining path."""
    if not tokens:
        return False
    count = len(tokens)
    if any(
        token.i != index
        or not 0 <= token.start < token.end <= len(text)
        or not 0 <= token.head < count
        for index, token in enumerate(tokens)
    ):
        return False
    if sum(token.dep == "ROOT" for token in tokens) != 1:
        return False
    for start in range(count):
        seen: set[int] = set()
        current = start
        while current not in seen:
            seen.add(current)
            next_index = tokens[current].head
            if next_index == current:
                break
            current = next_index
        else:
            return False
    return True


def children_by_head(tokens: Sequence[TokenFeature]) -> dict[int, tuple[int, ...]]:
    children: dict[int, list[int]] = {token.i: [] for token in tokens}
    for token in tokens:
        children[token.head].append(token.i)
    return {index: tuple(values) for index, values in children.items()}


def normalized_children_by_head(tokens: Sequence[TokenFeature]) -> dict[int, tuple[int, ...]]:
    """Normalize aux-attached clause markers and subjects one level toward their clause head."""
    children = children_by_head(tokens)
    clause_heads = {
        token.i for token in tokens if token.dep in {"ROOT", "ccomp", "xcomp", "advcl", "acl"}
    }
    normalized: dict[int, list[int]] = {index: [] for index in children}
    for token in tokens:
        parent = tokens[token.head]
        if (
            token.dep in {"mark", "nsubj", "nsubjpass", "csubj", "csubjpass"}
            and parent.dep in {"aux", "auxpass", "cop"}
            and parent.head in clause_heads
            and tokens[parent.head].pos in {"VERB", "AUX"}
        ):
            normalized[parent.head].append(token.i)
        else:
            normalized[token.head].append(token.i)
    return {index: tuple(values) for index, values in normalized.items()}


def subtree_indices(children: dict[int, tuple[int, ...]], root: int) -> tuple[int, ...]:
    found: list[int] = []
    pending = [root]
    visited: set[int] = set()
    while pending:
        index = pending.pop()
        if index in visited:
            continue
        visited.add(index)
        found.append(index)
        pending.extend(reversed(children.get(index, ())))
    return tuple(found)


def subtree_span(
    tokens: Sequence[TokenFeature], children: dict[int, tuple[int, ...]], root: int
) -> tuple[int, int]:
    indices = subtree_indices(children, root)
    return min(tokens[index].start for index in indices), max(
        tokens[index].end for index in indices
    )


@dataclass(frozen=True)
class SyntaxRootSelection:
    """Parser ROOT, or a promoted reporting predicate and its inferred subject span."""

    token: TokenFeature
    promoted_subject_span: tuple[int, int] | None = None


def select_syntax_root(tokens: Sequence[TokenFeature]) -> SyntaxRootSelection | None:
    """Select the parser ROOT or a unique marked-clause ACL directly under it."""
    if not tokens or any(
        token.i != index or not 0 <= token.head < len(tokens) for index, token in enumerate(tokens)
    ):
        return None
    roots = [token for token in tokens if token.dep == "ROOT"]
    if len(roots) != 1:
        return None

    parser_root = roots[0]
    children = normalized_children_by_head(tokens)
    candidates = [
        tokens[index]
        for index in children[parser_root.i]
        if tokens[index].dep == "acl"
        and any(
            tokens[marker].dep == "mark" and tokens[marker].lemma.casefold() == "that"
            for clause in children[index]
            for marker in children[clause]
        )
    ]
    if len(candidates) != 1:
        return SyntaxRootSelection(parser_root)

    promoted = candidates[0]
    prefix_starts = [
        tokens[index].start
        for index in subtree_indices(children, parser_root.i)
        if tokens[index].end <= promoted.start
    ]
    if not prefix_starts:
        return SyntaxRootSelection(parser_root)
    return SyntaxRootSelection(promoted, (min(prefix_starts), promoted.start))


def spacy_subtree_text(token: Any, source: str) -> str:
    """Render a spaCy subtree for the human-readable spike probe only."""
    start = token.left_edge.idx
    end = token.right_edge.idx + len(token.right_edge.text)
    return source[start:end].rstrip(".,!?;:").replace("|", "\\|")
