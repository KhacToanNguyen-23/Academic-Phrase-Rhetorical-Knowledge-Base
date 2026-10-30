"""Candidate writer port that refuses unsourced mined output."""

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class CandidateDraft:
    canonical_frame: str
    source_sentence_ids: list[UUID]
    slots: dict[str, object] = field(default_factory=dict)
    confidence: float | None = None
    epistemic_strength: str | None = None


class CandidateRepository(Protocol):
    def create_candidate(self, draft: CandidateDraft) -> object: ...


class CandidateWriter:
    def __init__(self, repository: CandidateRepository | None) -> None:
        self._repository = repository

    def write(self, draft: CandidateDraft) -> object:
        if not draft.source_sentence_ids:
            raise ValueError("source_sentence_ids are required for every mined candidate")
        if self._repository is None:
            raise RuntimeError("Candidate repository is not configured")
        return self._repository.create_candidate(draft)
