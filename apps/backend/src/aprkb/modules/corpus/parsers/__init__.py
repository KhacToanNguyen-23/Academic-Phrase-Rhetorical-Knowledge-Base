"""Document parser interfaces and implementations."""

from pathlib import Path

from aprkb.modules.corpus.parsers.base import DocumentParser, ParsedDocument, ParsedSection
from aprkb.modules.corpus.parsers.jats_parser import JatsParserStub
from aprkb.modules.corpus.parsers.markdown_parser import MarkdownParser
from aprkb.modules.corpus.parsers.pdf_parser import PdfParserStub
from aprkb.modules.corpus.parsers.text_parser import TextParser

_PARSERS: tuple[DocumentParser, ...] = (
    TextParser(),
    MarkdownParser(),
    JatsParserStub(),
    PdfParserStub(),
)


def mime_from_key(blob_key: str) -> str:
    """Resolve the supported MIME type from a stored blob key."""
    return {
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".xml": "application/xml",
        ".jats": "application/jats+xml",
        ".pdf": "application/pdf",
    }.get(Path(blob_key).suffix.casefold(), "application/octet-stream")


def parser_for_key(blob_key: str) -> DocumentParser | None:
    """Return the parser used by worker ingestion for a blob key."""
    mime_type = mime_from_key(blob_key)
    return next((parser for parser in _PARSERS if parser.supports(mime_type)), None)


__all__ = [
    "DocumentParser",
    "JatsParserStub",
    "MarkdownParser",
    "ParsedDocument",
    "ParsedSection",
    "PdfParserStub",
    "TextParser",
    "mime_from_key",
    "parser_for_key",
]
