"""Dependency based, deterministic Tier 2 mining fallback."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import replace

from aprkb.modules.mining.schemas import Ownership, SlotDefinition, SlotType
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
    HYBRID_SLOT_BOUNDARY,
    HybridConstructionsPolicy,
    ReportingVerbsPolicy,
    SlotAbstractionPolicy,
    hybrid_frame_has_abbreviation,
    hybrid_frame_has_dangling_tail,
    is_safe_hybrid_frame,
)

_PUNCT = re.compile(r"^[,.;:!?]+$")
# A frame keeps the pattern around its slots, not the whole sentence (FR-06.2, round 1 fix).
_LIGHT_DEPS = frozenset({"aux", "auxpass", "neg", "advmod", "prt", "acomp"})
_LIGHT_CHILD_DEPS = frozenset({"advmod", "neg", "aux"})
_DISCOURSE_LEAD_MAX_TOKENS = 4
_DISCOURSE_LEAD_BLOCKED_POS = frozenset({"VERB", "AUX", "PROPN", "NUM"})
_SLOT_LEAD_MAX_WORDS = 12
_TRAILING_MAX_TOKENS = 8
# Trigger words that define a family. TODO(owner, FR-06.2): provisional, grammar-level only.
_GAP_TRIGGERS = frozenset({"little", "few", "rarely", "no", "lack", "remain", "unclear"})
_COMPARATIVE_ROOTS = frozenset({"outperform", "correlate", "differ"})
_COMPARATIVE_MARKERS = frozenset({"more", "less", "than", "superior", "similar", "higher", "lower"})
_CLAUSE_DEPS = frozenset(
    {"mark", "cc", "advcl", "relcl", "acl", "parataxis", "conj", "ccomp", "appos", "dep"}
)
# Names and sizes such as ``CNN+LSTM`` or ``128 × 128`` are ordinary slot text, not formulas.
_SLOT_SAFE_MATH_SIGNS = frozenset("+×")
_CITATION = re.compile(r"\[(?:\s*\d+\s*(?:[,;–-]\s*\d+\s*)*)\]")


class HybridSlotEngine(MiningStage):
    """Try eight configured construction families after both Tier 1 matchers miss."""

    name = "hybrid_slot_engine"
    requirement_id = "FR-06.2"

    def __init__(
        self,
        policy: HybridConstructionsPolicy,
        reporting_verbs: ReportingVerbsPolicy,
        ownership_policy: SlotAbstractionPolicy,
        fixed_lead_ins: list[str] | None = None,
    ) -> None:
        self._policy = policy
        self._reporting_verbs = reporting_verbs
        self._ownership_policy = ownership_policy
        self._fixed_lead_ins = fixed_lead_ins or []
        self._infinitive_verbs = {verb.casefold() for verb in policy.infinitive_verbs}
        self._preposition_verbs = {
            verb.casefold(): preposition.casefold()
            for verb, preposition in policy.preposition_verbs.items()
        }
        self._idioms = [
            (idiom.verb.casefold(), idiom.noun.casefold(), idiom.preposition.casefold())
            for idiom in policy.idiom_frames
        ]
        self._reporting = SlotAbstractor(reporting_verbs, ownership_policy)
        self._families = {family.id: family for family in policy.families}
        self._matches: Counter[str] = Counter()
        self._rejections: Counter[str] = Counter()

    @property
    def match_counts(self) -> dict[str, int]:
        return dict(sorted(self._matches.items()))

    @property
    def rejection_counts(self) -> dict[str, int]:
        return dict(sorted(self._rejections.items()))

    def process(self, batch: list[MiningItem]) -> list[MiningItem]:
        return [result for item in batch if (result := self.match_item(item)) is not None]

    def match_item(self, item: MiningItem) -> MiningItem | None:
        tokens = item.tokens
        if tokens is None:
            self._rejections["no_tokens"] += 1
            return None
        if not validate_token_features(item.text, tokens):
            self._rejections["invalid_tokens"] += 1
            return None
        children = normalized_children_by_head(tokens)
        root_selection = select_syntax_root(tokens)
        if root_selection is None:
            self._rejections["invalid_root"] += 1
            return None
        root = root_selection.token
        first = next((token for token in tokens if not token.is_space), None)
        if first is not None and first.dep == "mark" and first.head == root.i:
            # "Although ...": a subordinate clause with no main clause is not a pattern.
            self._rejections["subordinate_fragment"] += 1
            return None
        for family in (f for f in self._policy.families if f.enabled):
            spans = self._match_family(family.id, item.text, tokens, children, root.i)
            if spans is None:
                continue
            result = self._build(item, family.id, spans, root.i, children)
            if result is not None:
                self._matches[family.id] += 1
                return result
        self._rejections["no_family_match"] += 1
        return None

    def _match_family(
        self,
        family: str,
        text: str,
        tokens: tuple[TokenFeature, ...],
        children: dict[int, tuple[int, ...]],
        root_index: int,
    ) -> dict[str, tuple[int, int]] | None:
        root = tokens[root_index]
        direct = [tokens[index] for index in children[root_index]]
        subject = next((token for token in direct if token.dep in {"nsubj", "nsubjpass"}), None)
        subject_scope = frozenset(subtree_indices(children, subject.i)) if subject else frozenset()
        if family == "hybrid_reporting_spine":
            if self._reporting.extractability_reason(text, tokens) != "subject_too_long":
                return None
            if root.lemma.casefold() not in self._reporting_verbs.all_lemmas or subject is None:
                return None
            clause = next((token for token in direct if token.dep in {"ccomp", "acl"}), None)
            if clause is None:
                return None
            start, end = _span(tokens, children, clause.i)
            marker = next(
                (
                    token
                    for token in tokens
                    if token.dep == "mark"
                    and token.lemma.casefold() == "that"
                    and start <= token.start < end
                ),
                None,
            )
            if marker is not None and marker.start == start:
                start = _trim_left(text, marker.end, end)
            return {"X": _span(tokens, children, subject.i), "Y": (start, end)}

        if family == "hybrid_active_modified":
            if root.pos != "VERB" or any(token.tag == "MD" for token in direct):
                return None
            if subject is None or subject.dep != "nsubj":
                return None
            closed = self._closed_verb_spans(text, tokens, children, root, direct, subject)
            if closed is not None:
                return closed
            direct_object = next((token for token in direct if token.dep in {"dobj", "obj"}), None)
            if direct_object is None:
                return None
            adverb = any(
                token.dep == "advmod" and token.pos == "ADV" and token.start > subject.start
                for token in direct
            )
            phrase = next(
                (
                    tokens[child]
                    for token in direct
                    if token.dep in {"prep", "agent"} and token.start > direct_object.start
                    for child in children[token.i]
                    if tokens[child].dep == "pobj"
                ),
                None,
            )
            if not adverb and phrase is None:
                return None
            spans = {
                "X": _span(tokens, children, subject.i),
                "Y": _span(tokens, children, direct_object.i),
            }
            if phrase is not None:
                spans["Z"] = _span(tokens, children, phrase.i)
            return spans

        if family == "hybrid_passive_academic":
            if root.tag != "VBN" or not any(token.dep == "auxpass" for token in direct):
                return None
            if subject is None:
                # Some English parses attach nsubjpass outside the finite root.
                subject = next((token for token in tokens if token.dep == "nsubjpass"), None)
            subject_scope = (
                frozenset(subtree_indices(children, subject.i)) if subject else frozenset()
            )
            fixed_lead_span = _fixed_lead_prefix(text, self._fixed_lead_ins)
            method = _passive_method(
                tokens,
                children,
                root_index,
                subject_scope,
                ignore_before=fixed_lead_span[1] if fixed_lead_span is not None else None,
            )
            if subject is None or method is None:
                return None
            return {"X": _span(tokens, children, subject.i), "Y": method}

        if family == "hybrid_extraposed_it":
            if root.pos != "AUX" or subject is None or subject.lemma.casefold() != "it":
                return None
            predicate = next((token for token in direct if token.dep in {"acomp", "attr"}), None)
            clause = next((token for token in direct if token.dep in {"xcomp", "ccomp"}), None)
            if clause is None and predicate is not None:
                # spaCy often attaches the clause to the adjective: "It is unclear whether ...".
                clause = next(
                    (
                        tokens[index]
                        for index in children[predicate.i]
                        if tokens[index].dep in {"xcomp", "ccomp"}
                    ),
                    None,
                )
            if predicate is None or clause is None:
                return None
            if clause.tag == "VBG":
                # Only the fixed "worth + V-ing" is a pattern; "It was busy modelling" is not.
                if predicate.lemma.casefold() != "worth":
                    return None
                content_clause = next(
                    (tokens[index] for index in children[clause.i] if tokens[index].dep == "ccomp"),
                    None,
                )
                if content_clause is not None:
                    span = _span(tokens, children, content_clause.i)
                    return {"X": _without_marker(text, tokens, span)}
            objects = [
                tokens[index]
                for index in children[clause.i]
                if tokens[index].dep in {"dobj", "obj", "attr", "pobj"}
            ]
            if objects:
                target = objects[-1]
                return {"X": _span(tokens, children, target.i)}
            return {"X": _without_marker(text, tokens, _span(tokens, children, clause.i))}

        if family == "hybrid_copular_definitional":
            if root.lemma.casefold() not in {"be", "remain", "become"} or subject is None:
                return None
            predicate = next((token for token in direct if token.dep in {"attr", "acomp"}), None)
            if predicate is None:
                return self._meta_clause_spans(text, tokens, children, direct, subject)
            meta = _meta_complement(tokens, children, subject.i, self._policy)
            left = meta or _span(tokens, children, subject.i)
            return {"X": left, "Y": _span(tokens, children, predicate.i)}

        if family == "hybrid_discourse_gap":
            lemmas = {token.lemma.casefold() for token in tokens}
            if not lemmas.intersection(_GAP_TRIGGERS):
                return None
            subject_index = subject.i if subject is not None else -1
            complement = next(
                (
                    tokens[index]
                    for index in subtree_indices(children, root_index)
                    if tokens[index].dep in {"pobj", "dobj", "obj", "attr", "acomp"}
                    and tokens[index].i != subject_index
                ),
                None,
            )
            if complement is None:
                complement = next(
                    (token for token in tokens if token.dep in {"pobj", "dobj", "obj"}), None
                )
            if complement is None:
                return None
            return {"X": _span(tokens, children, complement.i)}

        if family == "hybrid_participial_lead_in":
            lead = next(
                (token for token in direct if token.dep == "advcl" and token.tag in {"VBG", "VBN"}),
                None,
            )
            if lead is None or subject is None or lead.start > subject.start:
                return None
            if not any(
                text[token.start : token.end] == "," and lead.end <= token.start < subject.start
                for token in tokens
            ):
                return None
            lead_target = _lead_object(tokens, children, lead.i)
            object_token = next(
                (token for token in direct if token.dep in {"dobj", "obj", "attr", "acomp"}), None
            )
            if lead_target is None or object_token is None:
                return None
            return {
                "X": lead_target,
                "Y": _span(tokens, children, subject.i),
                "Z": _span(tokens, children, object_token.i),
            }

        if family == "hybrid_comparative_correlation":
            markers = {token.lemma.casefold() for token in tokens}
            if root.lemma.casefold() not in _COMPARATIVE_ROOTS and not markers.intersection(
                _COMPARATIVE_MARKERS
            ):
                return None
            if subject is None:
                return None
            direct_object = next((token for token in direct if token.dep in {"dobj", "obj"}), None)
            object_scope = (
                frozenset(subtree_indices(children, direct_object.i))
                if direct_object is not None
                else frozenset()
            )
            comparison = next(
                (
                    tokens[index]
                    for index in subtree_indices(children, root_index)
                    if index not in subject_scope
                    and index not in object_scope
                    and tokens[index].dep in {"pobj", "obl"}
                    and tokens[tokens[index].head].lemma.casefold() in {"than", "to", "with"}
                ),
                None,
            )
            if direct_object is None and comparison is None:
                return None
            spans = {"X": _span(tokens, children, subject.i)}
            if direct_object is not None:
                spans["Y"] = _span(tokens, children, direct_object.i)
            if comparison is not None:
                spans["Z" if "Y" in spans else "Y"] = _span(tokens, children, comparison.i)
            return spans
        return None

    def _closed_verb_spans(
        self,
        text: str,
        tokens: tuple[TokenFeature, ...],
        children: dict[int, tuple[int, ...]],
        root: TokenFeature,
        direct: list[TokenFeature],
        subject: TokenFeature,
    ) -> dict[str, tuple[int, int]] | None:
        """Raising verbs with `to` + verb, and intransitive verbs with one fixed preposition."""
        lemma = root.lemma.casefold()
        subject_span = _span(tokens, children, subject.i)
        idiom = self._idiom_match(tokens, children, root, direct)
        if idiom is not None:
            return {"X": subject_span, "Y": _span(tokens, children, idiom[1].i)}
        if lemma in self._infinitive_verbs:
            clause = next((token for token in direct if token.dep == "xcomp"), None)
            if clause is None:
                return None
            marker = next(
                (
                    tokens[index]
                    for index in children[clause.i]
                    if tokens[index].dep == "aux" and tokens[index].lemma.casefold() == "to"
                ),
                None,
            )
            if marker is None or marker.start < root.start:
                return None
            _, end = _span(tokens, children, clause.i)
            clause_object = next(
                (
                    tokens[index]
                    for index in children[clause.i]
                    if tokens[index].dep in {"dobj", "obj"}
                ),
                None,
            )
            if clause_object is not None:
                return {"X": subject_span, "Y": _span(tokens, children, clause_object.i)}
            return {"X": subject_span, "Y": (_trim_left(text, marker.end, end), end)}
        preposition = self._preposition_verbs.get(lemma)
        if preposition is None or any(token.dep in {"dobj", "obj"} for token in direct):
            return None
        phrase = next(
            (
                tokens[child]
                for token in direct
                if token.dep == "prep" and token.lemma.casefold() == preposition
                for child in children[token.i]
                if tokens[child].dep == "pobj"
            ),
            None,
        )
        if phrase is None:
            return None
        return {"X": subject_span, "Y": _span(tokens, children, phrase.i)}

    def _idiom_match(
        self,
        tokens: tuple[TokenFeature, ...],
        children: dict[int, tuple[int, ...]],
        root: TokenFeature,
        direct: list[TokenFeature],
    ) -> tuple[TokenFeature, TokenFeature] | None:
        """A fixed verb + noun + preposition idiom: the noun stays in the frame, not in a slot."""
        lemma = root.lemma.casefold()
        for verb, noun, preposition in self._idioms:
            if lemma != verb:
                continue
            noun_token = next(
                (
                    token
                    for token in direct
                    if token.dep in {"dobj", "obj"} and token.lemma.casefold() == noun
                ),
                None,
            )
            if noun_token is None:
                continue
            candidates = [*direct, *(tokens[index] for index in children[noun_token.i])]
            target = next(
                (
                    tokens[child]
                    for token in candidates
                    if token.dep == "prep" and token.lemma.casefold() == preposition
                    for child in children[token.i]
                    if tokens[child].dep == "pobj"
                ),
                None,
            )
            if target is not None:
                return noun_token, target
        return None

    def _meta_clause_spans(
        self,
        text: str,
        tokens: tuple[TokenFeature, ...],
        children: dict[int, tuple[int, ...]],
        direct: list[TokenFeature],
        subject: TokenFeature,
    ) -> dict[str, tuple[int, int]] | None:
        """`Another limitation is that ...`: a Meta-NP subject whose complement is a clause."""
        heads = {head.casefold() for head in self._policy.meta_np["heads"]}
        clause = next((token for token in direct if token.dep in {"ccomp", "xcomp"}), None)
        if clause is None or subject.pos != "NOUN" or subject.lemma.casefold() not in heads:
            return None
        clause_span = _span(tokens, children, clause.i)
        if clause.dep == "xcomp":
            marker = next(
                (
                    tokens[index]
                    for index in children[clause.i]
                    if tokens[index].dep == "aux" and tokens[index].lemma.casefold() == "to"
                ),
                None,
            )
            if marker is None:
                return None
            clause_span = (_trim_left(text, marker.end, clause_span[1]), clause_span[1])
        else:
            clause_span = _without_marker(text, tokens, clause_span)
        if not any(tokens[index].dep == "prep" for index in children[subject.i]):
            return {"X": clause_span}
        owner = _meta_complement(tokens, children, subject.i, self._policy)
        if owner is None:
            return None
        return {"X": owner, "Y": clause_span}

    def _build(
        self,
        item: MiningItem,
        family_id: str,
        spans: dict[str, tuple[int, int]],
        root_index: int,
        children: dict[int, tuple[int, ...]],
    ) -> MiningItem | None:
        tokens = item.tokens
        assert tokens is not None
        family = self._families[family_id]
        spans = {
            name: _balance_parentheses(item.text, _extend_following_citation(item.text, start, end))
            for name, (start, end) in spans.items()
        }
        fixed_lead = _fixed_lead_prefix(item.text, self._fixed_lead_ins)
        if fixed_lead is not None and spans:
            first_name = min(spans, key=lambda name: spans[name])
            start, end = spans[first_name]
            if fixed_lead[0] <= start and end <= fixed_lead[1]:
                self._rejections["purity_fixed_lead_slot"] += 1
                return None
            if start < fixed_lead[1] and end > fixed_lead[0]:
                spans[first_name] = (fixed_lead[1], end)
        ordered = sorted(spans.items(), key=lambda pair: pair[1])
        if not _valid_spans(item.text, ordered):
            self._rejections["frame_invariant"] += 1
            return None
        if len(ordered) > 3:
            self._rejections["too_many_slots"] += 1
            return None
        # Frames name slots by reading order; a fronted phrase becomes [X], never "In [Y], [X]".
        ordered = [(name, span) for name, (_, span) in zip("XYZ", ordered, strict=False)]
        core = _core_range(item.text, tokens, ordered, root_index, children, self._fixed_lead_ins)
        if core is None:
            self._rejections["lead_too_long"] += 1
            return None
        low, high, content_from = core
        if not _trigger_in_core(family_id, tokens, root_index, low, high, ordered):
            self._rejections["trigger_outside_core"] += 1
            return None
        literal_indices = [
            token.i
            for token in tokens
            if low <= token.start
            and token.end <= high
            and not any(start <= token.start and token.end <= end for _, (start, end) in ordered)
            and not token.is_space
            and not _PUNCT.fullmatch(item.text[token.start : token.end])
        ]
        if any(_empty_slot(tokens, start, end, item.text) for _, (start, end) in ordered):
            self._rejections["purity_empty_slot"] += 1
            return None
        if any(_symbolic_slot(item.text[start:end]) for _, (start, end) in ordered):
            self._rejections["purity_symbolic_slot"] += 1
            return None
        if any(_unbalanced_slot(item.text[start:end]) for _, (start, end) in ordered):
            self._rejections["purity_unbalanced_slot"] += 1
            return None
        if _slot_cuts_modifier(tokens, ordered):
            self._rejections["purity_slot_cuts_modifier"] += 1
            return None
        if any(tokens[index].pos == "PROPN" for index in literal_indices):
            self._rejections["purity_proper_noun"] += 1
            return None
        literal_text = " ".join(item.text[tokens[i].start : tokens[i].end] for i in literal_indices)
        if (
            re.search(r"\d", literal_text)
            or _CITATION.search(literal_text)
            or re.search(r"\b[A-Z]{2,}\b", literal_text)
        ):
            self._rejections["purity_sensitive_literal"] += 1
            return None
        content = [
            tokens[index]
            for index in literal_indices
            if tokens[index].pos in {"NOUN", "VERB", "ADJ", "ADV"}
            and tokens[index].start >= content_from
        ]
        meta_heads = {head.casefold() for head in self._policy.meta_np["heads"]}
        head_noun = any(
            token.pos == "NOUN" and token.lemma.casefold() in meta_heads for token in content
        )
        idiom = (
            self._idiom_match(
                tokens, children, tokens[root_index], [tokens[i] for i in children[root_index]]
            )
            if family_id == "hybrid_active_modified"
            else None
        )
        idiom_noun = idiom[0].i if idiom is not None else None
        literal_nouns = [
            token
            for token in content
            if token.pos == "NOUN"
            and token.lemma.casefold() not in meta_heads
            and token.i != idiom_noun
        ]
        if len(literal_nouns) > self._policy.max_literal_nouns:
            self._rejections["purity_literal_noun"] += 1
            return None
        if (
            len(content) < max(family.min_content_tokens, self._policy.min_fixed_content_tokens)
            or not any(token.pos in {"VERB", "ADJ"} for token in content)
            and not head_noun
        ):
            self._rejections["purity_content_minimum"] += 1
            return None
        frame = _render(item.text, ordered, low, high)
        if _joined_heading(tokens, ordered, low, high, item.text):
            self._rejections["purity_heading_join"] += 1
            return None
        if frame.count("(") != frame.count(")") or re.search(
            r"[;:\[\]]", re.sub(r"\[[XYZ]\]", " ", frame)
        ):
            self._rejections["purity_unbalanced_punctuation"] += 1
            return None
        if HYBRID_SLOT_BOUNDARY.search(frame):
            self._rejections["purity_slot_boundary_punctuation"] += 1
            return None
        if hybrid_frame_has_dangling_tail(frame, self._policy):
            self._rejections["purity_dangling_tail"] += 1
            return None
        if hybrid_frame_has_abbreviation(frame, self._policy):
            self._rejections["purity_abbreviation"] += 1
            return None
        if len(re.sub(r"\[[XYZ]\]", " ", frame).split()) > self._policy.max_literal_words:
            self._rejections["purity_frame_too_long"] += 1
            return None
        safety_key = f"construction={family_id}:{self._policy.version}:" + "0" * 64
        if not is_safe_hybrid_frame(frame, self._policy, safety_key):
            self._rejections["purity_writer_safety"] += 1
            return None
        root = tokens[root_index]
        root_children = set(children[root_index])
        tense = SlotAbstractor._syntax_tense(tokens, root_index, root_children)
        modality = next(
            (
                item.text[tokens[index].start : tokens[index].end]
                for index in sorted(root_children | {root_index})
                if tokens[index].tag == "MD"
            ),
            None,
        )
        subject_token = next(
            (
                tokens[index]
                for index in children[root_index]
                if tokens[index].dep in {"nsubj", "nsubjpass"}
            ),
            None,
        )
        if subject_token is None:
            ownership = Ownership.UNCLEAR
        else:
            subject_start, subject_end = _span(tokens, children, subject_token.i)
            ownership = infer_ownership(
                item.text[subject_start:subject_end],
                item.previous_text,
                self._ownership_policy,
                item.section_code,
            )
        slot_defs: dict[str, SlotDefinition] = {}
        for name, (start, end) in ordered:
            contained = [token for token in tokens if start <= token.start and token.end <= end]
            contained_ids = {token.i for token in contained}
            heads = [token for token in contained if token.head not in contained_ids]
            finite = any(
                token.pos in {"VERB", "AUX"}
                and ("VerbForm=Fin" in token.morph or token.tag in {"VBD", "VBP", "VBZ", "MD"})
                for token in heads
            )
            slot_type = SlotType.CLAUSE if finite else SlotType.NOUN_PHRASE
            slot_defs[name] = _definition(slot_type, item.text[start:end])
        occurrence = ExtractionOccurrence(
            sentence_id=item.source_sentence_ids[0],
            sentence_start=item.char_start,
            sentence_end=item.char_start + len(item.text),
            slot_spans={
                name: (item.char_start + start, item.char_start + end)
                for name, (start, end) in ordered
            },
        )
        root_start = root.start - low
        for name, (start, end) in ordered:
            if end <= root.start:
                root_start += len(f"[{name}]") - (end - start)
        root_surface = item.text[root.start : root.end]
        if frame[root_start : root_start + len(root_surface)] == root_surface:
            skeleton = frame[:root_start] + root.lemma + frame[root_start + len(root_surface) :]
        else:
            skeleton = frame
        # The final period only says whether the core reached the sentence end, so it must not
        # split one pattern into two clusters. The displayed frame keeps it.
        skeleton = skeleton.rstrip().removesuffix(".").rstrip()
        return replace(
            item,
            text=frame,
            slots=slot_defs,
            occurrences=[occurrence],
            tense=tense,
            modality=modality,
            ownership=ownership,
            cluster_key=None,
            construction_id=family_id,
            construction_version=self._policy.version,
            canonical_skeleton=skeleton,
        )


def _span(
    tokens: tuple[TokenFeature, ...], children: dict[int, tuple[int, ...]], root: int
) -> tuple[int, int]:
    start, end = subtree_span(tokens, children, root)
    edges = [
        token
        for token in tokens
        if start <= token.start and token.end <= end and not token.is_space
    ]
    while edges and edges[0].pos == "PUNCT":
        start = edges.pop(0).end
    while edges and edges[-1].pos == "PUNCT":
        end = edges.pop().start
    return start, end


def _balance_parentheses(text: str, span: tuple[int, int]) -> tuple[int, int]:
    """Keep a slot's closing parenthesis (and the dot before it) so a citation is not cut."""
    start, end = span
    segment = text[start:end]
    if segment.count("(") > segment.count(")"):
        probe = end
        while probe < len(text) and text[probe] in ".)":
            probe += 1
            if text[start:probe].count("(") == text[start:probe].count(")"):
                return start, probe
    elif segment.count(")") > segment.count("(") and start > 0 and text[start - 1] == "(":
        return start - 1, end
    return span


