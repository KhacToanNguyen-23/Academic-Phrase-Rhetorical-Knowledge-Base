"""JATS XML parser placeholder; full XML extraction is out of scaffold scope."""

from aprkb.modules.corpus.parsers.base import DocumentParser, ParsedDocument


class JatsParserStub(DocumentParser):
    def supports(self, mime_type: str) -> bool:
        return mime_type.casefold() in {"application/xml", "text/xml", "application/jats+xml"}

    def parse(self, blob: bytes) -> ParsedDocument:
        del blob
        # TODO(owner): implement section-aware JATS parsing under FR-07.
        raise NotImplementedError("JATS parsing is not implemented")
