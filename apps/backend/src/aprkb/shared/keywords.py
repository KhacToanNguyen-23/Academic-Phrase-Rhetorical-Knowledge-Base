"""Small, deterministic English suffix rules shared by retrieval and scoring."""

import re

# TODO(owner): approve suffix normalization and exceptions; this is not lemmatization.
SUFFIXES = ("ing", "ed", "es", "s")
MIN_STEM_LENGTH = 3


def normalize_token(token: str) -> str:
    token = token.casefold()
    for suffix in SUFFIXES:
        if not token.endswith(suffix):
            continue
        stem = token[: -len(suffix)]
        if len(stem) < MIN_STEM_LENGTH:
            continue
        # "suggests" -> "suggest", "uses" -> "use", "matches" -> "match".
        if suffix == "es" and not stem.endswith(("s", "x", "z", "ch", "sh")):
            continue
        if suffix == "s" and token.endswith(("ss", "us", "is")):
            continue
        return stem
    return token


def keyword_tokens(text: str) -> set[str]:
    return {normalize_token(word) for word in re.findall(r"[^\W_]+", text, re.UNICODE)}