def _without_marker(
    text: str, tokens: tuple[TokenFeature, ...], span: tuple[int, int]
) -> tuple[int, int]:
    """Keep `that` / `whether` outside a clause slot so the frame stays grammatical."""
    start, end = span
    first = next((token for token in tokens if token.start == start), None)
    if first is not None and first.dep == "mark":
        return _trim_left(text, first.end, end), end
    return span


def _trim_left(text: str, start: int, end: int) -> int:
    while start < end and text[start].isspace():
        start += 1
    return start


def _meta_complement(
    tokens: tuple[TokenFeature, ...],
    children: dict[int, tuple[int, ...]],
    root: int,
    policy: HybridConstructionsPolicy,
) -> tuple[int, int] | None:
    configured = {head.casefold() for head in policy.meta_np["heads"]}
    connectors = {connector.casefold() for connector in policy.meta_np["connectors"]}
    candidates: set[tuple[int, int]] = set()
    for index in subtree_indices(children, root):
        token = tokens[index]
        if token.lemma.casefold() not in configured:
            continue
        for child_index in children[index]:
            connector = tokens[child_index]
            if (
                connector.dep not in {"prep", "case"}
                or connector.lemma.casefold() not in connectors
            ):
                continue
            complement = next(
                (
                    tokens[grandchild]
                    for grandchild in children[connector.i]
                    if tokens[grandchild].dep in {"pobj", "obj"}
                ),
                None,
            )
            if complement is not None:
                candidates.add(_span(tokens, children, complement.i))
    return next(iter(candidates)) if len(candidates) == 1 else None


