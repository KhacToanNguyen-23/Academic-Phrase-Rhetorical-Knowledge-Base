"""Read-time filters for mined frames; extraction and stored candidates stay unchanged."""

from aprkb.modules.mining.frame_sections import FrameSectionDistribution


def unknown_single_paper_reason(
    distribution: FrameSectionDistribution,
    *,
    enabled: bool,
) -> str | None:
    """Return an audit reason when policy hides an UNKNOWN frame from one paper."""
    if enabled and distribution.is_unknown and distribution.paper_count == 1:
        return "unknown_single_paper"
    return None
