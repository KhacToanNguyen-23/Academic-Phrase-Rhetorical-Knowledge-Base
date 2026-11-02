"""Self-authored examples for scholarly sentence boundaries (not a gold corpus)."""

import pytest

from aprkb.modules.corpus.sentence_splitter import split_sentences


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "We use examples, e.g. neural models. They work.",
            ["We use examples, e.g. neural models.", "They work."],
        ),
        (
            "Use controls, i.e. untreated cells. Compare them.",
            ["Use controls, i.e. untreated cells.", "Compare them."],
        ),
        ("Dr. Smith met Prof. Jones. They agreed.", ["Dr. Smith met Prof. Jones.", "They agreed."]),
        ("J. R. Smith reports this. We agree.", ["J. R. Smith reports this.", "We agree."]),
        (
            "Smith et al. report gains. We replicate them.",
            ["Smith et al. report gains.", "We replicate them."],
        ),
        (
            "Smith et al. (2020) report gains. We agree.",
            ["Smith et al. (2020) report gains.", "We agree."],
        ),
        (
            "Smith et al. in 2020 reported gains. We agree.",
            ["Smith et al. in 2020 reported gains.", "We agree."],
        ),
        (
            "We studied the U.S. in 2020. We replicated results.",
            ["We studied the U.S. in 2020.", "We replicated results."],
        ),
        (
            "Examples include e.g. Smith's method. Results follow.",
            ["Examples include e.g. Smith's method.", "Results follow."],
        ),
        ("See Fig. 2 and Eq. 3. Results follow.", ["See Fig. 2 and Eq. 3.", "Results follow."]),
        (
            "The U.S. cohort improved. This was replicated in the U.K. We agree.",
            ["The U.S. cohort improved.", "This was replicated in the U.K.", "We agree."],
        ),
        (
            "We used etc. as an abbreviation. We listed cells, tissues, etc. These differ.",
            ["We used etc. as an abbreviation.", "We listed cells, tissues, etc.", "These differ."],
        ),
        (
            'She said "It works." Then left. (Why?) We checked.',
            ['She said "It works."', "Then left.", "(Why?)", "We checked."],
        ),
        (
            "The effect was 3.14 (p < 0.05). Visit https://example.org/data. Done.",
            ["The effect was 3.14 (p < 0.05).", "Visit https://example.org/data.", "Done."],
        ),
        ("Wait... Is this real?! Yes!", ["Wait...", "Is this real?!", "Yes!"]),
        (
            "Heading\n\nA wrapped\nline with e.g. examples.\n\nNext section",
            ["Heading", "A wrapped\nline with e.g. examples.", "Next section"],
        ),
        ("e.g.\n\nNew paragraph", ["e.g.", "New paragraph"]),
        (
            "Heading\r\n\r\nText with e.g. examples.\r\n\r\nNext",
            ["Heading", "Text with e.g. examples.", "Next"],
        ),
        ("  Ω improves.  Ω remains.  ", ["Ω improves.", "Ω remains."]),
        ("", []),
        (" \n\t", []),
    ],
)
def test_scholarly_sentence_boundaries(source: str, expected: list[str]) -> None:
    spans = split_sentences(source)

    assert [span.text for span in spans] == expected
    assert all(source[span.char_start : span.char_end] == span.text for span in spans)
    assert all(
        left.char_end <= right.char_start for left, right in zip(spans, spans[1:], strict=False)
    )
    # No punctuation or non-whitespace content may disappear between spans.
    assert "".join("".join(span.text.split()) for span in spans) == "".join(source.split())
