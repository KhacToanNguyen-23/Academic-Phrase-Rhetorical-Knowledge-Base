"""Read-side IMRaD distributions for a mined frame's source sentences."""

from collections import Counter
from collections.abc import Hashable, Iterable

from pydantic import BaseModel, ConfigDict

IMRAD_CODES = (
    "ABSTRACT",
    "INTRO",
    "RELATED_WORK",
    "METHODS",
    "RESULTS",
    "DISCUSSION",
    "CONCLUSION",
)
_IMRAD_SET = frozenset(IMRAD_CODES)


class FrameSectionDistribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counts: dict[str, int]
    shares: dict[str, float]
    paper_count: int
    known_count: int
    unknown_count: int
    dominant_code: str
    dominant_share: float
    is_unknown: bool


def summarize_frame_sections(
    sources: Iterable[tuple[Hashable, str | None]], *, dominant_share_threshold: float
) -> FrameSectionDistribution:
    """Summarize heading-sourced codes; inference and non-rhetorical labels stay unknown."""
    rows = list(sources)
    counts = Counter(code for _, code in rows if code in _IMRAD_SET)
    known_count = sum(counts.values())
    unknown_count = len(rows) - known_count
    shares = {
        code: counts.get(code, 0) / known_count if known_count else 0.0 for code in IMRAD_CODES
    }
    if known_count == 0:
        dominant_code = "UNKNOWN"
        dominant_share = 0.0
    else:
        top_count = max(counts.values())
        dominant_share = top_count / known_count
        top_codes = [code for code in IMRAD_CODES if counts.get(code, 0) == top_count]
        dominant_code = (
            top_codes[0]
            if (dominant_share >= dominant_share_threshold and len(top_codes) == 1)
            else "MIXED"
        )
    return FrameSectionDistribution(
        counts={code: counts.get(code, 0) for code in IMRAD_CODES},
        shares=shares,
        paper_count=len({article_id for article_id, _ in rows}),
        known_count=known_count,
        unknown_count=unknown_count,
        dominant_code=dominant_code,
        dominant_share=dominant_share,
        is_unknown=known_count == 0,
    )