def _passive_method(
    tokens: tuple[TokenFeature, ...],
    children: dict[int, tuple[int, ...]],
    root: int,
    exclude: frozenset[int] = frozenset(),
    *,
    ignore_before: int | None = None,
) -> tuple[int, int] | None:
    for index in subtree_indices(children, root):
        if index in exclude:
            continue
        token = tokens[index]
        if ignore_before is not None and token.start < ignore_before:
            continue
        if token.dep in {"agent", "prep"}:
            target = next(
                (
                    tokens[child]
                    for child in children[token.i]
                    if tokens[child].dep in {"pobj", "obj"}
                ),
                None,
            )
            if target is not None:
                return _span(tokens, children, target.i)
        if (
            token.lemma.casefold() == "use"
            and token.tag == "VBG"
            and token.dep in {"xcomp", "advcl"}
        ):
            target = next(
                (
                    tokens[child]
                    for child in children[token.i]
                    if tokens[child].dep in {"dobj", "obj"}
                ),
                None,
            )
            if target is not None:
                return _span(tokens, children, target.i)
    return None


def _lead_object(
    tokens: tuple[TokenFeature, ...], children: dict[int, tuple[int, ...]], lead: int
) -> tuple[int, int] | None:
    for index in subtree_indices(children, lead):
        token = tokens[index]
        if token.dep == "agent":
            target = next(
                (
                    tokens[child]
                    for child in children[token.i]
                    if tokens[child].dep in {"pobj", "obj"}
                ),
                None,
            )
            if target is not None:
                return _span(tokens, children, target.i)
        if token.dep in {"prep", "dobj", "obj"}:
            target = next(
                (
                    tokens[child]
                    for child in children[token.i]
                    if tokens[child].dep in {"pobj", "obj"}
                ),
                token if token.dep in {"dobj", "obj"} else None,
            )
            if target is not None:
                return _span(tokens, children, target.i)
    return None


