from aprkb.modules.mining.frame_sections import summarize_frame_sections
from aprkb.modules.mining.read_filter import unknown_single_paper_reason
from aprkb.policies.loader import load_policy_bundle


def test_unknown_single_paper_frame_is_filtered_by_default_policy() -> None:
    policy = load_policy_bundle().mining_filter
    assert policy.unknown_single_paper_filter is True
    distribution = summarize_frame_sections(
        [("paper-a", None)],
        dominant_share_threshold=policy.frame_section_dominant_share_threshold,
    )
    assert (
        unknown_single_paper_reason(distribution, enabled=policy.unknown_single_paper_filter)
        == "unknown_single_paper"
    )


def test_unknown_frame_shared_by_two_papers_is_kept() -> None:
    distribution = summarize_frame_sections(
        [("paper-a", None), ("paper-b", None)], dominant_share_threshold=0.6
    )
    assert unknown_single_paper_reason(distribution, enabled=True) is None


def test_known_or_mixed_section_frame_is_kept() -> None:
    known = summarize_frame_sections([("paper-a", "RESULTS")], dominant_share_threshold=0.6)
    mixed = summarize_frame_sections(
        [("paper-a", None), ("paper-a", "INTRO")], dominant_share_threshold=0.6
    )
    assert unknown_single_paper_reason(known, enabled=True) is None
    assert unknown_single_paper_reason(mixed, enabled=True) is None


def test_disabled_filter_keeps_unknown_single_paper_frame() -> None:
    distribution = summarize_frame_sections([("paper-a", None)], dominant_share_threshold=0.6)
    assert unknown_single_paper_reason(distribution, enabled=False) is None


def test_frame_section_distribution_ignores_non_rhetorical_and_applies_share_threshold() -> None:
    single = summarize_frame_sections([("paper-a", "RESULTS")], dominant_share_threshold=0.6)
    non_rhetorical = summarize_frame_sections(
        [("paper-a", "APPENDIX")], dominant_share_threshold=0.6
    )
    result = summarize_frame_sections(
        [("paper-a", "RESULTS"), ("paper-b", "RESULTS"), ("paper-b", "APPENDIX")],
        dominant_share_threshold=0.6,
    )
    balanced = summarize_frame_sections(
        [("paper-a", "INTRO"), ("paper-b", "RESULTS")], dominant_share_threshold=0.6
    )

    assert single.dominant_code == "RESULTS"
    assert non_rhetorical.is_unknown is True
    assert unknown_single_paper_reason(non_rhetorical, enabled=True) == "unknown_single_paper"
    assert (result.counts["RESULTS"], result.shares["RESULTS"]) == (2, 1.0)
    assert (result.paper_count, result.known_count, result.unknown_count) == (2, 2, 1)
    assert result.dominant_code == "RESULTS"
    assert balanced.dominant_code == "MIXED"
