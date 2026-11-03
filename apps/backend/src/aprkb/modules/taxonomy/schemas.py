"""HTTP schemas for published taxonomy and release metadata."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ReleaseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: str
    status: str
    published_at: datetime | None


class TaxonomyIntent(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None


class TaxonomyStep(BaseModel):
    id: UUID
    code: str
    name: str
    intents: list[TaxonomyIntent]


class TaxonomyMove(BaseModel):
    id: UUID
    code: str
    name: str
    steps: list[TaxonomyStep]


class TaxonomySection(BaseModel):
    id: UUID
    code: str
    name: str
    order: int
    compatible_genres: list[str]
    moves: list[TaxonomyMove]


class TaxonomyTree(BaseModel):
    release_id: UUID
    version: str
    sections: list[TaxonomySection]
    article_genres: list[dict[str, str]]


class ReferenceOption(BaseModel):
    group: str
    code: str
    label: str
    order: int
