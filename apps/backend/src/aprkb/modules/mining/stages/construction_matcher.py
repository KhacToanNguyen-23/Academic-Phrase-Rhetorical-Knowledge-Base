"""Conservative dependency-anchored matcher for versioned non-reporting constructions."""

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, replace

from aprkb.modules.mining.schemas import Ownership, SlotDefinition, SlotType, Tense
from aprkb.modules.mining.stages.base import ExtractionOccurrence, MiningItem, MiningStage
from aprkb.modules.mining.stages.slot_abstractor import (
    SlotAbstractor,
    _definition,
    _extend_following_citation,
    infer_ownership,
)
from aprkb.nlp.features import TokenFeature
from aprkb.nlp.syntax import (
    normalized_children_by_head,
    select_syntax_root,
    subtree_indices,
    subtree_span,
    validate_token_features,
)
from aprkb.policies.schemas import (
    ConstructionChild,
    ConstructionRule,
    ConstructionsPolicy,
    SlotAbstractionPolicy,
    compile_construction_template,
)


@dataclass(frozen=True)
class MatchResult:
    frame: str
    slots: dict[str, SlotDefinition]
    slot_spans: dict[str, tuple[int, int]]
    tense: Tense
    ownership: Ownership
    construction_id: str
    construction_version: str


def match_construction(
    tokens: tuple[TokenFeature, ...],
    text: str,
    registry: ConstructionsPolicy,
    ownership_policy: SlotAbstractionPolicy | None = None,
    previous_text: str | None = None,
    section_code: str | None = None,
) -> MatchResult | str:
    """Match the first registry construction, returning counts-safe reasons on rejection."""
    if not validate_token_features(text, tokens):
        return "syntax_invalid_tokens"
    selection = select_syntax_root(tokens)
    if selection is None:
        return "syntax_invalid_tokens"
    last_reason = "no_anchor"
    for rule in registry.constructions:
        if selection.token.pos != "VERB" or selection.token.lemma.casefold() not in {
            lemma.casefold() for lemma in rule.anchor_lemmas
        }:
            continue
        result = _match_rule(
            tokens,
            text,
            selection.token,
            rule,
            registry.version,
            ownership_policy,
            previous_text,
            section_code,
        )
        if isinstance(result, MatchResult):
            return result
        last_reason = result
    return last_reason


def _match_rule(
    tokens: tuple[TokenFeature, ...],
    text: str,
    anchor: TokenFeature,
    rule: ConstructionRule,
    version: str,
    ownership_policy: SlotAbstractionPolicy | None,
    previous_text: str | None,
    section_code: str | None,
) -> MatchResult | str:
    children = normalized_children_by_head(tokens)
    if any(
        tokens[index].dep == "conj" and tokens[index].pos in {"VERB", "AUX"}
        for index in children[anchor.i]
    ):
        return "coordinated_construction"

    literal_indices = {anchor.i}
    slot_spans: dict[str, tuple[int, int]] = {}
    for child in rule.children:
        route = _resolve_path(tokens, children, anchor.i, child)
        if route is None:
            if child.optional:
                continue
            return "missing_child"
        for parent in route[:-1]:
            literal_indices.add(parent)
        node_index = route[-1]
        node = tokens[node_index]
        if child.lemmas and node.lemma.casefold() not in {
            lemma.casefold() for lemma in child.lemmas
        }:
            return "missing_child"

        if child.mode == "literal_optional":
            if node.lemma.casefold() not in {value.casefold() for value in rule.allowed_literal}:
                return "unmatched_content"
            literal_indices.update(subtree_indices(children, node_index))
        elif child.mode == "literal":
            literal_indices.add(node_index)
            for descendant in children[node_index]:
                if tokens[descendant].dep in child.include_descendant_deps:
                    literal_indices.update(subtree_indices(children, descendant))
        elif child.mode == "slot":
            start, end = subtree_span(tokens, children, node_index)
            if child.slot in slot_spans:
                return "missing_child"
            slot_spans[child.slot or ""] = (start, end)
        elif child.mode == "head_literal_modifiers_slot":
            modifiers = [
                index for index in children[node_index] if tokens[index].dep in child.modifier_deps
            ]
            if not modifiers or child.slot in slot_spans:
                return "missing_child"
            modifier_spans = [subtree_span(tokens, children, index) for index in modifiers]
            slot_spans[child.slot or ""] = (
                min(span[0] for span in modifier_spans),
                max(span[1] for span in modifier_spans),
            )
            literal_indices.add(node_index)
            for modifier in modifiers:
                literal_indices.difference_update(subtree_indices(children, modifier))

    if not slot_spans:
        return "missing_child"
    for token in tokens:
        if token.is_space or token.pos == "PUNCT":
            continue
        if token.i in literal_indices or _inside(token, slot_spans.values()):
            continue
        if token.lemma.casefold() not in {value.casefold() for value in rule.allowed_literal}:
            return "unmatched_content"

    frame = _render_frame(text, tokens, literal_indices, slot_spans)
    trailing = re.search(r"[.!?]+\s*$", text)
    if trailing is not None:
        frame += trailing.group(0).strip()
    if not any(
        re.fullmatch(compile_construction_template(template), frame, flags=re.IGNORECASE)
        for template in rule.frame_templates
    ):
        return "unsafe_frame"

    slots: dict[str, SlotDefinition] = {}
    for name, (start, end) in sorted(slot_spans.items()):
        root = next(token for token in tokens if token.start <= start < token.end)
        slot_type = SlotType.CLAUSE if root.pos in {"VERB", "AUX"} else SlotType.NOUN_PHRASE
        slots[name] = _definition(slot_type, text[start:end])
    group = {
        token.i
        for token in tokens
        if token.head == anchor.i and token.dep in {"aux", "auxpass", "neg", "advmod"}
    }
    subject_node = next(
        (
            tokens[index]
            for index in children[anchor.i]
            if tokens[index].dep in {"nsubj", "nsubjpass"}
        ),
        None,
    )
    if subject_node is None:
        subject = ""
    else:
        subject_span = subtree_span(tokens, children, subject_node.i)
        subject_span = _extend_following_citation(text, *subject_span)
        subject = text[slice(*subject_span)]
    return MatchResult(
        frame=frame,
        slots=slots,
        slot_spans=slot_spans,
        tense=SlotAbstractor._syntax_tense(tokens, anchor.i, group),
        ownership=infer_ownership(subject, previous_text, ownership_policy, section_code),
        construction_id=rule.id,
        construction_version=version,
    )


