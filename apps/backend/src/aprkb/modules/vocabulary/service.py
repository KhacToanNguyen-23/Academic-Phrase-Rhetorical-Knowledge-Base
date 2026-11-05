"""Application service for transactional vocabulary imports."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.audit.service import record_event
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.vocabulary.models import VocabImportRun
from aprkb.modules.vocabulary.parsers import VocabularyParseError, parse_workbook
from aprkb.modules.vocabulary.repository import (
    list_import_runs,
    upsert_acad_core,
    upsert_families,
    upsert_lemmas,
)
from aprkb.modules.vocabulary.schemas import ImportResult, ImportRunPage, ImportRunRead
from aprkb.policies.schemas import VocabularyImportPolicy


async def import_workbook(
    session: AsyncSession,
    *,
    content: bytes,
    filename: str,
    actor: ApiClient | None,
    request_id: str,
    policy: VocabularyImportPolicy,
) -> ImportResult:
    """Parse and import one workbook in one database transaction."""
    if len(content) > policy.max_upload_bytes:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File is too large"
        )
    try:
        parsed = parse_workbook(content, policy)
        if parsed.source_kind == "all_words":
            counts = await upsert_lemmas(session, parsed.lemmas, source_kind=parsed.source_kind)
        elif parsed.source_kind == "acad_core":
            counts = await upsert_acad_core(session, parsed.lemmas, parsed.domain_stats)
        else:
            counts = await upsert_families(session, parsed.families, parsed.members)
        run = VocabImportRun(
            created_by=actor.id if actor else None,
            source_kind=parsed.source_kind,
            filename=Path(filename).name[:255],
            sha256=hashlib.sha256(content).hexdigest(),
            rows_read=parsed.rows_read,
            inserted=counts.inserted,
            updated=counts.updated,
            skipped=parsed.skipped,
            warnings=parsed.warnings,
        )
        session.add(run)
        await session.flush()
        await record_event(
            session,
            actor_id=actor.id if actor else None,
            action="vocabulary.import",
            entity_type="vocab_import_run",
            entity_id=run.id,
            after={
                "source_kind": parsed.source_kind,
                "filename": run.filename,
                "sha256": run.sha256,
                "rows_read": parsed.rows_read,
                "inserted": counts.inserted,
                "updated": counts.updated,
                "skipped": parsed.skipped,
                "warning_count": len(parsed.warnings),
            },
            request_id=request_id,
        )
        await session.commit()
        return ImportResult(
            run_id=run.id,
            source_kind=parsed.source_kind,
            rows_read=parsed.rows_read,
            inserted=counts.inserted,
            updated=counts.updated,
            skipped=parsed.skipped,
            warnings=parsed.warnings,
        )
    except VocabularyParseError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(error), "missing_columns": error.missing_columns},
        ) from error
    except Exception:
        await session.rollback()
        raise


async def list_import_history(session: AsyncSession, *, limit: int, offset: int) -> ImportRunPage:
    items, total = await list_import_runs(session, limit=limit, offset=offset)
    return ImportRunPage(items=[ImportRunRead.model_validate(item) for item in items], total=total)