def _valid_spans(text: str, spans: list[tuple[str, tuple[int, int]]]) -> bool:
    if not spans:
        return False
    previous: int | None = None
    for _, (start, end) in spans:
        if not 0 <= start < end <= len(text) or (previous is not None and start < previous):
            return False
        if previous is not None and not text[previous:start].strip():
            return False
        previous = end
    return True


def _fixed_lead_prefix(text: str, leads: list[str]) -> tuple[int, int] | None:
    """Return an approved comma-terminated lead at the start of a sentence."""
    for lead in leads:
        words = re.escape(lead.strip()).replace(r"\ ", r"\s+")
        match = re.match(rf"^\s*{words}\s*,\s*", text, re.IGNORECASE)
        if match is not None:
            return match.start(), match.end()
    return None


def _slot_cuts_modifier(
    tokens: tuple[TokenFeature, ...], ordered: list[tuple[str, tuple[int, int]]]
) -> bool:
    """Reject a slot edge that separates a modifier from its syntactic head."""
    modifier_deps = {"amod", "compound", "det", "nummod", "poss"}
    for _, (start, end) in ordered:
        inside = {token.i for token in tokens if start <= token.start and token.end <= end}
        for token in tokens:
            if token.dep not in modifier_deps or token.head == token.i:
                continue
            if (token.i in inside) != (token.head in inside):
                return True
    return False


