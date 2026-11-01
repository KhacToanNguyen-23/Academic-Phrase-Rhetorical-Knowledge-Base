"""Map parsed article headings to section codes from ``policies/section_headings.yaml``.

Headings are read in document order. Sub-headings ("3.1", "B.2") and unmatched headings
inherit the code of the section they sit in, so page headers and paragraph titles that the
markdown export promotes to headings do not break a section apart.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from aprkb.modules.corpus.parsers.base import ParsedSection
from aprkb.policies.schemas import SectionHeadingsPolicy

_TOP_NUMBER = re.compile(r"^(?:(?P<arabic>\d+)\.?|[IVXLC]+\.)\s+(?=\S)")
_SUB_NUMBER = re.compile(r"^\d+(?:\.\d+)+\.?\s+(?=\S)")
_APPENDIX_NUMBER = re.compile(r"^[A-H](?:\.\d+)*\.?\s+(?=[A-Z])")


@dataclass(frozen=True)
class _Matcher:
    code: str
    patterns: tuple[re.Pattern[str], ...]

    def matches(self, heading: str) -> bool:
        return any(pattern.search(heading) for pattern in self.patterns)


class SectionDetector:
    def __init__(self, policy: SectionHeadingsPolicy) -> None:
        self._rhetorical = _compile(policy.sections)
        self._non_rhetorical = _compile(policy.non_rhetorical)
        self._reset = tuple(re.compile(value) for value in policy.reset)
        self.non_rhetorical_codes = frozenset(policy.non_rhetorical)
        self._last_number = 0

    def detect(self, sections: Sequence[ParsedSection]) -> list[str | None]:
        """Return one section code (or ``None``) per parsed section, in the same order."""
        headings = [section.heading.strip() if section.heading else "" for section in sections]
        numbered = any(_TOP_NUMBER.match(heading) for heading in headings)
        codes: list[str | None] = []
        current: str | None = None
        self._last_number = 0
        for index, raw in enumerate(headings):
            if raw:
                current = self._next_code(raw, current, numbered=numbered, first=index == 0)
            codes.append(current)
        return codes

    def _is_top_heading(self, raw: str) -> bool:
        # Numbered list items and algorithm lines also become headings in exported
        # markdown, so an arabic number counts only when it continues the sequence.
        match = _TOP_NUMBER.match(raw)
        if match is None:
            return False
        if match.group("arabic") is None:
            return True
        number = int(match.group("arabic"))
        if number not in {self._last_number, self._last_number + 1}:
            return False
        self._last_number = number
        return True

    def _next_code(
        self, raw: str, current: str | None, *, numbered: bool, first: bool
    ) -> str | None:
        heading = _normalize(raw)
        if any(pattern.search(heading) for pattern in self._reset):
            return None
        non_rhetorical = _first_match(self._non_rhetorical, heading)
        if non_rhetorical is not None:
            return non_rhetorical
        if _SUB_NUMBER.match(raw):
            return current
        if self._is_top_heading(raw):
            return _first_match(self._rhetorical, heading)
        if numbered and not first and _APPENDIX_NUMBER.match(raw):
            return "APPENDIX" if "APPENDIX" in self.non_rhetorical_codes else current
        # In numbered documents, unnumbered headings are usually paragraph titles or
        # page headers; they only open a section before the first numbered heading.
        if numbered and current is not None:
            return current
        return _first_match(self._rhetorical, heading) or current


def _compile(patterns: dict[str, list[str]]) -> tuple[_Matcher, ...]:
    return tuple(
        _Matcher(code, tuple(re.compile(value) for value in values))
        for code, values in patterns.items()
    )


def _first_match(matchers: tuple[_Matcher, ...], heading: str) -> str | None:
    return next((matcher.code for matcher in matchers if matcher.matches(heading)), None)


def _normalize(heading: str) -> str:
    for numbering in (_SUB_NUMBER, _TOP_NUMBER, _APPENDIX_NUMBER):
        heading = numbering.sub("", heading, count=1)
    return " ".join(heading.casefold().rstrip(".:").split())
