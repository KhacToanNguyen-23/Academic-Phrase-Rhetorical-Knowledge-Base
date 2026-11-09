"""Stable phrase-statistics identity, separate from the sentence-level cluster key."""

import re


def frame_key(canonical_frame: str, construction_id: str | None = None) -> str:
    """Normalize frame spacing/case/punctuation without merging forms or tenses."""
    normalized = re.sub(r"\s+", " ", canonical_frame).strip().casefold().rstrip(".!?").strip()
    if construction_id:
        return f"construction={construction_id}|{normalized}"
    return normalized
