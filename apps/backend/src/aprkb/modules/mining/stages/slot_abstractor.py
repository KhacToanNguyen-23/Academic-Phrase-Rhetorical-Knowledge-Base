"""Conservative regex extraction for reviewed reporting verb constructions."""

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, replace

from aprkb.modules.mining.schemas import Ownership, ProtectedSignal, SlotDefinition, SlotType, Tense
from aprkb.modules.mining.stages.base import ExtractionOccurrence, MiningItem, MiningStage
from aprkb.nlp.features import TokenFeature
from aprkb.nlp.syntax import (
    normalized_children_by_head,
    select_syntax_root,
    subtree_span,
    validate_token_features,
)
from aprkb.policies.schemas import ReportingVerbsPolicy, SlotAbstractionPolicy

_SIGNAL_PATTERNS = {
    ProtectedSignal.CITATION: re.compile(
        r"\[(?:\d+[\s,;–-]*)+\]|\([^()]*\b(?:18|19|20)\d{2}\b[^()]*\)"
    ),
    ProtectedSignal.PERCENTAGE: re.compile(r"\b\d+(?:\.\d+)?\s*%"),
    ProtectedSignal.YEAR: re.compile(r"\b(?:18|19|20)\d{2}\b"),
    ProtectedSignal.NUMBER: re.compile(r"\b\d+(?:\.\d+)?\b"),
    ProtectedSignal.ACRONYM: re.compile(r"\b[A-Z]{2,}\b"),
    ProtectedSignal.NEGATION: re.compile(r"\b(?:not|never|no|neither|nor)\b", re.I),
    ProtectedSignal.MODAL: re.compile(r"\b(?:may|might|could|can|should|would|must)\b", re.I),
    ProtectedSignal.COMPARISON: re.compile(
        r"\b(?:more|less|higher|lower|greater|fewer|than|compared)\b", re.I
    ),
    ProtectedSignal.UNIT: re.compile(
        r"\b(?:ms|s|seconds?|minutes?|hours?|days?|mm|cm|m|km|kg|g|mb|gb)\b", re.I
    ),
}


@dataclass(frozen=True)
class _Located:
    tense: Tense
    surface: str
    subject: tuple[int, int]
    clause: tuple[int, int]
    modifiers: str = ""