def _joined_heading(
    tokens: tuple[TokenFeature, ...],
    ordered: list[tuple[str, tuple[int, int]]],
    low: int,
    high: int,
    text: str,
) -> bool:
    """Detect a capitalized sentence-initial function word glued after a slot."""
    first_slot_end = ordered[0][1][1]
    return any(
        first_slot_end <= token.start < high
        and token.start >= low
        and token.pos in {"ADP", "SCONJ", "DET", "PRON"}
        and (surface := text[token.start : token.end])[:1].isupper()
        and surface[1:].islower()
        for token in tokens
        if not token.is_space
    )


def _render(
    text: str,
    spans: list[tuple[str, tuple[int, int]]],
    low: int = 0,
    high: int | None = None,
) -> str:
    output = text
    for name, (start, end) in reversed(spans):
        output = output[:start] + f"[{name}]" + output[end:]
    removed = sum(
        (end - start) - len(f"[{name}]")
        for name, (start, end) in spans
        if end <= (high if high is not None else len(text))
    )
    stop = (high if high is not None else len(text)) - removed
    return output[low:stop].strip()


def _trigger_in_core(
    family_id: str,
    tokens: tuple[TokenFeature, ...],
    root_index: int,
    low: int,
    high: int,
    ordered: list[tuple[str, tuple[int, int]]],
) -> bool:
    """The defining word must stay in the frame's literal text, not inside a slot."""
    inside = {
        token.lemma.casefold()
        for token in tokens
        if low <= token.start
        and token.end <= high
        and not any(start <= token.start and token.end <= end for _, (start, end) in ordered)
    }
    if family_id == "hybrid_discourse_gap":
        return bool(inside & _GAP_TRIGGERS)
    if family_id == "hybrid_comparative_correlation":
        return tokens[root_index].lemma.casefold() in _COMPARATIVE_ROOTS or bool(
            inside & _COMPARATIVE_MARKERS
        )
    return True


