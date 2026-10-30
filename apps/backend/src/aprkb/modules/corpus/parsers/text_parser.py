"""UTF-8 plain text parser used by the scaffold ingestion path."""

from aprkb.modules.corpus.parsers.base import DocumentParser, ParsedDocument, ParsedSection


class TextParser(DocumentParser):
    def supports(self, mime_type: str) -> bool:
        return mime_type.casefold().split(";", maxsplit=1)[0].strip() in {
            "text/plain",
            "text/x-plain",
        }

    def parse(self, blob: bytes) -> ParsedDocument:
        text = blob.decode("utf-8-sig")
        return ParsedDocument(
            sections=(ParsedSection(heading=None, text=text, order=0),), raw_text=text
        )