class SlotAbstractor(MiningStage):
    name = "slot_abstractor"
    requirement_id = "FR-06.2"

    def __init__(self, verbs: ReportingVerbsPolicy, policy: SlotAbstractionPolicy) -> None:
        self._policy = policy
        self._lemma_to_class = {
            lemma.strip().casefold(): class_name
            for class_name, forms in verbs.classes.items()
            for lemma in forms.lemmas
        }
        self._forms: list[tuple[str, Tense, str]] = []
        for class_name, forms in verbs.classes.items():
            for tense, values in (
                (Tense.PRESENT, forms.present),
                (Tense.PAST, forms.past),
                (Tense.PRESENT_PERFECT, forms.present_perfect),
            ):
                self._forms.extend((form, tense, class_name) for form in values)
        self._forms.sort(key=lambda row: (-len(row[0]), row[0].casefold()))
        self._modifiers = {word.casefold() for word in policy.verb_modifiers}
        self._syntax_fallbacks: Counter[str] = Counter()

    def process(self, batch: list[MiningItem]) -> list[MiningItem]:
        extracted: list[MiningItem] = []
        for item in batch:
            result = self._extract(item)
            if result is not None:
                extracted.append(result)
        return extracted

    @property
    def syntax_fallback_reasons(self) -> dict[str, int]:
        return dict(self._syntax_fallbacks)

    def extractability_reason(
        self, text: str, tokens: tuple[TokenFeature, ...] | None = None
    ) -> str | None:
        """Return why ``text`` cannot be abstracted, or ``None`` when it can."""
        located = self._locate(text, tokens=tokens)
        return located if isinstance(located, str) else None

    def _locate(
        self, text: str, *, tokens: tuple[TokenFeature, ...] | None = None
    ) -> str | _Located:
        """Find verb, subject and clause spans, or return the reason extraction is impossible."""
        if tokens is not None:
            syntax = self._locate_syntax(text, tokens)
            if syntax != "syntax_invalid_tokens":
                return syntax
            self._syntax_fallbacks["syntax_invalid_tokens"] += 1
        return self._locate_regex(text)

    def _locate_regex(self, text: str) -> str | _Located:
        match = self._reporting_match(text)
        if match is None:
            return "no_reporting_verb"
        verb_start, verb_end, tense, verb_class, surface = match
        that = re.match(r"\s+that\b\s*", text[verb_end:], re.I)
        if that is None:
            return "no_that"
        subject_start, subject_end = _trim_span(text, 0, verb_start)
        subject_end = self._peel_modifiers(text, subject_start, subject_end)
        modifiers = " ".join(text[subject_end:verb_start].split())
        if re.search(r"\bdid\b", modifiers, re.I):
            # "did not show" carries the past tense on the auxiliary, not on the verb form.
            tense = Tense.PAST
        clause_start, clause_end = _trim_span(text, verb_end + that.end(), len(text))
        subject_words = re.findall(r"\b[\w'-]+\b", text[subject_start:subject_end])
        clause_words = re.findall(r"\b[\w'-]+\b", text[clause_start:clause_end])
        if not subject_words:
            return "no_subject"
        if len(subject_words) > self._policy.max_subject_words:
            return "subject_too_long"
        if len(clause_words) < self._policy.min_clause_words:
            return "clause_too_short"
        determiner = _determiner_match(
            text[subject_start:subject_end],
            self._policy.own_determiners + self._policy.prior_determiners,
        )
        if determiner is not None:
            noun_start, noun_end = _trim_span(text, subject_start + determiner.end(), subject_end)
            if noun_start == noun_end:
                return "empty_noun_phrase"
        return _Located(
            tense, surface, (subject_start, subject_end), (clause_start, clause_end), modifiers
        )

    def _locate_syntax(self, text: str, tokens: tuple[TokenFeature, ...]) -> str | _Located:
        if not validate_token_features(text, tokens):
            return "syntax_invalid_tokens"
        children = normalized_children_by_head(tokens)
        selection = select_syntax_root(tokens)
        if selection is None:
            return "syntax_invalid_tokens"
        parser_root = next(token for token in tokens if token.dep == "ROOT")
        root = selection.token
        class_name = self._lemma_to_class.get(root.lemma.casefold())
        promoted_subject = selection.promoted_subject_span
        if class_name is None:
            return "no_reporting_verb"
        if any(
            token.dep == "conj" and token.lemma.casefold() in self._lemma_to_class
            for token in tokens
            if token.head == root.i
        ):
            return "coordinated_reporting_verbs"

        subject = next(
            (
                token
                for token in (tokens[index] for index in children[root.i])
                if token.dep in {"nsubj", "nsubjpass", "expl"}
            ),
            parser_root if promoted_subject is not None else None,
        )
        if subject is None:
            return "no_subject"
        if subject.pos not in {"NOUN", "PROPN", "PRON"}:
            return "subject_not_nominal"
        subject_start, subject_end = (
            promoted_subject
            if promoted_subject is not None
            else subtree_span(tokens, children, subject.i)
        )

        that_clause: tuple[int, int, int] | None = None
        for child_index in children[root.i]:
            marker = next(
                (
                    tokens[index]
                    for index in children[child_index]
                    if tokens[index].dep == "mark" and tokens[index].lemma.casefold() == "that"
                ),
                None,
            )
            if marker is not None:
                clause_start, clause_end = subtree_span(tokens, children, child_index)
                that_clause = (marker.end, clause_end, child_index)
                break
        if that_clause is None:
            return "no_that"
        clause_start, clause_end, _ = that_clause
        subject_start, subject_end = _trim_span(text, subject_start, subject_end)
        clause_start, clause_end = _trim_span(text, clause_start, clause_end)

        group_indices = {
            token.i
            for token in tokens
            if subject_end <= token.start < token.end <= root.start
            and token.dep in {"aux", "auxpass", "neg", "advmod"}
        }
        modifiers = " ".join(
            text[tokens[index].start : tokens[index].end] for index in sorted(group_indices)
        )
        tense = self._syntax_tense(tokens, root.i, group_indices)
        subject_words = re.findall(r"\b[\w'-]+\b", text[subject_start:subject_end])
        clause_words = re.findall(r"\b[\w'-]+\b", text[clause_start:clause_end])
        if not subject_words:
            return "no_subject"
        if len(subject_words) > self._policy.max_subject_words:
            return "subject_too_long"
        if len(clause_words) < self._policy.min_clause_words:
            return "clause_too_short"
        determiner = _determiner_match(
            text[subject_start:subject_end],
            self._policy.own_determiners + self._policy.prior_determiners,
        )
        if determiner is not None:
            noun_start, noun_end = _trim_span(text, subject_start + determiner.end(), subject_end)
            if noun_start == noun_end:
                return "empty_noun_phrase"
        return _Located(
            tense,
            text[root.start : root.end],
            (subject_start, subject_end),
            (clause_start, clause_end),
            modifiers,
        )

    @staticmethod
    def _syntax_tense(
        tokens: tuple[TokenFeature, ...], root_index: int, group_indices: set[int]
    ) -> Tense:
        group = [tokens[index] for index in sorted(group_indices)] + [tokens[root_index]]
        lemmas = {token.lemma.casefold() for token in group}
        if "may" in lemmas or lemmas & {"might", "could", "can", "should", "would", "must"}:
            return Tense.PRESENT
        if lemmas & {"has", "have"}:
            return Tense.PRESENT_PERFECT
        finite = [token for token in group if token.tag == "MD" or "VerbForm=Fin" in token.morph]
        if "did" in lemmas or any("Tense=Past" in token.morph for token in finite):
            return Tense.PAST
        if any("Tense=Pres" in token.morph for token in finite):
            return Tense.PRESENT
        return Tense.UNKNOWN

    def _peel_modifiers(self, text: str, start: int, end: int) -> int:
        """Move ``end`` left past trailing negation, modal and emphasis words of the subject."""
        while True:
            match = re.search(r"([A-Za-z]+)\s*$", text[start:end])
            if match is None or match.group(1).casefold() not in self._modifiers:
                return end
            end = _trim_span(text, start, start + match.start())[1]

    def _extract(self, item: MiningItem) -> MiningItem | None:
        located = self._locate(item.text, tokens=item.tokens)
        if isinstance(located, str):
            return None
        tense, surface = located.tense, located.surface
        subject_start, subject_end = located.subject
        clause_start, clause_end = located.clause
        subject = item.text[subject_start:subject_end]

        determiner = _determiner_match(
            item.text[subject_start:subject_end],
            self._policy.own_determiners + self._policy.prior_determiners,
        )
        has_determiner_slot = determiner is not None
        determiner_text = ""
        spans: dict[str, tuple[int, int]] = {}
        slot_defs: dict[str, SlotDefinition] = {}
        if has_determiner_slot:
            if determiner is None:
                return None
            det_span = (subject_start, subject_start + determiner.end())
            determiner_text = item.text[slice(*det_span)].casefold()
            noun_start, noun_end = _trim_span(item.text, det_span[1], subject_end)
            if noun_start == noun_end:
                return None
            spans["X"] = det_span
            spans["Y"] = (noun_start, noun_end)
            spans["Z"] = (clause_start, clause_end)
            det_type = (
                SlotType.DETERMINER_OWN
                if determiner_text in self._policy.own_determiners
                else SlotType.DETERMINER_PRIOR
            )
            slot_defs = {
                "X": _definition(det_type, item.text[slice(*det_span)]),
                "Y": _definition(SlotType.NOUN_PHRASE, item.text[noun_start:noun_end]),
                "Z": _definition(SlotType.CLAUSE, item.text[clause_start:clause_end]),
            }
        else:
            spans["X"] = (subject_start, subject_end)
            spans["Y"] = (clause_start, clause_end)
            slot_defs = {
                "X": _definition(SlotType.NOUN_PHRASE, subject),
                "Y": _definition(SlotType.CLAUSE, item.text[clause_start:clause_end]),
            }

        ownership = self._ownership(item, determiner_text)
        verb = f"{located.modifiers} {surface}" if located.modifiers else surface
        frame_location = self._locate_regex(item.text) if item.tokens is not None else located
        if isinstance(frame_location, _Located):
            frame_verb = (
                f"{frame_location.modifiers} {frame_location.surface}"
                if frame_location.modifiers
                else frame_location.surface
            )
        else:
            frame_verb = verb
        frame = f"[X] [Y] {frame_verb} that [Z]" if "Z" in spans else f"[X] {frame_verb} that [Y]"
        trailing = re.search(r"[.!?]+\s*$", item.text)
        if trailing is not None:
            frame += trailing.group(0).strip()
        occurrence = ExtractionOccurrence(
            sentence_id=item.source_sentence_ids[0],
            sentence_start=item.char_start,
            sentence_end=item.char_start + len(item.text),
            slot_spans={
                name: (item.char_start + start, item.char_start + end)
                for name, (start, end) in spans.items()
            },
        )
        binding = "\x1f".join(
            f"{name}:{re.sub(r'\s+', ' ', item.text[start:end]).strip().casefold()}"
            for name, (start, end) in sorted(spans.items())
        )
        return replace(
            item,
            text=frame,
            slots=slot_defs,
            occurrences=[occurrence],
            tense=tense,
            ownership=ownership,
            cluster_key=None,
            confidence=None,
            slot_binding_fingerprint=hashlib.sha256(binding.encode("utf-8")).hexdigest(),
        )

    def _reporting_match(self, text: str) -> tuple[int, int, Tense, str, str] | None:
        for form, tense, class_name in self._forms:
            pattern = re.compile(rf"(?<!\w){re.escape(form)}(?!\w)", re.I)
            match = pattern.search(text)
            if match is not None:
                return match.start(), match.end(), tense, class_name, match.group(0)
        return None

    def _ownership(self, item: MiningItem, determiner: str) -> Ownership:
        if determiner in self._policy.prior_determiners:
            return Ownership.PRIOR
        if determiner in self._policy.own_determiners:
            if item.previous_text and (
                _CITATION_PATTERN.search(item.previous_text)
                or re.search(
                    r"\b(?:prior|previous|earlier|other)\s+(?:study|studies|research|work|author)s?\b|\b(?:prior|previous|earlier)\s+research\b",
                    item.previous_text,
                    re.I,
                )
            ):
                return Ownership.UNCLEAR
            return Ownership.OWN
        return Ownership.UNCLEAR


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


_CITATION_PATTERN = re.compile(r"\[(?:\d+[\s,;–-]*)+\]|\([^()]*\b(?:18|19|20)\d{2}\b[^()]*\)")


def _determiner_match(subject: str, cues: list[str]) -> re.Match[str] | None:
    ordered_cues = sorted(cues, key=len, reverse=True)
    if not ordered_cues:
        return None
    pattern = r"\s*(?:" + "|".join(re.escape(cue) for cue in ordered_cues) + r")\b"
    return re.match(pattern, subject, re.I)


def _definition(slot_type: SlotType, text: str) -> SlotDefinition:
    signals = [signal for signal, pattern in _SIGNAL_PATTERNS.items() if pattern.search(text)]
    return SlotDefinition(type=slot_type, signals=signals)
