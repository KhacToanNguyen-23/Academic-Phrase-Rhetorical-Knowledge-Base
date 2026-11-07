"""Shared PDF preview/upload checks, with no external document processing."""

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from aprkb.core.config import settings
from aprkb.modules.corpus.models import License
from aprkb.modules.corpus.parsers.pdf_parser import PdfInputError, PdfInspection, inspect_pdf
from aprkb.modules.corpus.pdf_schemas import PdfMetadata
from aprkb.modules.journals.models import JournalProfile
from aprkb.modules.taxonomy.models import ArticleGenre


async def read_upload(file: UploadFile) -> bytes:
    content = await file.read(settings.pdf_max_upload_bytes + 1)
    if len(content) > settings.pdf_max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds the configured upload limit")
    return content


def require_pdf_rights(license_row: License) -> None:
    if not license_row.allows_mining:
        raise HTTPException(status_code=403, detail="License does not allow PDF processing")


async def inspect_upload(content: bytes) -> PdfInspection:
    try:
        return await run_in_threadpool(inspect_pdf, content)
    except PdfInputError as error:
        raise HTTPException(
            status_code=422, detail={"code": error.code, "message": str(error)}
        ) from error


async def validate_metadata_references(session: AsyncSession, metadata: PdfMetadata) -> None:
    for value, model, label in (
        (metadata.journal_id, JournalProfile, "journal_id"),
        (metadata.genre_id, ArticleGenre, "genre_id"),
    ):
        if value is not None and await session.get(model, value) is None:
            raise HTTPException(status_code=422, detail=f"Unknown {label}")


async def reference_choices(
    session: AsyncSession,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    journals = [
        {"id": str(row.id), "name": row.name}
        for row in await session.scalars(select(JournalProfile).order_by(JournalProfile.name))
    ]
    genres = [
        {"id": str(row.id), "name": row.name}
        for row in await session.scalars(select(ArticleGenre).order_by(ArticleGenre.name))
    ]
    return journals, genres