def _unbalanced_slot(text: str) -> bool:
    """A slot that opens or closes a parenthesis alone was cut inside a citation or formula."""
    return text.count("(") != text.count(")")


def _empty_slot(tokens: tuple[TokenFeature, ...], start: int, end: int, text: str) -> bool:
    """A slot made only of grammatical function words carries no content to abstract."""
    inside = [
        token
        for token in tokens
        if start <= token.start
        and token.end <= end
        and any(char.isalnum() for char in text[token.start : token.end])
    ]
    return not inside or all(
        token.pos in {"PRON", "DET", "ADP", "CCONJ", "SCONJ", "PART", "AUX"} for token in inside
    )


def _symbolic_slot(text: str) -> bool:
    """A slot holding a formula is damaged extraction output, not a noun phrase."""
    return any(
        0x1D400 <= ord(char) <= 0x1D7FF
        or (unicodedata.category(char) == "Sm" and char not in _SLOT_SAFE_MATH_SIGNS)
        for char in text
    )


def _light_end(
    tokens: tuple[TokenFeature, ...], children: dict[int, tuple[int, ...]], token: TokenFeature
) -> int:
    """End of a predicate-adjacent word plus its own light modifiers, never its clauses."""
    return max(
        [token.end]
        + [
            tokens[child].end
            for child in children[token.i]
            if tokens[child].dep in _LIGHT_CHILD_DEPS
        ]
    )


