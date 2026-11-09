"""Conservative dependency-anchored matcher for versioned non-reporting constructions."""

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, replace

from aprkb.modules.mining.schemas import Ownership, SlotDefinition, SlotType, Tense
from aprkb.modules.mining.stages.base import ExtractionOccurrence, MiningItem, MiningStage
from aprkb.modules.mining.stages.hybrid_slot_engine import HybridSlotEngine
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
    ConstructionVerbGroupPolicy,
    SlotAbstractionPolicy,
    compile_construction_template,
    is_safe_construction_frame,
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
    verb_group_policy: ConstructionVerbGroupPolicy | None = None,
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
            verb_group_policy,
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
    verb_group_policy: ConstructionVerbGroupPolicy | None,
) -> MatchResult | str:
    children = normalized_children_by_head(tokens)
    if any(
        tokens[index].dep == "conj" and tokens[index].pos in {"VERB", "AUX"}
        for index in children[anchor.i]
    ):
        return (
            "unsupported_coordination" if rule.adjuncts is not None else "coordinated_construction"
        )

    if rule.subject_phrases or (rule.id == "author_action" and rule.adjuncts is not None):
        allowed_subject_phrases = rule.subject_phrases or ["we"]
        subject_nodes = [
            tokens[index]
            for index in children[anchor.i]
            if tokens[index].dep in {"nsubj", "nsubjpass"}
        ]
        if not subject_nodes:
            return "missing_subject"
        if any(node.dep == "nsubjpass" for node in subject_nodes):
            return "unsupported_voice"
        if len(subject_nodes) != 1 or subject_nodes[0].dep != "nsubj":
            return "ambiguous_dependency"
        subject_indices = sorted(subtree_indices(children, subject_nodes[0].i))
        subject_phrase = " ".join(
            text[tokens[index].start : tokens[index].end]
            for index in subject_indices
            if not tokens[index].is_space and tokens[index].pos != "PUNCT"
        ).casefold()
        if subject_phrase not in {phrase.casefold() for phrase in allowed_subject_phrases}:
            return "unsupported_subject"
        subject_node = subject_nodes[0]
        subject_span = subtree_span(tokens, children, subject_node.i)

    literal_indices = {anchor.i}
    slot_spans: dict[str, tuple[int, int]] = {}
    consumed_roots: set[int] = set()
    for child in rule.children:
        route, path_issue = _resolve_path_diagnosed(tokens, children, anchor.i, child)
        if route is None:
            if child.optional:
                continue
            if path_issue == "ambiguous":
                return "ambiguous_dependency"
            if child.path and any(dep in {"nsubj", "nsubjpass"} for dep in child.path[0]):
                return "missing_subject"
            return (
                "missing_object"
                if rule.adjuncts is not None and child.slot == "X"
                else "missing_child"
            )
        for parent in route[:-1]:
            literal_indices.add(parent)
        consumed_roots.add(route[0])
        node_index = route[-1]
        node = tokens[node_index]
        if child.lemmas and node.lemma.casefold() not in {
            lemma.casefold() for lemma in child.lemmas
        }:
            return (
                "missing_object"
                if rule.adjuncts is not None and child.slot == "X"
                else "missing_child"
            )

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
            excluded: set[int] = set()
            if rule.adjuncts is not None and child.slot == "X":
                for descendant in subtree_indices(children, node_index):
                    if (
                        tokens[descendant].dep != "prep"
                        or tokens[descendant].lemma.casefold() != "in"
                    ):
                        continue
                    objects = [
                        index
                        for index in children[descendant]
                        if tokens[index].dep in {"pobj", "obj"}
                    ]
                    if len(objects) != 1:
                        continue
                    object_index = objects[0]
                    has_this = any(
                        tokens[index].dep == "det" and tokens[index].lemma.casefold() == "this"
                        for index in children[object_index]
                    )
                    if (
                        has_this
                        and tokens[object_index].lemma.casefold()
                        in rule.adjuncts.literal_in_objects
                    ):
                        literal_phrase = set(subtree_indices(children, descendant))
                        excluded.update(literal_phrase)
                        literal_indices.update(literal_phrase)
                span = _content_subtree_span(tokens, children, node_index, exclude=excluded)
                if span is not None and any(
                    tokens[index].start < span[1] and tokens[index].end > span[0]
                    for index in excluded
                ):
                    span = None
            else:
                span = (
                    _content_subtree_span(tokens, children, node_index)
                    if rule.adjuncts is not None
                    else subtree_span(tokens, children, node_index)
                )
            if span is None:
                return "invalid_source_span" if rule.adjuncts is not None else "missing_child"
            start, end = span
            if child.slot in slot_spans:
                return "ambiguous_dependency" if rule.adjuncts is not None else "missing_child"
            slot_spans[child.slot or ""] = (start, end)
        elif child.mode == "head_literal_modifiers_slot":
            modifiers = [
                index for index in children[node_index] if tokens[index].dep in child.modifier_deps
            ]
            if not modifiers or child.slot in slot_spans:
                return "ambiguous_dependency" if rule.adjuncts is not None else "missing_child"
            modifier_spans = [subtree_span(tokens, children, index) for index in modifiers]
            slot_spans[child.slot or ""] = (
                min(span[0] for span in modifier_spans),
                max(span[1] for span in modifier_spans),
            )
            literal_indices.add(node_index)
            for modifier in modifiers:
                literal_indices.difference_update(subtree_indices(children, modifier))

    if not slot_spans:
        return "missing_object" if rule.adjuncts is not None else "missing_child"
    if rule.adjuncts is not None:
        adjunct_spans: list[tuple[int, int]] = []
        # A PP is a construction adjunct only when spaCy attaches it to the predicate.
        # PPs below the direct object remain part of the complete object NP slot.
        prep_nodes = {index for index in children[anchor.i] if tokens[index].dep == "prep"}
        purpose_markers = {
            index
            for child_index in children[anchor.i]
            if tokens[child_index].dep in rule.adjuncts.purpose_deps
            for index in children[child_index]
            if tokens[index].dep in {"aux", "mark"} and tokens[index].lemma.casefold() == "to"
        }
        for child_index in sorted(prep_nodes | set(children[anchor.i])):
            dep_token = tokens[child_index]
            if (
                child_index == anchor.i
                or child_index in consumed_roots
                or child_index in purpose_markers
                or dep_token.pos == "PUNCT"
            ):
                continue
            if child_index not in prep_nodes and dep_token.dep not in {
                "prep",
                *rule.adjuncts.purpose_deps,
            }:
                continue
            if dep_token.dep == "prep":
                prep = dep_token.lemma.casefold()
                if prep not in rule.adjuncts.prepositions:
                    return "unsupported_adjunct"
                objects = [
                    index for index in children[child_index] if tokens[index].dep in {"pobj", "obj"}
                ]
                if len(objects) != 1:
                    return "ambiguous_dependency"
                object_index = objects[0]
                object_lemma = tokens[object_index].lemma.casefold()
                has_this = any(
                    tokens[index].dep == "det" and tokens[index].lemma.casefold() == "this"
                    for index in children[object_index]
                )
                if prep == "in" and has_this and object_lemma in rule.adjuncts.literal_in_objects:
                    literal_indices.update(subtree_indices(children, child_index))
                    continue
                adjunct_spans.append(subtree_span(tokens, children, object_index))
                literal_indices.add(child_index)
                continue
            if dep_token.dep in rule.adjuncts.purpose_deps:
                to_tokens = [
                    index
                    for index in children[child_index]
                    if tokens[index].dep in {"aux", "mark"}
                    and tokens[index].lemma.casefold() == "to"
                ]
                if len(to_tokens) != 1:
                    return "ambiguous_dependency"
                excluded = set(to_tokens)
                for descendant in subtree_indices(children, child_index):
                    if (
                        tokens[descendant].dep == "prep"
                        and tokens[descendant].lemma.casefold() == "in"
                    ):
                        objects = [
                            index
                            for index in children[descendant]
                            if tokens[index].dep in {"pobj", "obj"}
                        ]
                        if (
                            len(objects) == 1
                            and tokens[objects[0]].lemma.casefold()
                            in rule.adjuncts.literal_in_objects
                            and any(
                                tokens[index].dep == "det"
                                and tokens[index].lemma.casefold() == "this"
                                for index in children[objects[0]]
                            )
                        ):
                            literal_indices.update(subtree_indices(children, descendant))
                            excluded.update(subtree_indices(children, descendant))
                span = _content_subtree_span(tokens, children, child_index, exclude=excluded)
                if span is None:
                    return "invalid_source_span"
                adjunct_spans.append(span)
                literal_indices.add(to_tokens[0])
                continue
            return "unsupported_adjunct"
        ordered_adjuncts = sorted(adjunct_spans, key=lambda value: value[0])
        if len(ordered_adjuncts) > rule.adjuncts.max_count:
            return "too_many_adjuncts"
        for ordinal, span in enumerate(ordered_adjuncts, start=1):
            slot_spans[{1: "Y", 2: "Z"}[ordinal]] = span
        ordered_slots = sorted(slot_spans.items(), key=lambda item: item[1][0])
        if any(
            current[1][0] < previous[1][1]
            for previous, current in zip(ordered_slots, ordered_slots[1:], strict=False)
        ):
            return "invalid_source_span"

    if rule.adjuncts is not None and verb_group_policy is not None:
        modifier_counts: Counter[str] = Counter()
        auxiliary_count = 0
        object_start = slot_spans.get("X", (len(text), len(text)))[0]
        for child_index in children[anchor.i]:
            token = tokens[child_index]
            lemma = token.lemma.casefold()
            if (
                token.dep == "advmod"
                and token.pos == "ADV"
                and lemma in verb_group_policy.modifier_positions
            ):
                if token.end <= subject_span[0]:
                    position = "before_subject"
                elif token.start >= subject_span[1] and token.end <= anchor.start:
                    position = "between_subject_and_anchor"
                elif token.start >= anchor.end and token.end <= object_start:
                    position = "after_anchor_before_object"
                else:
                    return "unsupported_adjunct"
                if position not in verb_group_policy.modifier_positions[lemma]:
                    return "unsupported_adjunct"
                modifier_counts[position] += 1
                if modifier_counts[position] > 1:
                    return "ambiguous_dependency"
                literal_indices.add(child_index)
            elif token.dep == "aux" and lemma in verb_group_policy.auxiliary_lemmas:
                if token.pos != "AUX" or token.start < subject_span[1] or token.end > anchor.start:
                    return "ambiguous_dependency"
                auxiliary_count += 1
                if auxiliary_count > 1:
                    return "ambiguous_dependency"
                literal_indices.add(child_index)

    for token in tokens:
        if token.is_space or token.pos == "PUNCT":
            continue
        if token.i in literal_indices or _inside(token, slot_spans.values()):
            continue
        if token.lemma.casefold() in {value.casefold() for value in rule.allowed_literal}:
            literal_indices.add(token.i)
        elif rule.adjuncts is not None:
            return "unsupported_adjunct"
        else:
            return "unmatched_content"

    if rule.adjuncts is not None:
        frame = _replace_slot_spans(text, slot_spans)
        if not is_safe_construction_frame(
            frame,
            ConstructionsPolicy(version=version, constructions=[rule]),
            construction_id=rule.id,
            verb_group_policy=verb_group_policy,
        ):
            return "unsafe_clause_boundary"
    else:
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
    output_subject_node = next(
        (
            tokens[index]
            for index in children[anchor.i]
            if tokens[index].dep in {"nsubj", "nsubjpass"}
        ),
        None,
    )
    if output_subject_node is None:
        subject = ""
    else:
        subject_span = subtree_span(tokens, children, output_subject_node.i)
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


