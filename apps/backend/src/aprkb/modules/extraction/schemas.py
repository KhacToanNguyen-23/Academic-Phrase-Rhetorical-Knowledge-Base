"""HTTP contracts for the extraction page."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from aprkb.modules.mining.schemas import SlotDefinition

MiningStatus = Literal["not_started", "queued", "processing", "succeeded", "failed"]
PhraseStatus = Literal["pending", "accepted", "rejected"]
MAX_MINE_ARTICLES = 1000


class PhraseCounts(BaseModel):
    pending: int = 0
    accepted: int = 0
    rejected: int = 0


class BatchRead(BaseModel):
    batch_id: UUID | None
    imported_at: datetime
    articles: int
    ready: int
    mined: int
    phrases: PhraseCounts


class ArticleRowRead(BaseModel):
    id: UUID
    title: str | None
    doi: str | None
    journal: str | None
    batch_id: UUID | None
    ingest_status: str
    mining_status: MiningStatus
    phrases: PhraseCounts


class SentenceText(BaseModel):
    id: UUID
    text: str


class SectionText(BaseModel):
    heading: str | None
    section_code: str | None
    sentences: list[SentenceText]
    page_number: int | None = None


class ArticleTextRead(BaseModel):
    article_id: UUID
    title: str | None
    sections: list[SectionText]


class MineRequest(BaseModel):
    article_ids: list[UUID] = Field(default_factory=list, max_length=MAX_MINE_ARTICLES)
    batch_ids: list[UUID] = Field(default_factory=list, max_length=100)
    unbatched: bool = False

    @model_validator(mode="after")
    def need_a_scope(self) -> "MineRequest":
        if not (self.article_ids or self.batch_ids or self.unbatched):
            raise ValueError("Select at least one article or batch")
        return self


class MineResult(BaseModel):
    job_ids: list[UUID]
    articles: int
    skipped_not_ready: int


class PhraseSource(BaseModel):
    sentence_id: UUID
    article_id: UUID
    article_title: str | None
    journal: str | None
    section: str | None
    text: str
    # Slot character ranges relative to ``text``.
    slot_spans: dict[str, tuple[int, int]]


class PhraseRead(BaseModel):
    id: UUID
    canonical_frame: str
    slots: dict[str, SlotDefinition]
    epistemic_strength: str | None
    status: str
    # True when provenance, licence or slot schema is not safe to accept (reject stays possible).
    blocked: bool
    sources: list[PhraseSource]


class PhrasePage(BaseModel):
    items: list[PhraseRead]
    total: int


class PhraseDecisionCreate(BaseModel):
    decision: Literal["accept", "reject"]
    comment: str | None = Field(default=None, max_length=4000)


class PhraseDecisionResult(BaseModel):
    candidate_id: UUID
    status: str
    approved_phrase_id: UUID | None


class BulkDecisionCreate(BaseModel):
    candidate_ids: list[UUID] = Field(min_length=1, max_length=200)
    decision: Literal["accept", "reject"]
    comment: str | None = Field(default=None, max_length=4000)


class BulkDecisionFailure(BaseModel):
    candidate_id: UUID
    reason: str


class BulkDecisionResult(BaseModel):
    results: list[PhraseDecisionResult]
    failed: list[BulkDecisionFailure]
