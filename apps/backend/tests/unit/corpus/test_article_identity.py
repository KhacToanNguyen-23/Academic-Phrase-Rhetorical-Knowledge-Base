import pytest

from aprkb.modules.corpus.identity import normalize_doi, normalize_title, title_identity


@pytest.mark.parametrize(
    "raw",
    [
        "10.1234/ABC",
        " https://doi.org/10.1234/ABC ",
        "http://dx.doi.org/10.1234/abc",
        "DOI: 10.1234/abc",
        "10.1234%2Fabc",
    ],
)
def test_doi_forms_share_an_identity(raw):
    assert normalize_doi(raw) == "10.1234/abc"


@pytest.mark.parametrize("raw", [None, "", " ", "not a doi", "10.1234/has spaces"])
def test_missing_or_invalid_doi_is_not_an_identity(raw):
    assert normalize_doi(raw) is None


def test_doi_suffix_punctuation_is_preserved():
    assert normalize_doi("10.1234/a.(b)") == "10.1234/a.(b)"
    assert normalize_doi("10.1234/a.(b)") != normalize_doi("10.1234/ab")


def test_title_normalization_preserves_words_and_unicode():
    assert normalize_title("  A STUDY: of  Việt Nam! ") == "a study of việt nam"
    assert title_identity("A study: of Việt Nam!") == title_identity("a study of việt nam")
    assert title_identity(None) is None
    assert len(title_identity("x" * 10000)) == 64
