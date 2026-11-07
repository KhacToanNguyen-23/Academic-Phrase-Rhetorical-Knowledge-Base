"""Local text-layer PDF parsing. No network enrichment or OCR is performed."""

import re
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader, __version__
from pypdf.errors import PyPdfError

from aprkb.core.config import settings
from aprkb.modules.corpus.identity import normalize_doi, pdf_text_hash
from aprkb.modules.corpus.parsers.base import DocumentParser, ParsedDocument, ParsedSection

PARSER_VERSION = f"pypdf-{__version__}:text-v1"
_DOI = re.compile(r"\b10\.\d{4,9}/[^\s<>\"\u201c\u201d]+", re.I)
_HEADING = re.compile(
    r"^(?:(?:\d+(?:\.\d+)*\.?|[IVX]+\.)\s+)?"
    r"(?:abstract|summary|introduction|background|related work|literature review|"
    r"methods?|methodology|materials and methods|results?|discussion|limitations|"
    r"conclusions?|references|bibliography|acknowledgements?|appendix)\s*$",
    re.I,
)


class PdfInputError(ValueError):
    """Fixed public error code/message, without raw parser exceptions or file text."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class PdfInspection:
    document: ParsedDocument
    page_count: int
    text_sha256: str
    title: str | None
    authors: tuple[str, ...]
    doi_candidates: tuple[str, ...]
    warnings: tuple[str, ...]


def inspect_pdf(blob: bytes) -> PdfInspection:
    if not blob.startswith(b"%PDF-"):
        raise PdfInputError("invalid_pdf", "The file is not a PDF document.")
    if len(blob) > settings.pdf_max_upload_bytes:
        raise PdfInputError("pdf_too_large", "PDF exceeds the configured upload limit.")
    try:
        reader = PdfReader(BytesIO(blob), strict=False)
        if reader.is_encrypted:
            raise PdfInputError("pdf_encrypted", "Upload an unencrypted PDF you may process.")
        if not 0 < len(reader.pages) <= settings.pdf_max_pages:
            raise PdfInputError("pdf_page_limit", "PDF exceeds the configured page limit.")
        pages: list[str] = []
        chars = 0
        for page in reader.pages:
            stream = page.get_contents()
            if stream is not None and len(stream.get_data()) > settings.pdf_max_page_stream_bytes:
                raise PdfInputError("pdf_page_limit", "PDF page content exceeds the parser limit.")
            text = (page.extract_text() or "").replace("\x00", "").strip()
            if not any(char.isalnum() for char in text) and page.images:
                raise PdfInputError("pdf_ocr_required", "PDF has image-only pages. Run OCR first.")
            chars += len(text)
            if chars > settings.pdf_max_text_chars:
                raise PdfInputError(
                    "pdf_text_limit", "Extracted PDF text exceeds the parser limit."
                )
            pages.append(text)
        info = reader.metadata
        title = str(info.title).strip()[:1000] if info and info.title else None
        author = str(info.author).strip()[:1000] if info and info.author else None
    except PdfInputError:
        raise
    except (PyPdfError, ValueError, TypeError, KeyError, RecursionError, OverflowError) as error:
        raise PdfInputError(
            "invalid_pdf", "PDF could not be read. Upload a valid text PDF."
        ) from error

    # Only first-page DOI candidates are offered. References are not a work's identity.
    dois = tuple(
        dict.fromkeys(
            key
            for match in _DOI.finditer(pages[0])
            if (key := normalize_doi(match.group().rstrip(".,;")))
        )
    )
    warnings = [
        "PDF metadata and first-page DOI candidates are suggestions; verify them before import.",
        "Publication year, journal, genre and license are not inferred from PDF creation dates.",
    ]
    if len(dois) > 1:
        warnings.append("Multiple first-page DOIs found; select the paper DOI manually.")
    if any(len(page.strip()) < 50 for page in pages):
        warnings.append("Some pages have little or no text; inspect page extraction before mining.")
    sections: list[ParsedSection] = []
    raw_parts: list[str] = []
    offset = 0
    heading: str | None = None

    def emit(lines: list[str], page_number: int, heading: str | None) -> None:
        nonlocal offset
        body = "\n".join(lines).strip()
        if not body:
            return
        if raw_parts:
            offset += 2
        sections.append(ParsedSection(heading, body, len(sections), offset, page_number))
        raw_parts.append(body)
        offset += len(body)

    for page_number, text in enumerate(pages, 1):
        lines: list[str] = []
        for line in text.splitlines():
            if _HEADING.fullmatch(line.strip()):
                emit(lines, page_number, heading)
                lines = []
                heading = line.strip()
            else:
                lines.append(line)
        emit(lines, page_number, heading)
    if not raw_parts:
        raise PdfInputError("pdf_ocr_required", "PDF has no readable body text. Run OCR first.")
    raw_text = "\n\n".join(raw_parts)
    # Hash includes headings; retain mathematical symbols/exponents and case.
    return PdfInspection(
        ParsedDocument(tuple(sections), raw_text),
        len(pages),
        pdf_text_hash("\n".join(pages)),
        title,
        (author,) if author else (),
        dois,
        tuple(warnings),
    )


class PdfParser(DocumentParser):
    def supports(self, mime_type: str) -> bool:
        return mime_type.casefold().split(";", 1)[0].strip() == "application/pdf"

    def parse(self, blob: bytes) -> ParsedDocument:
        return inspect_pdf(blob).document


# Compatibility for integrations that imported the original interface name.
PdfParserStub = PdfParser
