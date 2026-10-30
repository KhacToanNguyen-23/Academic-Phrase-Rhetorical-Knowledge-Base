"""Pattern read and append-only write services."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.audit.service import record_event
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.patterns import repository
from aprkb.modules.patterns.models import (
    EvidenceProvenance,
    PatternVersion,
    PhrasePattern,
    UsageConstraint,
)
from aprkb.modules.patterns.schemas import PatternCreate, PatternVersionCreate
from aprkb.modules.taxonomy.models import Intent


async def list_patterns(
    session: AsyncSession,
    *,
    intent: str | None,
    section: str | None,
    status: str | None,
    offset: int,
    limit: int,
) -> list[dict[str, object]]:
    rows = await repository.list_patterns(
        session,
        intent_code=intent,
        section_code=section,
        status=status,
        offset=offset,
        limit=limit,
    )
    return [await pattern_detail(session, row.id) for row in rows]


async def pattern_detail(session: AsyncSession, pattern_id: UUID) -> dict[str, object]:
    pattern = await repository.get_pattern(session, pattern_id)
    if pattern is None:
        raise HTTPException(status_code=404, detail="Pattern not found")
    intent = await session.get(Intent, pattern.intent_id)
    version = await repository.get_current_version(session, pattern)
    usage = await repository.get_usage_constraint(session, version.id) if version else None
    return {
        "id": pattern.id,
        "status": pattern.status,
        "intent_code": intent.code if intent else "",
        "canonical_frame": version.canonical_frame if version else None,
        "version_no": version.version_no if version else None,
        "current_version_id": version.id if version else None,
        "slots": version.slots if version else None,
        "epistemic_strength": version.epistemic_strength if version else None,
        "claim_type": version.claim_type if version else None,
        "allowed_sections": usage.allowed_sections if usage else [],
        "allowed_genres": usage.allowed_genres if usage else [],
    }


async def pattern_versions(session: AsyncSession, pattern_id: UUID) -> list[PatternVersion]:
    if await repository.get_pattern(session, pattern_id) is None:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return await repository.list_versions(session, pattern_id)


async def create_pattern(
    session: AsyncSession,
    *,
    payload: PatternCreate,
    actor: ApiClient,
    request_id: str,
) -> dict[str, object]:
    intent = await repository.get_intent(session, payload.intent_code)
    if intent is None:
        raise HTTPException(status_code=422, detail="Unknown intent_code")
    pattern = PhrasePattern(intent_id=intent.id, status="draft", created_by=actor.id)
    session.add(pattern)
    try:
        await session.flush()
        version = PatternVersion(
            pattern_id=pattern.id,
            version_no=1,
            canonical_frame=payload.canonical_frame,
            slots=payload.slots,
            epistemic_strength=payload.epistemic_strength,
            claim_type=payload.claim_type,
            change_note=payload.change_note,
            created_by=actor.id,
        )
        session.add(version)
        await session.flush()
        pattern.current_version_id = version.id
        session.add(
            UsageConstraint(
                pattern_version_id=version.id,
                allowed_sections=payload.allowed_sections,
                allowed_genres=payload.allowed_genres,
            )
        )
        session.add(
            EvidenceProvenance(
                pattern_version_id=version.id,
                source_type=payload.source_type,
                sentence_ids=[],
            )
        )
        await session.flush()
        await record_event(
            session,
            actor_id=actor.id,
            action="pattern.create",
            entity_type="phrase_pattern",
            entity_id=pattern.id,
            after={"status": pattern.status, "intent_code": intent.code, "version_no": 1},
            request_id=request_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return await pattern_detail(session, pattern.id)


async def append_version(
    session: AsyncSession,
    *,
    pattern_id: UUID,
    payload: PatternVersionCreate,
    actor: ApiClient,
    request_id: str,
) -> PatternVersion:
    pattern = await session.scalar(
        select(PhrasePattern).where(PhrasePattern.id == pattern_id).with_for_update()
    )
    if pattern is None:
        raise HTTPException(status_code=404, detail="Pattern not found")
    old_version = await repository.get_current_version(session, pattern)
    old_usage = (
        await repository.get_usage_constraint(session, old_version.id) if old_version else None
    )
    old_provenance = (
        await repository.get_provenance(session, old_version.id) if old_version else None
    )
    current = await session.scalar(
        select(func.max(PatternVersion.version_no)).where(PatternVersion.pattern_id == pattern_id)
    )
    version = PatternVersion(
        pattern_id=pattern_id,
        version_no=(current or 0) + 1,
        canonical_frame=payload.canonical_frame,
        slots=payload.slots,
        epistemic_strength=payload.epistemic_strength,
        claim_type=payload.claim_type,
        change_note=payload.change_note,
        created_by=actor.id,
    )
    session.add(version)
    try:
        await session.flush()
        pattern.current_version_id = version.id
        old_version_no = current
        session.add(
            UsageConstraint(
                pattern_version_id=version.id,
                allowed_sections=old_usage.allowed_sections if old_usage else [],
                allowed_genres=old_usage.allowed_genres if old_usage else [],
            )
        )
        session.add(
            EvidenceProvenance(
                pattern_version_id=version.id,
                source_type=old_provenance.source_type if old_provenance else "authored",
                article_id=old_provenance.article_id if old_provenance else None,
                sentence_ids=old_provenance.sentence_ids if old_provenance else [],
                license_id=old_provenance.license_id if old_provenance else None,
            )
        )
        await record_event(
            session,
            actor_id=actor.id,
            action="pattern.version.create",
            entity_type="pattern_version",
            entity_id=version.id,
            before={"version_no": old_version_no},
            after={"pattern_id": str(pattern_id), "version_no": version.version_no},
            request_id=request_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return version


async def retire_pattern(
    session: AsyncSession, *, pattern_id: UUID, actor: ApiClient, request_id: str
) -> None:
    pattern = await session.get(PhrasePattern, pattern_id)
    if pattern is None:
        raise HTTPException(status_code=404, detail="Pattern not found")
    before = {"status": pattern.status}
    pattern.status = "retired"
    try:
        await record_event(
            session,
            actor_id=actor.id,
            action="pattern.retire",
            entity_type="phrase_pattern",
            entity_id=pattern.id,
            before=before,
            after={"status": pattern.status},
            request_id=request_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
