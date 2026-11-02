"""Sentence splitting around abbreviations, initials, and decimals (phase 01)."""

import pytest

from aprkb.modules.corpus.sentence_splitter import split_sentences


def _texts(source: str) -> list[str]:
    spans = split_sentences(source)
    assert all(source[span.char_start : span.char_end] == span.text for span in spans)
    return [span.text for span in spans]


@pytest.mark.parametrize(
    "abbreviation",
    ["e.g.", "i.e.", "et al.", "Fig.", "Eq.", "Tab.", "Dr.", "vs.", "cf.", "approx."],
)
def test_listed_abbreviation_does_not_end_a_sentence(abbreviation: str) -> None:
    source = f"We compare two settings {abbreviation} Twenty runs were kept. A second one follows."

    assert _texts(source) == [
        f"We compare two settings {abbreviation} Twenty runs were kept.",
        "A second one follows.",
    ]


def test_name_initials_and_decimals_stay_inside_the_sentence() -> None:
    source = "The method of J. Tran reached 0.93 on the dev set. It was stable."

    assert _texts(source) == [
        "The method of J. Tran reached 0.93 on the dev set.",
        "It was stable.",
    ]


def test_lower_case_continuation_is_not_a_boundary() -> None:
    assert _texts("The rate was 4 per min. on average over the trial. Then it fell.") == [
        "The rate was 4 per min. on average over the trial.",
        "Then it fell.",
    ]


def test_paragraph_break_always_ends_a_sentence() -> None:
    assert _texts("A heading without a period\n\nlower-case paragraph text.") == [
        "A heading without a period",
        "lower-case paragraph text.",
    ]


def test_explicit_abbreviation_list_overrides_the_packaged_one() -> None:
    source = "The values agree, cf. Table one. A new sentence starts."

    assert [span.text for span in split_sentences(source, abbreviations=[])] == [
        "The values agree, cf.",
        "Table one.",
        "A new sentence starts.",
    ]