def _phrase_tail_end(text: str, tokens: tuple[TokenFeature, ...], start: int) -> int:
    """Extend ``start`` over phrase tokens up to the first clause boundary."""
    end = start
    count = 0
    for token in tokens:
        if token.start < start or token.is_space:
            continue
        surface = text[token.start : token.end]
        if (
            token.dep in _CLAUSE_DEPS
            or token.pos in {"SCONJ", "CCONJ"}
            or (token.pos in {"VERB", "AUX"} and token.dep not in {"amod", "compound"})
            or token.tag in {"WDT", "WP", "WRB", "TO"}
            or (token.pos == "PUNCT" and surface not in {".", "?", "!"})
        ):
            break
        if token.pos == "PUNCT":
            continue
        count += 1
        if count > _TRAILING_MAX_TOKENS:
            return start
        end = token.end
    return end


def _drop_dangling_tail(text: str, tokens: tuple[TokenFeature, ...], floor: int, high: int) -> int:
    """Cut trailing prepositions after ``floor``; their objects were left outside the core."""
    for token in reversed(tokens):
        if token.end > high or token.is_space or token.pos == "PUNCT":
            continue
        if token.start < floor or token.tag not in {"IN", "TO"} or token.dep == "prt":
            break
        high = len(text[: token.start].rstrip(" ,"))
    return high


