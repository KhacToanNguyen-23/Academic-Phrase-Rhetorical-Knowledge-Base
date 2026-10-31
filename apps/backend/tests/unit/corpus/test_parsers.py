"""Unit tests for the corpus domain."""

import pytest

from aprkb.modules.corpus.parsers.base import DocumentParser
from aprkb.modules.corpus.parsers.pdf_parser import PdfParserStub


def test_pdf_parser_implements_document_parser_interface_as_a_stub():
    parser = PdfParserStub()

    assert isinstance(parser, DocumentParser)
    assert parser.supports("application/pdf")
    with pytest.raises(NotImplementedError):
        parser.parse(b"%PDF-1.7")
