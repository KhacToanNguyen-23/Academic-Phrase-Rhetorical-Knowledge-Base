"""Pure phrase-statistics ranking and selector tests."""

from math import isfinite
from uuid import UUID

import pytest

from aprkb.modules.extraction.phrase_stats import (
    CandidateArticle,
    PhraseStatsRequest,
    compute_phrase_stats,
)
from aprkb.modules.mining.frame_key import frame_key
from aprkb.policies.loader import load_policy_bundle


def _row(
    candidate: int,
    sentence: int,
    article: int,
    batch: int,
    frame: str,
    *,
    status: str = "pending",
    cluster_key: str | None = None,
) -> CandidateArticle:
    return CandidateArticle(
        candidate_id=UUID(int=candidate),
        frame=frame,
        status=status,
        sentence_id=UUID(int=sentence),
        article_id=UUID(int=article),
        batch_id=UUID(int=batch),
        journal_id=None,
        cluster_key=cluster_key,
    )


def test_frame_key_normalizes_only_case_spacing_and_terminal_punctuation() -> None:
    assert frame_key("  [X]   Show that [Y].  ") == "[x] show that [y]"
    assert frame_key("[X] shows that [Y].") != frame_key("[X] show that [Y].")
    assert frame_key("[X] show that [Y].", "author_action:0.1.0").startswith(
        "construction=author_action:0.1.0|"
    )


def test_document_frequency_deduplicates_articles_and_scores_focal_only_frames() -> None:
    focal, background = UUID(int=1), UUID(int=2)
    rows = [
        _row(1, 1, 101, 1, "[X] common frame."),
        _row(2, 2, 101, 1, "[X] common frame."),
        _row(2, 3, 101, 1, "[X] common frame."),
        _row(3, 4, 102, 1, "[X] common frame."),
        _row(4, 5, 103, 1, "[X] focal only."),
        _row(5, 6, 103, 1, "[X] focal only."),
        _row(10, 11, 102, 1, "[X] focal only."),
        _row(6, 7, 201, 2, "[X] common frame."),
        _row(7, 8, 202, 2, "[X] common frame."),
        _row(8, 9, 203, 2, "[X] other background."),
        _row(9, 10, 203, 2, "[X] rejected frame.", status="rejected"),
    ]
    result = compute_phrase_stats(
        rows,
        PhraseStatsRequest(focal_batch_id=focal, background_batch_ids=(background,)),
        load_policy_bundle().phrase_stats.model_copy(update={"warn_below_focal_articles": 2}),
    )
    by_frame = {frame_key(row.frame): row for row in result.recurrence_ranking}

    assert result.n_focal == 3
    assert result.n_bg == 3
    assert by_frame["[x] common frame"].df_focal == 2
    assert by_frame["[x] common frame"].occurrences == 3
    assert by_frame["[x] common frame"].score == 0
    assert by_frame["[x] focal only"].df_focal == 2
    assert result.score_ranking[0].frame == "[X] focal only."
    assert "rejected frame" not in {row.frame for row in result.recurrence_ranking}


def test_small_focal_set_or_empty_background_uses_recurrence_only() -> None:
    focal = UUID(int=1)
    rows = [_row(1, 1, 101, 1, "[X] repeated frame.")]
    result = compute_phrase_stats(
        rows,
        PhraseStatsRequest(focal_batch_id=focal, all_other=True),
        load_policy_bundle().phrase_stats,
    )

    assert result.score_ranking == ()
    assert result.recurrence_ranking[0].frame == "[X] repeated frame."
    assert len(result.notices) == 2
    assert isfinite(result.recurrence_ranking[0].score)


def test_focal_background_overlap_fails_closed() -> None:
    rows = [_row(1, 1, 101, 1, "[X] frame")]

    with pytest.raises(ValueError, match="overlap"):
        compute_phrase_stats(
            rows,
            PhraseStatsRequest(focal_batch_id=UUID(int=1), background_batch_ids=(UUID(int=1),)),
            load_policy_bundle().phrase_stats,
        )


def test_request_requires_one_focal_and_background_mode() -> None:
    with pytest.raises(ValueError, match="exactly one focal"):
        compute_phrase_stats([], PhraseStatsRequest(), load_policy_bundle().phrase_stats)


def test_ties_use_document_frequency_then_occurrences_then_frame_key() -> None:
    rows = [
        _row(1, 1, 101, 1, "[X] zeta."),
        _row(2, 2, 102, 1, "[X] zeta."),
        _row(3, 3, 101, 1, "[X] alpha."),
        _row(4, 4, 102, 1, "[X] alpha."),
        _row(5, 5, 201, 2, "[X] background."),
        _row(6, 6, 202, 2, "[X] background."),
        _row(7, 7, 203, 2, "[X] background."),
    ]
    result = compute_phrase_stats(
        rows,
        PhraseStatsRequest(focal_batch_id=UUID(int=1), background_batch_ids=(UUID(int=2),)),
        load_policy_bundle().phrase_stats.model_copy(update={"warn_below_focal_articles": 2}),
    )

    assert [row.frame for row in result.score_ranking] == ["[X] alpha.", "[X] zeta."]