def _core_range(
    text: str,
    tokens: tuple[TokenFeature, ...],
    ordered: list[tuple[str, tuple[int, int]]],
    root_index: int,
    children: dict[int, tuple[int, ...]],
    fixed_lead_ins: list[str] | None = None,
) -> tuple[int, int, int] | None:
    """Return (low, high, content_from): the pattern core of the main clause.

    The core runs from the main-clause subject (or a slot-bearing lead) to the last slot or
    predicate word. Trailing clauses and slot-free lead adjuncts are dropped; a short
    comma-terminated discourse lead stays as literal text but does not count as pattern content.
    """
    root = tokens[root_index]
    slot_start, slot_end = ordered[0][1][0], ordered[-1][1][1]
    direct = [tokens[index] for index in children[root_index]]
    subject = next((token for token in direct if token.dep in {"nsubj", "nsubjpass"}), None)
    main_start = (
        min(_span(tokens, children, subject.i)[0], root.start)
        if subject is not None
        else min(slot_start, root.start)
    )
    comma = text.rfind(",", 0, main_start)
    main_start = min(
        [main_start]
        + [
            token.start
            for token in direct
            if token.dep in _LIGHT_DEPS and comma < token.start < main_start
        ]
    )
    # Trailing side: predicate words, then phrase material up to the first clause boundary.
    high = max(slot_end, root.end)
    for token in direct:
        if token.dep in _LIGHT_DEPS:
            high = max(high, _light_end(tokens, children, token))
    high = _drop_dangling_tail(text, tokens, high, _phrase_tail_end(text, tokens, high))
    if text[high:].strip() in {".", "?", "!"}:
        high = len(text.rstrip())
    # Leading side.
    prefix_tokens = [
        token
        for token in tokens
        if token.end <= main_start
        and not token.is_space
        and token.pos != "PUNCT"
        and any(char.isalnum() for char in text[token.start : token.end])
    ]
    if not prefix_tokens:
        return main_start, high, main_start
    first_start = prefix_tokens[0].start
    if first_start >= main_start:
        return main_start, high, main_start
    fixed_lead = _fixed_lead_prefix(text, fixed_lead_ins or [])
    if fixed_lead is not None and fixed_lead[1] <= main_start:
        return first_start, high, fixed_lead[1]
    prefix_has_slot = slot_start < main_start
    if prefix_has_slot:
        if len(text[first_start:main_start].split()) > _SLOT_LEAD_MAX_WORDS:
            return None
        return first_start, high, first_start
    is_discourse = (
        text[:main_start].rstrip().endswith(",")
        and len(prefix_tokens) <= _DISCOURSE_LEAD_MAX_TOKENS
        and not any(token.pos in _DISCOURSE_LEAD_BLOCKED_POS for token in prefix_tokens)
    )
    if is_discourse:
        return first_start, high, main_start
    return main_start, high, main_start
