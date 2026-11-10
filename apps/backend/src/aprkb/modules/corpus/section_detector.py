"""Map parsed article headings to section codes from ``policies/section_headings.yaml``.

Headings are read in document order. Sub-headings with a known parent and unmatched
headings inherit the current code; a sub-heading with an unseen numbered parent opens an
implicit section instead of inheriting a stale code.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from aprkb.modules.corpus.parsers.base import ParsedSection
from aprkb.policies.schemas import SectionHeadingsPolicy

_TOP_NUMBER = re.compile(r"^(?:(?P<arabic>\d+)(?:\.)?(?!\))|[IVXLC]+\.)\s*(?=\S|$)")
_SUB_NUMBER = re.compile(r"^\d+(?:\.\d+)+\.?\s+(?=\S)")
_APPENDIX_NUMBER = re.compile(r"^[A-H](?:\.\d+)*\.?\s+(?=[A-Z])")
_LabelSource = Literal["heading", "inherited", "implicit_parent", "inferred", "sandwich", "none"]


@dataclass(frozen=True)
class _Matcher:
    code: str
    patterns: tuple[re.Pattern[str], ...]

    def matches(self, heading: str) -> bool:
        return any(pattern.search(heading) for pattern in self.patterns)


class SectionDetector:
    def __init__(self, policy: SectionHeadingsPolicy) -> None:
        self._rhetorical = _compile(policy.sections)
        self._long_methods_parent_override = tuple(
            re.compile(value) for value in policy.long_methods_parent_override
        )
        self._non_rhetorical = _compile(policy.non_rhetorical)
        self._formal_blocks = _compile(policy.formal_blocks)
        self._formal_block_policy = policy.formal_block_policy
        self._appendix_patterns = tuple(re.compile(value) for value in policy.appendix_patterns)
        self._reset = tuple(re.compile(value) for value in policy.reset)
        self.non_rhetorical_codes = frozenset(policy.non_rhetorical)
        self._max_top_number_gap = policy.max_top_number_gap
        self._max_heading_length = policy.max_heading_length
        self._sentence_endings = tuple(policy.sentence_ending_punctuation)
        self._code_keywords = tuple(
            re.compile(rf"\b{re.escape(word)}\b", re.I) for word in policy.code_keywords
        )
        self._last_number = 0

    def detect(
        self, sections: Sequence[ParsedSection], *, infer_methods: bool = False
    ) -> list[str | None]:
        """Return one section code (or ``None``) per parsed section, in the same order."""
        labels = self.detect_with_provenance(sections)
        return [
            entry.inferred_code if infer_methods and entry.inferred_code else entry.code
            for entry in labels
        ]

    def detect_with_provenance(
        self, sections: Sequence[ParsedSection], *, apply_sandwich: bool = False
    ) -> list["SectionLabel"]:
        """Return a code, optional secondary code, and assignment source per section."""
        headings = [section.heading.strip() if section.heading else "" for section in sections]
        numbered = any(_TOP_NUMBER.match(heading) for heading in headings)
        labels: list[SectionLabel] = []
        current: str | None = None
        top_current: str | None = None
        subheading_override: tuple[tuple[int, ...], str] | None = None
        seen_top_numbers: set[int] = set()
        self._last_number = 0
        for index, raw in enumerate(headings):
            source: _LabelSource = "none"
            secondary_code: str | None = None
            if raw:
                parent = _sub_parent(raw)
                if parent is not None and parent not in seen_top_numbers:
                    if top_current in self.non_rhetorical_codes:
                        current, secondary_code, source = (
                            top_current,
                            None,
                            "inherited",
                        )
                    else:
                        current, secondary_code = self._matched_heading(raw)
                        source = "implicit_parent"
                    top_current = current
                    subheading_override = None
                    seen_top_numbers.add(parent)
                    self._last_number = max(self._last_number, parent)
                elif parent is not None:
                    subheading_number = _sub_number(raw)
                    long_methods_override = top_current not in self.non_rhetorical_codes and any(
                        pattern.search(_normalize(raw))
                        for pattern in self._long_methods_parent_override
                    )
                    if (
                        subheading_override is not None
                        and subheading_number[: len(subheading_override[0])]
                        == subheading_override[0]
                    ):
                        current = subheading_override[1]
                    else:
                        # A child match applies only in its subtree. Narrow METHODS phrases
                        # can override a rhetorical parent, but never a formal exclusion.
                        current = None if long_methods_override else top_current
                        subheading_override = None
                    current, secondary_code, source = self._next_label(
                        raw, current, numbered=numbered, first=index == 0
                    )
                    if (
                        source == "heading"
                        and current is not None
                        and (top_current is None or long_methods_override)
                    ):
                        subheading_override = (subheading_number, current)
                else:
                    leaving_subheading_scope = subheading_override is not None
                    subheading_override = None
                    current, secondary_code, source = self._next_label(
                        raw,
                        top_current
                        if leaving_subheading_scope or _TOP_NUMBER.match(raw)
                        else current,
                        numbered=numbered,
                        first=index == 0,
                    )
                    top_match = _TOP_NUMBER.match(raw)
                    if (
                        top_match is not None
                        and top_match.group("arabic") is not None
                        and source != "inherited"
                    ):
                        seen_top_numbers.add(int(top_match.group("arabic")))
                    is_non_rhetorical_anchor = (
                        source == "heading"
                        and current in self.non_rhetorical_codes
                        and not _SUB_NUMBER.match(raw)
                        and self._is_non_rhetorical_anchor(raw, current)
                    )
                    if top_match is not None or not numbered or is_non_rhetorical_anchor:
                        top_current = current
            elif current is not None:
                source = "inherited"
            labels.append(SectionLabel(current, secondary_code, source))
        inferred_indices = self._inferred_methods_indices(headings, labels)
        for index in inferred_indices:
            labels[index] = SectionLabel(
                labels[index].code, labels[index].secondary_code, "inferred", "METHODS"
            )
        # Inferred top-level sections pass their reporting label to their children.
        inferred_parent = False
        for index, heading in enumerate(headings):
            if index in inferred_indices:
                inferred_parent = True
            elif heading and not _SUB_NUMBER.match(heading):
                inferred_parent = False
            elif (
                inferred_parent
                and labels[index].code is None
                and labels[index].source in {"none", "inherited"}
            ):
                labels[index] = SectionLabel(
                    None, labels[index].secondary_code, "inferred", "METHODS"
                )
        return _apply_sandwich(sections, labels) if apply_sandwich else labels

    def _inferred_methods_indices(
        self, headings: list[str], labels: list["SectionLabel"]
    ) -> set[int]:
        top_indices = [
            i for i, heading in enumerate(headings) if heading and not _SUB_NUMBER.match(heading)
        ]
        inferred: set[int] = set()
        anchors_before: list[tuple[int, str]] = []
        for position, index in enumerate(top_indices):
            heading = headings[index]
            if (
                self._formal_kind(heading) is not None
                or self._is_lettered_appendix(heading)
                or any(pattern.search(_normalize(heading)) for pattern in self._reset)
            ):
                anchors_before.clear()
                continue
            code = labels[index].code
            if code in {"INTRO", "RELATED_WORK"}:
                anchors_before.append((index, code))
            elif code in {"RESULTS", "DISCUSSION", "CONCLUSION"}:
                anchors_before.clear()
            elif code is None and labels[index].source == "none":
                prior = next((code for _, code in reversed(anchors_before)), None)
                next_code = None
                for next_index in top_indices[position + 1 :]:
                    if (
                        self._formal_kind(headings[next_index]) is not None
                        or self._is_lettered_appendix(headings[next_index])
                        or any(
                            pattern.search(_normalize(headings[next_index]))
                            for pattern in self._reset
                        )
                    ):
                        break
                    if labels[next_index].code in {"RESULTS", "DISCUSSION", "CONCLUSION"}:
                        next_code = labels[next_index].code
                        break
                if prior in {"INTRO", "RELATED_WORK"} and next_code is not None:
                    inferred.add(index)
        return inferred

    def _formal_kind(self, raw: str) -> str | None:
        heading = _normalize(raw)
        return _first_match(self._formal_blocks, heading)

    def _is_lettered_appendix(self, raw: str) -> bool:
        return any(pattern.search(raw) for pattern in self._appendix_patterns)

    def _is_non_rhetorical_anchor(self, raw: str, code: str) -> bool:
        explicit = _first_match(self._non_rhetorical, _normalize(raw))
        return explicit == code or (
            code == "APPENDIX"
            and (self._is_lettered_appendix(raw) or _APPENDIX_NUMBER.match(raw) is not None)
        )

    def _is_top_heading(self, raw: str) -> bool:
        # Numbered list items and algorithm lines also become headings in exported
        # markdown, so an arabic number counts only when it continues the sequence.
        match = _TOP_NUMBER.match(raw)
        if match is None:
            return False
        if match.group("arabic") is None:
            return True
        number = int(match.group("arabic"))
        if number < self._last_number or number - self._last_number > self._max_top_number_gap:
            return False
        if _looks_like_list_or_code(
            raw, self._max_heading_length, self._sentence_endings, self._code_keywords
        ):
            return False
        self._last_number = number
        return True

    def _matched_heading(self, raw: str) -> tuple[str | None, str | None]:
        heading = _normalize(raw)
        if any(pattern.search(heading) for pattern in self._reset):
            return None, None
        non_rhetorical = _first_match(self._non_rhetorical, heading)
        if non_rhetorical is not None:
            return non_rhetorical, None
        formal = _first_match(self._formal_blocks, heading)
        if formal is not None:
            return "APPENDIX", None
        return _match_heading(self._rhetorical, heading)

    def _next_label(
        self, raw: str, current: str | None, *, numbered: bool, first: bool
    ) -> tuple[str | None, str | None, _LabelSource]:
        heading = _normalize(raw)
        if any(pattern.search(heading) for pattern in self._reset):
            return None, None, "none"
        non_rhetorical = _first_match(self._non_rhetorical, heading)
        if non_rhetorical is not None:
            return non_rhetorical, None, "heading"
        formal = _first_match(self._formal_blocks, heading)
        if formal == "DEFINITION_ASSUMPTION":
            if self._formal_block_policy == "inherit" and current == "METHODS":
                return current, None, "inherited"
            return "APPENDIX", None, "heading"
        if formal is not None:
            return "APPENDIX", None, "heading"
        if self._is_lettered_appendix(raw):
            return "APPENDIX", None, "heading"
        if _SUB_NUMBER.match(raw):
            if current is None:
                matched, secondary = _match_heading(self._rhetorical, heading)
                if matched is not None:
                    return matched, secondary, "heading"
            return current, None, "inherited"
        arabic_top = _TOP_NUMBER.match(raw)
        if arabic_top is not None and arabic_top.group("arabic") is not None:
            if not self._is_top_heading(raw):
                return current, None, "inherited" if current is not None else "none"
            code, secondary = _match_heading(self._rhetorical, heading)
            return code, secondary, "heading" if code is not None else "none"
        if self._is_top_heading(raw):
            code, secondary = _match_heading(self._rhetorical, heading)
            return code, secondary, "heading" if code is not None else "none"
        if numbered and not first and _APPENDIX_NUMBER.match(raw):
            if "APPENDIX" in self.non_rhetorical_codes:
                return "APPENDIX", None, "heading"
            return current, None, "inherited" if current is not None else "none"
        if numbered and current is not None:
            return current, None, "inherited"
        matched, secondary = _match_heading(self._rhetorical, heading)
        if matched is not None:
            return matched, secondary, "heading"
        return current, None, "inherited" if current is not None else "none"


def _compile(patterns: dict[str, list[str]]) -> tuple[_Matcher, ...]:
    return tuple(
        _Matcher(code, tuple(re.compile(value) for value in values))
        for code, values in patterns.items()
    )


def _first_match(matchers: tuple[_Matcher, ...], heading: str) -> str | None:
    return next((matcher.code for matcher in matchers if matcher.matches(heading)), None)


@dataclass(frozen=True)
class SectionLabel:
    code: str | None
    secondary_code: str | None
    source: _LabelSource
    inferred_code: str | None = None


def _apply_sandwich(
    sections: Sequence[ParsedSection], labels: list[SectionLabel]
) -> list[SectionLabel]:
    """Opt-in only: label unknown top sections bracketed by matching heading labels."""
    result = list(labels)
    top_indices = [
        index
        for index, section in enumerate(sections)
        if section.heading and not _SUB_NUMBER.match(section.heading)
    ]
    allowed = {"INTRO", "RELATED_WORK", "RESULTS", "DISCUSSION", "CONCLUSION"}
    assignments: dict[int, str] = {}
    for index in top_indices:
        label = labels[index]
        if label.code is not None or label.source not in {"none", "inferred"}:
            continue
        before = next(
            (
                labels[other].code
                for other in range(index - 1, -1, -1)
                if labels[other].source == "heading" and labels[other].code is not None
            ),
            None,
        )
        after = next(
            (
                labels[other].code
                for other in range(index + 1, len(labels))
                if labels[other].source == "heading" and labels[other].code is not None
            ),
            None,
        )
        if before == after and before in allowed:
            assignments[index] = before

    for index, code in assignments.items():
        result[index] = SectionLabel(code, labels[index].secondary_code, "sandwich")
        for child in range(index + 1, len(sections)):
            heading = sections[child].heading or ""
            if heading and not _SUB_NUMBER.match(heading):
                break
            if (
                _SUB_NUMBER.match(heading)
                and labels[child].code is None
                and labels[child].source in {"none", "inherited", "inferred"}
            ):
                result[child] = SectionLabel(code, labels[child].secondary_code, "inherited")
    return result


def _match_heading(matchers: tuple[_Matcher, ...], heading: str) -> tuple[str | None, str | None]:
    compound = re.fullmatch(r"(.+?)\s+and\s+(.+)", heading)
    if compound is not None:
        first = _first_match(matchers, compound.group(1))
        second = _first_match(matchers, compound.group(2))
        if first is not None and second is not None and first != second:
            return first, second
    return _first_match(matchers, heading), None


def _sub_parent(raw: str) -> int | None:
    match = _SUB_NUMBER.match(raw)
    return int(raw[: match.end()].split(".", 1)[0]) if match is not None else None


def _sub_number(raw: str) -> tuple[int, ...]:
    match = _SUB_NUMBER.match(raw)
    if match is None:
        return ()
    number = raw[: match.end()].rstrip(". ").split()
    return tuple(int(part) for part in number[0].split("."))


def _looks_like_list_or_code(
    raw: str,
    max_length: int,
    endings: tuple[str, ...],
    code_keywords: tuple[re.Pattern[str], ...],
) -> bool:
    match = _TOP_NUMBER.match(raw)
    title = raw[match.end() :].strip() if match else raw
    return (
        len(raw) > max_length
        or any(title.endswith(ending) for ending in endings)
        or any(keyword.search(title) for keyword in code_keywords)
    )


def _normalize(heading: str) -> str:
    for numbering in (_SUB_NUMBER, _TOP_NUMBER, _APPENDIX_NUMBER):
        heading = numbering.sub("", heading, count=1)
    return " ".join(heading.casefold().rstrip(".:").split())
