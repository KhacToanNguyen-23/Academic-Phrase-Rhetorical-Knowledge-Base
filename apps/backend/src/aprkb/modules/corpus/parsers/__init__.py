"""Document parser interfaces and implementations."""

from aprkb.modules.corpus.parsers.base import DocumentParser, ParsedDocument, ParsedSection
from aprkb.modules.corpus.parsers.jats_parser import JatsParserStub
from aprkb.modules.corpus.parsers.markdown_parser import MarkdownParser
from aprkb.modules.corpus.parsers.pdf_parser import PdfParser, PdfParserStub
from aprkb.modules.corpus.parsers.text_parser import TextParser

__all__ = [
    "DocumentParser",
    "JatsParserStub",
    "MarkdownParser",
    "ParsedDocument",
    "ParsedSection",
    "PdfParserStub",
    "PdfParser",
    "TextParser",
]
