"""Public read contracts for the vocabulary dictionary."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class LemmaSummary(BaseModel):
    id: UUID
    word: str
    pos: str
    pos_label: str
    rank: int | None
    band: int | None
    status: str | None
    status_label: str
    is_core: bool
    coca_acad: int | None


class LemmaPage(BaseModel):
    items: list[LemmaSummary]
    total: int


class FamilyPage(BaseModel):
    items: list[FamilyRead]
    total: int


class LetterCount(BaseModel):
    letter: str
    count: int


class DomainStatRead(BaseModel):
    domain: str
    domain_label: str
    freq: int
    relative_ratio: float


class FamilyMemberRead(BaseModel):
    lemma_id: UUID
    word: str
    pos: str
    pos_label: str
    freq: int
    category: str
    category_label: str
    domains: list[str]


class FamilyRead(BaseModel):
    id: UUID
    headword: str
    rank: int
    family_freq: int
    members: list[FamilyMemberRead]


class LemmaDetail(LemmaSummary):
    coca_all: int | None
    ratio: float | None
    disp: float | None
    range: int | None
    domains: list[str]
    domain_stats: list[DomainStatRead]
    families: list[FamilyRead]


class VocabularyPolicyLabels(BaseModel):
    """Internal typed helper for labels passed to mapping functions."""

    pos: dict[str, str]
    status: dict[str, str]
    category: dict[str, str]
    domains: dict[str, str]

    @classmethod
    def from_policy(cls, labels: Any) -> VocabularyPolicyLabels:
        return cls(
            pos=dict(labels.pos),
            status=dict(labels.status),
            category=dict(labels.category),
            domains=dict(labels.domains),
        )


class VocabularyFilterOptions(BaseModel):
    pos: dict[str, str]
    status: dict[str, str]
    domains: dict[str, str]
