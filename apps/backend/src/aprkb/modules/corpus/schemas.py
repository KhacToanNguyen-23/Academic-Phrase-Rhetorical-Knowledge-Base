"""Pydantic schemas (data contracts) của module corpus."""

from pydantic import BaseModel, Field

from aprkb.modules.corpus.importer import MAX_IMPORT_BATCH_LIMIT


class ArticleImportCreate(BaseModel):
    cursor: str | None = Field(default=None, max_length=1024)
    limit: int | None = Field(default=None, ge=1, le=MAX_IMPORT_BATCH_LIMIT)
