"""Unit tests for unlabeled corpus mining statistics."""

from aprkb.modules.mining.stats import StatsSentence, compute_mining_stats
from aprkb.policies.loader import load_policy_bundle


def test_compute_mining_stats_reports_reasons_frames_and_stable_samples() -> None:
    sentences = [
        StatsSentence("Our results reveal that the mock system improves retrieval quality."),
        StatsSentence("The study confirms that the mock system improves retrieval quality."),
        StatsSentence("This mock system improves retrieval quality today."),
        StatsSentence("Our results reveal the mock system improves retrieval quality."),
        StatsSentence("Reveal that the mock system improves retrieval quality."),
        StatsSentence(
            "The carefully designed mock retrieval experiment with several independent checks "
            "reveals that the mock system improves quality."
        ),
        StatsSentence("Our results reveal that cold."),
        StatsSentence("These reveal that the mock system improves retrieval quality."),
        StatsSentence("Table | row | values", section_code="RESULTS"),
        StatsSentence("A sentence in references should be ignored", section_code="REFERENCES"),
    ]

    first = compute_mining_stats(sentences, load_policy_bundle(), sample=2, seed=17)
    second = compute_mining_stats(sentences, load_policy_bundle(), sample=2, seed=17)

    assert first == second
    assert first.total_sentences == 10
    assert first.filter_kept == 8
    assert first.filter_rejected == {"excluded_section": 1, "table_row": 1}
    assert first.extraction_reasons["EXTRACTED"] == 2
    assert first.extraction_reasons["no_reporting_verb"] == 1
    assert first.extraction_reasons["no_that"] == 1
    assert first.extraction_reasons["no_subject"] == 1
    assert first.extraction_reasons["subject_too_long"] == 1
    assert first.extraction_reasons["clause_too_short"] == 1
    assert first.extraction_reasons["empty_noun_phrase"] == 1
    assert first.distinct_frames == 2
    assert len(first.extracted_samples) == 2
    assert len(first.missed_samples) == 2
