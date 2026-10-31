"""PDF parser placeholder; real extraction remains out of scope."""

from aprkb.modules.corpus.parsers.base import DocumentParser, ParsedDocument


class PdfParserStub(DocumentParser):
    def supports(self, mime_type: str) -> bool:
        return mime_type.casefold() == "application/pdf"

    def parse(self, blob: bytes) -> ParsedDocument:
        del blob
        # TODO(owner, FR-07): connect GROBID after parser deployment and license review.
        raise NotImplementedError("PDF parsing is not implemented")
