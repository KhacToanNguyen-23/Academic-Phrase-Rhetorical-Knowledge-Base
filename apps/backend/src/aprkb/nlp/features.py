"""TODO(owner, FR-06.2): spike only; not wired into ingest or mining."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from aprkb.modules.corpus.sentence_splitter import SentenceSpan

FEATURES_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class TokenFeature:
    """The serialisable NLP attributes for one token."""

    i: int
    start: int
    end: int
    pos: str
    tag: str
    dep: str
    head: int
    lemma: str
    morph: str
    is_space: bool

    def to_json(self) -> list[Any]:
        """Return the compact, version-independent token representation."""
        return [
            self.i,
            self.start,
            self.end,
            self.pos,
            self.tag,
            self.dep,
            self.head,
            self.lemma,
            self.morph,
            self.is_space,
        ]

    @classmethod
    def from_json(cls, value: Any) -> TokenFeature:
        """Build a token feature from the compact JSON representation."""
        if not isinstance(value, list) or len(value) != 10:
            raise ValueError("token feature must be a 10-item JSON array")
        if not all(isinstance(value[index], int) for index in (0, 1, 2, 6)):
            raise ValueError("token indexes and offsets must be integers")
        if not all(isinstance(value[index], str) for index in (3, 4, 5, 7, 8)):
            raise ValueError("token labels must be strings")
        if not isinstance(value[9], bool):
            raise ValueError("token is_space must be a boolean")
        return cls(
            i=value[0],
            start=value[1],
            end=value[2],
            pos=value[3],
            tag=value[4],
            dep=value[5],
            head=value[6],
            lemma=value[7],
            morph=value[8],
            is_space=value[9],
        )


@dataclass(frozen=True)
class NlpEngineInfo:
    """Metadata needed to interpret persisted sentence features."""

    engine: str
    spacy_version: str
    model_name: str
    model_version: str
    components: tuple[str, ...]
    schema_version: int
    abbreviation_guard: bool

    def to_json(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "spacy_version": self.spacy_version,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "components": list(self.components),
            "schema_version": self.schema_version,
            "abbreviation_guard": self.abbreviation_guard,
        }


@dataclass(frozen=True)
class SentenceAnalysis:
    """One sentence's source offsets and token features."""

    char_start: int
    char_end: int
    tokens: tuple[TokenFeature, ...]

    def to_json(self) -> dict[str, Any]:
        """Return a compact JSON-compatible object suitable for JSONB."""
        return {
            "schema_version": FEATURES_SCHEMA_VERSION,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "tokens": [token.to_json() for token in self.tokens],
        }

    @classmethod
    def from_json(cls, value: str | Mapping[str, Any]) -> SentenceAnalysis:
        """Restore an analysis from a JSON string or decoded JSON object."""
        payload: Any = json.loads(value) if isinstance(value, str) else value
        if not isinstance(payload, Mapping):
            raise ValueError("sentence analysis must be a JSON object")
        if payload.get("schema_version") != FEATURES_SCHEMA_VERSION:
            raise ValueError("unsupported sentence analysis schema version")
        char_start = payload.get("char_start")
        char_end = payload.get("char_end")
        tokens = payload.get("tokens")
        if not isinstance(char_start, int) or not isinstance(char_end, int):
            raise ValueError("sentence analysis offsets must be integers")
        if not isinstance(tokens, list):
            raise ValueError("sentence analysis tokens must be a list")
        restored = cls(
            char_start=char_start,
            char_end=char_end,
            tokens=tuple(TokenFeature.from_json(token) for token in tokens),
        )
        _validate_tokens(restored.tokens)
        return restored

    def to_sentence_span(self, source_text: str) -> SentenceSpan:
        """Convert offsets into the existing corpus sentence-span contract."""
        if not 0 <= self.char_start <= self.char_end <= len(source_text):
            raise ValueError("sentence analysis offsets are outside the source text")
        return SentenceSpan(
            source_text[self.char_start : self.char_end], self.char_start, self.char_end
        )


def _validate_tokens(tokens: tuple[TokenFeature, ...]) -> None:
    for expected_i, token in enumerate(tokens):
        if token.i != expected_i:
            raise ValueError("token indexes must be contiguous and sentence-relative")
        if token.start > token.end:
            raise ValueError("token start must not exceed token end")
        if not 0 <= token.head < len(tokens):
            raise ValueError("token head must point inside the sentence")