def _content_subtree_span(
    tokens: tuple[TokenFeature, ...],
    children: dict[int, tuple[int, ...]],
    root: int,
    exclude: set[int] | None = None,
) -> tuple[int, int] | None:
    ignored = exclude or set()
    content = [
        tokens[index]
        for index in subtree_indices(children, root)
        if index not in ignored and not tokens[index].is_space and tokens[index].pos != "PUNCT"
    ]
    if not content:
        return None
    return min(token.start for token in content), max(token.end for token in content)


def _replace_slot_spans(text: str, spans: dict[str, tuple[int, int]]) -> str:
    ordered = sorted((start, end, name) for name, (start, end) in spans.items())
    pieces: list[str] = []
    position = 0
    for start, end, name in ordered:
        if start < position or end < start:
            raise ValueError("construction slot spans overlap")
        pieces.extend((text[position:start], f"[{name}]"))
        position = end
    pieces.append(text[position:])
    return "".join(pieces)


def _resolve_path(
    tokens: tuple[TokenFeature, ...],
    children: dict[int, tuple[int, ...]],
    anchor_index: int,
    rule: ConstructionChild,
) -> list[int] | None:
    route, _ = _resolve_path_diagnosed(tokens, children, anchor_index, rule)
    return route


def _resolve_path_diagnosed(
    tokens: tuple[TokenFeature, ...],
    children: dict[int, tuple[int, ...]],
    anchor_index: int,
    rule: ConstructionChild,
) -> tuple[list[int] | None, str | None]:
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
        if not candidates:
            return None, "missing"
        if len(candidates) > 1:
            return None, "ambiguous"
        route.append(candidates[0])
        current = [candidates[0]]
    return route, None


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
        self,
        policy: ConstructionsPolicy,
        ownership_policy: SlotAbstractionPolicy | None = None,
        verb_group_policy: ConstructionVerbGroupPolicy | None = None,
    ) -> None:
        self._policy = policy
        self._ownership_policy = ownership_policy
        self._verb_group_policy = verb_group_policy
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
            self._verb_group_policy,
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

    def __init__(
        self,
        reporting: SlotAbstractor,
        constructions: ConstructionMatcher,
        hybrid: HybridSlotEngine | None = None,
    ) -> None:
        self.reporting = reporting
        self.constructions = constructions
        self.hybrid = hybrid

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
            if matched is None and self.hybrid is not None and item.tokens is not None:
                matched = self.hybrid.match_item(item)
            if matched is not None:
                output[key] = matched
        return [
            output[tuple(item.source_sentence_ids)]
            for item in batch
            if tuple(item.source_sentence_ids) in output
        ]