def _resolve_path(
    tokens: tuple[TokenFeature, ...],
    children: dict[int, tuple[int, ...]],
    anchor_index: int,
    rule: ConstructionChild,
) -> list[int] | None:
    current = [anchor_index]
    route: list[int] = []
    for step, dependencies in enumerate(rule.path):
        candidates = [
            index
            for parent in current
            for index in children[parent]
            if tokens[index].dep in dependencies
            and (
                not rule.path_lemmas
                or not rule.path_lemmas[step]
                or tokens[index].lemma.casefold()
                in {lemma.casefold() for lemma in rule.path_lemmas[step]}
            )
        ]
        if len(candidates) != 1:
            return None
        route.append(candidates[0])
        current = [candidates[0]]
    return route


def _inside(token: TokenFeature, spans: Iterable[tuple[int, int]]) -> bool:
    return any(start <= token.start and token.end <= end for start, end in spans)


def _render_frame(
    text: str,
    tokens: tuple[TokenFeature, ...],
    literal_indices: set[int],
    spans: dict[str, tuple[int, int]],
) -> str:
    starts = {start: (end, name) for name, (start, end) in spans.items()}
    parts: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.start in starts:
            end, name = starts[token.start]
            parts.append(f"[{name}]")
            while index < len(tokens) and tokens[index].start < end:
                index += 1
            continue
        if token.i in literal_indices:
            parts.append(text[token.start : token.end])
        index += 1
    return " ".join(parts)


class ConstructionMatcher(MiningStage):
    name = "construction_matcher"
    requirement_id = "FR-06.2"

    def __init__(
        self, policy: ConstructionsPolicy, ownership_policy: SlotAbstractionPolicy | None = None
    ) -> None:
        self._policy = policy
        self._ownership_policy = ownership_policy
        self._matches: Counter[str] = Counter()
        self._rejections: Counter[str] = Counter()

    @property
    def match_counts(self) -> dict[str, int]:
        return dict(sorted(self._matches.items()))

    @property
    def rejection_counts(self) -> dict[str, int]:
        return dict(sorted(self._rejections.items()))

    def match_item(self, item: MiningItem) -> MiningItem | None:
        if item.tokens is None:
            self._rejections["no_tokens"] += 1
            return None
        result = match_construction(
            item.tokens,
            item.text,
            self._policy,
            self._ownership_policy,
            item.previous_text,
            item.section_code,
        )
        if isinstance(result, str):
            self._rejections[result] += 1
            return None
        occurrence = ExtractionOccurrence(
            sentence_id=item.source_sentence_ids[0],
            sentence_start=item.char_start,
            sentence_end=item.char_start + len(item.text),
            slot_spans={
                name: (item.char_start + start, item.char_start + end)
                for name, (start, end) in result.slot_spans.items()
            },
        )
        self._matches[result.construction_id] += 1
        return replace(
            item,
            text=result.frame,
            slots=result.slots,
            occurrences=[occurrence],
            tense=result.tense,
            ownership=result.ownership,
            slot_binding_fingerprint=None,
            construction_id=result.construction_id,
            construction_version=result.construction_version,
        )

    def process(self, batch: list[MiningItem]) -> list[MiningItem]:
        matched: list[MiningItem] = []
        for item in batch:
            result = self.match_item(item)
            if result is not None:
                matched.append(result)
        return matched


class ReportingWithConstruction(MiningStage):
    """Run the established reporting path first, then try constructions on its misses."""

    name = "reporting_and_construction_matcher"
    requirement_id = "FR-06.2"

    def __init__(self, reporting: SlotAbstractor, constructions: ConstructionMatcher) -> None:
        self.reporting = reporting
        self.constructions = constructions

    def extractability_reason(
        self, text: str, tokens: tuple[TokenFeature, ...] | None
    ) -> str | None:
        return self.reporting.extractability_reason(text, tokens)

    @property
    def syntax_fallback_reasons(self) -> dict[str, int]:
        return self.reporting.syntax_fallback_reasons

    def process(self, batch: list[MiningItem]) -> list[MiningItem]:
        reported = self.reporting.process(batch)
        output: dict[tuple[object, ...], MiningItem] = {
            tuple(item.source_sentence_ids): item for item in reported
        }
        for item in batch:
            key = tuple(item.source_sentence_ids)
            if key in output:
                continue
            matched = self.constructions.match_item(item)
            if matched is not None:
                output[key] = matched
        return [
            output[tuple(item.source_sentence_ids)]
            for item in batch
            if tuple(item.source_sentence_ids) in output
        ]
