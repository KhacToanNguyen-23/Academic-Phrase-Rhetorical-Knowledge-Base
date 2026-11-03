"""Markdown parser: ATX headings become sections, inline markup is reduced to prose."""

import re

from aprkb.modules.corpus.parsers.base import DocumentParser, ParsedDocument, ParsedSection

_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
_FENCE = re.compile(r"^ {0,3}(```|~~~)")
_RULE = re.compile(r"^ {0,3}([-*_])(?:\s*\1){2,}\s*$")
_TABLE_ROW = re.compile(r"^\s*\|")
_BLOCK_PREFIX = re.compile(r"^\s{0,3}(?:>\s?)*(?:(?:[-*+]|\d+[.)])\s+)?")
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_CODE = re.compile(r"`([^`]*)`")
_STRONG = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
_EMPHASIS = re.compile(r"(?<!\w)([*_])(?=\S)(.+?)(?<=\S)\1(?!\w)")
_HTML = re.compile(r"<[^>]+>")


class MarkdownParser(DocumentParser):
    # TODO(owner, FR-07): setext headings, footnotes, and reference links are not handled.
    def supports(self, mime_type: str) -> bool:
        return mime_type.casefold().split(";", maxsplit=1)[0].strip() in {
            "text/markdown",
            "text/x-markdown",
        }

    def parse(self, blob: bytes) -> ParsedDocument:
        text = blob.decode("utf-8-sig")
        drafts: list[tuple[str | None, list[str]]] = [(None, [])]
        in_fence = False
        for line in _strip_front_matter(text).splitlines():
            if _FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence or _RULE.match(line) or _TABLE_ROW.match(line):
                continue
            heading_match = _HEADING.match(line)
            if heading_match:
                drafts.append((_inline(heading_match.group(2)) or None, []))
                continue
            drafts[-1][1].append(line)

        sections: list[ParsedSection] = []
        raw_parts: list[str] = []
        offset = 0
        for heading, lines in drafts:
            body = _paragraphs(lines)
            if not body and heading is None:
                continue
            if raw_parts:
                offset += 2
            sections.append(
                ParsedSection(heading=heading, text=body, order=len(sections), char_start=offset)
            )
            raw_parts.append(body)
            offset += len(body)
        return ParsedDocument(sections=tuple(sections), raw_text="\n\n".join(raw_parts))


def _strip_front_matter(text: str) -> str:
    if text.startswith("---\n") or text.startswith("---\r\n"):
        end = re.search(r"^---\s*$", text[3:], flags=re.MULTILINE)
        if end:
            return text[3 + end.end() :]
    return text


def _paragraphs(lines: list[str]) -> str:
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        cleaned = _inline(_BLOCK_PREFIX.sub("", line, count=1))
        if cleaned:
            current.append(cleaned)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def _inline(text: str) -> str:
    text = _IMAGE.sub("", text)
    text = _LINK.sub(r"\1", text)
    text = _CODE.sub(r"\1", text)
    text = _STRONG.sub(r"\2", text)
    text = _EMPHASIS.sub(r"\2", text)
    text = _HTML.sub("", text)
    return " ".join(text.split())
