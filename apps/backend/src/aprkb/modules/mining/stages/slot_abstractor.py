"""Conservative regex extraction for reviewed reporting verb constructions."""

import hashlib
import re
from dataclasses import replace

from aprkb.modules.mining.schemas import Ownership, ProtectedSignal, SlotDefinition, SlotType, Tense
from aprkb.modules.mining.stages.base import ExtractionOccurrence, MiningItem, MiningStage
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


class SlotAbstractor(MiningStage):
    name = "slot_abstractor"
    requirement_id = "FR-06.2"

    def __init__(self, verbs: ReportingVerbsPolicy, policy: SlotAbstractionPolicy) -> None:
        self._policy = policy
        self._forms: list[tuple[str, Tense, str]] = []
        for class_name, forms in verbs.classes.items():
            for tense, values in (
                (Tense.PRESENT, forms.present),
                (Tense.PAST, forms.past),
                (Tense.PRESENT_PERFECT, forms.present_perfect),
            ):
                self._forms.extend((form, tense, class_name) for form in values)
        self._forms.sort(key=lambda row: (-len(row[0]), row[0].casefold()))

    def process(self, batch: list[MiningItem]) -> list[MiningItem]:
        extracted: list[MiningItem] = []
        for item in batch:
            result = self._extract(item)
            if result is not None:
                extracted.append(result)
        return extracted

    def _extract(self, item: MiningItem) -> MiningItem | None:
        match = self._reporting_match(item.text)
        if match is None:
            return None
        verb_start, verb_end, tense, verb_class, surface = match
        that = re.match(r"\s+that\b\s*", item.text[verb_end:], re.I)
        if that is None:
            return None
        subject_start, subject_end = _trim_span(item.text, 0, verb_start)
        clause_start = verb_end + that.end()
        clause_start, clause_end = _trim_span(item.text, clause_start, len(item.text))
        subject = item.text[subject_start:subject_end]
        subject_words = re.findall(r"\b[\w'-]+\b", subject)
        clause_words = re.findall(r"\b[\w'-]+\b", item.text[clause_start:clause_end])
        if not subject_words or len(subject_words) > self._policy.max_subject_words:
            return None
        if len(clause_words) < self._policy.min_clause_words:
            return None

        determiner = _determiner_match(
            item.text[subject_start:subject_end],
            self._policy.own_determiners + self._policy.prior_determiners,
        )
        has_determiner_slot = determiner is not None
        spans: dict[str, tuple[int, int]] = {}
        slot_defs: dict[str, SlotDefinition] = {}
        if has_determiner_slot:
            if determiner is None:
                return None
            det_span = (subject_start, subject_start + determiner.end())
            noun_start, noun_end = _trim_span(item.text, det_span[1], subject_end)
            if noun_start == noun_end:
                return None
            spans["X"] = det_span
            spans["Y"] = (noun_start, noun_end)
            spans["Z"] = (clause_start, clause_end)
            determiner_text = item.text[slice(*det_span)].casefold()
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

        ownership = self._ownership(
            item, item.text[slice(*det_span)].casefold() if has_determiner_slot else ""
        )
        frame = f"[X] [Y] {surface} that [Z]" if "Z" in spans else f"[X] {surface} that [Y]"
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
