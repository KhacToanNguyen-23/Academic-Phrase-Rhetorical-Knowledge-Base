"""Text-layer extraction, metadata boundaries and stable PDF identities."""

import pytest

from aprkb.core.config import settings
from aprkb.modules.corpus.identity import pdf_text_hash
from aprkb.modules.corpus.parsers.pdf_parser import PdfInputError, PdfParser, inspect_pdf
from tests.pdf_factory import make_pdf, make_scanned_pdf


def test_pdf_pages_sections_offsets_and_metadata():
    info = inspect_pdf(make_pdf())
    assert info.page_count == 2
    assert info.title == "A self-authored PDF paper"
    assert info.authors == ("Test Author",)
    assert info.doi_candidates == ("10.1234/pdf-paper",)
    assert [row.page_number for row in info.document.sections] == [1, 2]
    assert [row.heading for row in info.document.sections] == ["Introduction", "Results"]
    for section in info.document.sections:
        assert (
            info.document.raw_text[section.char_start : section.char_start + len(section.text)]
            == section.text
        )
    assert PdfParser().supports("application/pdf; charset=binary")


def test_identity_ignores_pdf_properties_but_preserves_scientific_differences():
    left, right = make_pdf(title="First title"), make_pdf(title="Other title")
    assert left != right
    assert inspect_pdf(left).text_sha256 == inspect_pdf(right).text_sha256
    assert (
        inspect_pdf(make_pdf(("The observed rate was 10 percent.",))).text_sha256
        != inspect_pdf(make_pdf(("The observed rate was 20 percent.",))).text_sha256
    )
    assert (
        inspect_pdf(make_pdf(("The value of P was measured.",))).text_sha256
        != inspect_pdf(make_pdf(("The value of p was measured.",))).text_sha256
    )


def test_identity_preserves_mathematical_symbols_and_folds_whitespace_only():
    assert pdf_text_hash("x² = 4") != pdf_text_hash("x2 = 4")
    assert pdf_text_hash("A  result\non two lines") == pdf_text_hash("A result on two lines")


def test_blank_separator_page_does_not_shift_page_provenance():
    info = inspect_pdf(
        make_pdf(
            (
                "Introduction\nA meaningful opening sentence.",
                "",
                "Results\nThe results suggest an effect.",
            )
        )
    )
    assert info.page_count == 3
    assert [row.page_number for row in info.document.sections] == [1, 3]
    assert any("little or no text" in warning for warning in info.warnings)


def test_doi_candidates_exclude_references_on_later_pages_and_ambiguous_is_not_selected():
    info = inspect_pdf(
        make_pdf(("Paper 10.1234/first and 10.1234/second", "References\n10.1234/cited"))
    )
    assert info.doi_candidates == ("10.1234/first", "10.1234/second")
    assert any("Multiple" in warning for warning in info.warnings)


@pytest.mark.parametrize(
    "content,code",
    [
        (b"not PDF", "invalid_pdf"),
        (b"%PDF-broken", "invalid_pdf"),
        (make_pdf(("",)), "pdf_ocr_required"),
        (make_scanned_pdf(), "pdf_ocr_required"),
        (make_pdf(encrypted=True), "pdf_encrypted"),
    ],
)
def test_unreadable_pdfs_have_fixed_actionable_errors(content, code):
    with pytest.raises(PdfInputError) as caught:
        inspect_pdf(content)
    assert caught.value.code == code


@pytest.mark.parametrize(
    "setting,value,code",
    [
        ("pdf_max_upload_bytes", 10, "pdf_too_large"),
        ("pdf_max_pages", 1, "pdf_page_limit"),
        ("pdf_max_text_chars", 10, "pdf_text_limit"),
        ("pdf_max_page_stream_bytes", 10, "pdf_page_limit"),
    ],
)
def test_resource_limits_are_configurable(monkeypatch, setting, value, code):
    monkeypatch.setattr(settings, setting, value)
    with pytest.raises(PdfInputError) as caught:
        inspect_pdf(make_pdf())
    assert caught.value.code == code
