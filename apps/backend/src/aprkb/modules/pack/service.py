"""Transactional import and deterministic export of the PhrasePattern graph."""

import hashlib
import json
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.audit.service import record_event
from aprkb.modules.corpus.models import Article, License
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.pack.models import Version
from aprkb.modules.pack.validator import Finding, References, ValidationReport, validate_pack
from aprkb.modules.patterns.models import (
    EvidenceProvenance,
    PatternVersion,
    PhrasePattern,
    PhraseVariant,
    ReviewDecision,
    UsageConstraint,
)
from aprkb.modules.taxonomy.models import ArticleGenre, Intent, Move, Section, Step, TaxonomyRelease
from aprkb.shared.models import RefEnum

REVIEW_RE = re.compile(r"^\[reviewer: (.+) \((.+)\)\](?: (.*))?$", re.S)


async def database_references(
    session: AsyncSession,
) -> tuple[
    References, dict[tuple[str, str, str, str, str], UUID], dict[str, UUID], dict[str, UUID]
]:
    releases = list(
        await session.scalars(select(TaxonomyRelease).order_by(TaxonomyRelease.version))
    )
    versions = [row.version for row in releases]
    path_rows = (
        await session.execute(
            select(
                TaxonomyRelease.version, Section.code, Move.code, Step.code, Intent.code, Intent.id
            )
            .join(Section, Section.release_id == TaxonomyRelease.id)
            .join(Move, Move.section_id == Section.id)
            .join(Step, Step.move_id == Move.id)
            .join(Intent, Intent.step_id == Step.id)
        )
    ).all()
    intent_ids = {(row[0], row[1], row[2], row[3], row[4]): row[5] for row in path_rows}
    section_rows = (await session.execute(select(Section.code, Section.id))).all()
    genre_rows = (await session.execute(select(ArticleGenre.code, ArticleGenre.id))).all()
    license_rows = list(await session.scalars(select(License)))
    enum_rows = list(await session.scalars(select(RefEnum)))
    enums: dict[str, set[str]] = {}
    for row in enum_rows:
        enums.setdefault(row.group, set()).add(row.code)
    refs = References(
        taxonomy_version=versions[-1] if versions else "",
        intent_paths=frozenset(intent_ids),
        sections=frozenset(code for code, _ in section_rows),
        genres=frozenset(code for code, _ in genre_rows),
        enums={key: frozenset(values) for key, values in enums.items()},
        licenses={row.code: row.allows_mining for row in license_rows},
    )
    return refs, intent_ids, dict(section_rows), {row.code: row.id for row in license_rows}


def _note(note: str | None, author: str | None) -> str | None:
    return (
        f"{note}\nAuthor: {author}" if note and author else f"Author: {author}" if author else note
    )


def _split_note(note: str | None) -> tuple[str | None, str | None]:
    if not note:
        return None, None
    lines = note.split("\n")
    if lines[-1].startswith("Author: "):
        return "\n".join(lines[:-1]) or None, lines[-1][8:]
    return note, None


async def _stored_version(session: AsyncSession, version: PatternVersion) -> dict[str, Any]:
    usage = await session.scalar(
        select(UsageConstraint).where(UsageConstraint.pattern_version_id == version.id)
    )
    sources = list(
        await session.scalars(
            select(EvidenceProvenance).where(EvidenceProvenance.pattern_version_id == version.id)
        )
    )
    variants = list(
        await session.scalars(
            select(PhraseVariant)
            .where(PhraseVariant.pattern_version_id == version.id)
            .order_by(PhraseVariant.text, PhraseVariant.register)
        )
    )
    reviews = list(
        await session.scalars(
            select(ReviewDecision)
            .where(ReviewDecision.pattern_version_id == version.id)
            .order_by(ReviewDecision.round)
        )
    )
    if usage is None or len(sources) != 1:
        raise ValueError(f"Version {version.id} has incomplete pack metadata")
    source = sources[0]
    license_row = await session.get(License, source.license_id) if source.license_id else None
    article = await session.get(Article, source.article_id) if source.article_id else None
    change_note, author = _split_note(version.change_note)
    provenance: dict[str, Any] = {"source_type": source.source_type}
    if author:
        provenance["author"] = author
    if license_row:
        provenance["license_code"] = license_row.code
    if article:
        provenance["article"] = (
            {"doi": article.doi}
            if article.doi
            else {"source": article.source, "external_id": article.external_id}
        )
    if source.source_section_code:
        provenance["section_code"] = source.source_section_code
    if source.source_sentence_count is not None:
        provenance["source_sentence_count"] = source.source_sentence_count
    if source.occurrence_hash:
        provenance["occurrence_hash"] = source.occurrence_hash
    review_data = []
    for review in reviews:
        match = REVIEW_RE.fullmatch(review.comment or "")
        if match is None or review.decided_at is None:
            raise ValueError(f"Version {version.id} has unexportable review metadata")
        review_data.append(
            {
                "round": review.round,
                "decision": review.decision,
                "reviewer": match.group(1),
                "reviewer_role": match.group(2),
                "decided_at": review.decided_at.isoformat().replace("+00:00", "Z"),
                **({"comment": match.group(3)} if match.group(3) else {}),
            }
        )
    return {
        "version_id": str(version.id),
        "version_no": version.version_no,
        "canonical_frame": version.canonical_frame,
        "slots": version.slots,
        "claim_type": version.claim_type,
        "epistemic_strength": version.epistemic_strength,
        **({"change_note": change_note} if change_note is not None else {}),
        "usage": {
            "allowed_sections": usage.allowed_sections,
            "allowed_genres": usage.allowed_genres,
            "evidence_min": usage.evidence_min,
            "forbidden_contexts": usage.forbidden_contexts,
        },
        "variants": [
            {"text": row.text, **({"register": row.register} if row.register else {})}
            for row in variants
        ],
        "provenance": provenance,
        "reviews": review_data,
    }


def _canonical_version(version: Version) -> dict[str, Any]:
    return version.model_dump(mode="json", exclude_none=True)


async def check_import(session: AsyncSession, path: Path) -> ValidationReport:
    refs, _, _, _ = await database_references(session)
    report = validate_pack(path, refs)
    if report.patterns is None:
        return report
    for i, pattern in enumerate(report.patterns):
        existing_pattern = await session.get(PhrasePattern, pattern.pattern_id)
        if existing_pattern:
            versions = list(
                await session.scalars(
                    select(PatternVersion).where(PatternVersion.pattern_id == pattern.pattern_id)
                )
            )
            existing_numbers = {item.version_no for item in versions}
            supplied_numbers = {item.version_no for item in pattern.versions}
            if not existing_numbers.issubset(supplied_numbers):
                report.findings.append(
                    Finding(
                        "E16", "error", f"patterns[{i}].versions", "Pack omits an existing version"
                    )
                )
        for j, version in enumerate(pattern.versions):
            stored = await session.get(PatternVersion, version.version_id)
            if stored is None:
                continue
            try:
                equal = stored.pattern_id == pattern.pattern_id and _stored_equivalent(
                    await _stored_version(session, stored), _canonical_version(version)
                )
            except ValueError:
                equal = False
            if not equal:
                report.findings.append(
                    Finding(
                        "E15",
                        "error",
                        f"patterns[{i}].versions[{j}].version_id",
                        "Stored version_id has different content",
                    )
                )
    report.findings.sort(key=lambda item: (item.path, item.code, item.message))
    return report


def _stored_equivalent(left: dict[str, Any], right: dict[str, Any]) -> bool:
    # Omitted optional fields and explicit null are equivalent in the pack contract.
    for value in (left, right):
        value["variants"] = sorted(
            value.get("variants", []), key=lambda item: (item["text"], item.get("register") or "")
        )
    return Version.model_validate_json(json.dumps(left)).model_dump(
        mode="json", exclude_none=True
    ) == Version.model_validate_json(json.dumps(right)).model_dump(mode="json", exclude_none=True)


async def _actor(session: AsyncSession) -> ApiClient:
    actor = await session.scalar(select(ApiClient).where(ApiClient.name == "pack-importer"))
    if actor is None:
        actor = ApiClient(
            name="pack-importer",
            role="curator",
            is_active=False,
            key_prefix="disabled",
            key_hash=hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
        )
        session.add(actor)
        await session.flush()
    return actor


async def _article_stub(
    session: AsyncSession, version: Version, license_id: UUID, actor_id: UUID
) -> UUID | None:
    key = version.provenance.article
    if key is None:
        return None
    if key.doi:
        article = await session.scalar(select(Article).where(Article.doi == key.doi))
    else:
        article = await session.scalar(
            select(Article).where(
                Article.source == key.source, Article.external_id == key.external_id
            )
        )
    if article is None:
        article = Article(
            source=key.source or "pack",
            external_id=key.external_id,
            doi=key.doi,
            license_id=license_id,
            blob_key="",
            ingest_status="pack_metadata",
            created_by=actor_id,
        )
        session.add(article)
        await session.flush()
    elif article.license_id != license_id:
        raise ValueError("Article natural key is already associated with another license")
    return article.id


async def import_pack(
    session: AsyncSession, path: Path, *, dry_run: bool = False
) -> tuple[ValidationReport, dict[str, int]]:
    """Validate first, then add missing rows in one caller-controlled transaction."""
    report = await check_import(session, path)
    counts = {"patterns": 0, "versions": 0}
    if report.has_errors or report.patterns is None:
        return report, counts
    refs, intent_ids, _, license_ids = await database_references(session)
    del refs
    for pattern in report.patterns:
        if await session.get(PhrasePattern, pattern.pattern_id) is None:
            counts["patterns"] += 1
        for version in pattern.versions:
            if await session.get(PatternVersion, version.version_id) is None:
                counts["versions"] += 1
    if dry_run or not any(counts.values()):
        return report, counts
    actor = await _actor(session)
    for pattern in report.patterns:
        intent_key = (
            pattern.intent.taxonomy_version,
            pattern.intent.section,
            pattern.intent.move,
            pattern.intent.step,
            pattern.intent.intent,
        )
        existing = await session.get(PhrasePattern, pattern.pattern_id)
        if existing is None:
            existing = PhrasePattern(
                id=pattern.pattern_id,
                intent_id=intent_ids[intent_key],
                status="approved",
                current_version_id=None,
                created_by=actor.id,
            )
            session.add(existing)
            await session.flush()
        elif existing.intent_id != intent_ids[intent_key] or existing.status != "approved":
            raise ValueError("Existing pattern_id has different intent or status")
        for version in pattern.versions:
            if await session.get(PatternVersion, version.version_id):
                continue
            row = PatternVersion(
                id=version.version_id,
                pattern_id=pattern.pattern_id,
                version_no=version.version_no,
                canonical_frame=version.canonical_frame,
                slots={
                    key: value.model_dump(exclude_none=True) for key, value in version.slots.items()
                },
                epistemic_strength=version.epistemic_strength,
                claim_type=version.claim_type,
                change_note=_note(version.change_note, version.provenance.author),
                created_by=actor.id,
            )
            session.add(row)
            await session.flush()
            session.add(
                UsageConstraint(
                    pattern_version_id=row.id,
                    allowed_sections=version.usage.allowed_sections,
                    allowed_genres=version.usage.allowed_genres,
                    evidence_min=version.usage.evidence_min,
                    forbidden_contexts=version.usage.forbidden_contexts,
                    created_by=actor.id,
                )
            )
            for variant in version.variants:
                session.add(
                    PhraseVariant(
                        pattern_version_id=row.id,
                        text=variant.text,
                        register=variant.register,
                        created_by=actor.id,
                    )
                )
            license_id = license_ids.get(version.provenance.license_code or "")
            article_id = (
                await _article_stub(session, version, license_id, actor.id) if license_id else None
            )
            session.add(
                EvidenceProvenance(
                    pattern_version_id=row.id,
                    source_type=version.provenance.source_type,
                    article_id=article_id,
                    sentence_ids=[],
                    license_id=license_id,
                    source_sentence_count=version.provenance.source_sentence_count,
                    occurrence_hash=version.provenance.occurrence_hash,
                    source_section_code=version.provenance.section_code,
                    created_by=actor.id,
                )
            )
            for review in version.reviews:
                comment = f"[reviewer: {review.reviewer} ({review.reviewer_role})]" + (
                    f" {review.comment}" if review.comment else ""
                )
                session.add(
                    ReviewDecision(
                        pattern_version_id=row.id,
                        round=review.round,
                        decision=review.decision,
                        reviewer_id=actor.id,
                        comment=comment,
                        decided_at=review.decided_at,
                        created_by=actor.id,
                    )
                )
        latest = next(
            row for row in pattern.versions if row.version_no == pattern.current_version_no
        )
        existing.current_version_id = latest.version_id
    await session.flush()
    await record_event(
        session,
        actor_id=actor.id,
        action="pack.import",
        entity_type="data_pack",
        after={
            "pack_sha256": report.pack_sha256,
            "producer": report.manifest.producer if report.manifest else "",
            "patterns": counts["patterns"],
            "versions": counts["versions"],
            "actor": "pack-importer",
        },
        request_id="cli-pack-import",
    )
    return report, counts


async def export_pack(
    session: AsyncSession, out: Path, *, only_approved: bool = True
) -> dict[str, int]:
    """Write a deterministic pack from exportable, approved pattern graphs."""
    rows = list(await session.scalars(select(PhrasePattern).order_by(PhrasePattern.id)))
    patterns: list[dict[str, Any]] = []
    for pattern in rows:
        if pattern.status != "approved":
            continue  # pack v0.1 has no other status, irrespective of CLI flag
        intent_row = (
            await session.execute(
                select(TaxonomyRelease.version, Section.code, Move.code, Step.code, Intent.code)
                .join(Section, Section.release_id == TaxonomyRelease.id)
                .join(Move, Move.section_id == Section.id)
                .join(Step, Step.move_id == Move.id)
                .join(Intent, Intent.step_id == Step.id)
                .where(Intent.id == pattern.intent_id)
            )
        ).one()
        version_rows = list(
            await session.scalars(
                select(PatternVersion)
                .where(PatternVersion.pattern_id == pattern.id)
                .order_by(PatternVersion.version_no)
            )
        )
        try:
            versions = [await _stored_version(session, row) for row in version_rows]
        except ValueError:
            continue
        if any(
            version["provenance"]["source_type"] == "mined"
            and (
                not version["provenance"].get("article")
                or not version["provenance"].get("source_sentence_count")
                or len(version["reviews"]) != 2
            )
            for version in versions
        ):
            continue
        patterns.append(
            {
                "pattern_id": str(pattern.id),
                "status": pattern.status,
                "intent": dict(
                    zip(
                        ("taxonomy_version", "section", "move", "step", "intent"),
                        intent_row,
                        strict=True,
                    )
                ),
                "current_version_no": next(
                    row.version_no for row in version_rows if row.id == pattern.current_version_id
                ),
                "versions": versions,
            }
        )
    refs, _, _, _ = await database_references(session)
    payload = json.dumps(patterns, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    created_at = min((row.created_at for row in rows if row.status == "approved"), default=None)
    counts = {
        "patterns": len(patterns),
        "versions": sum(len(row["versions"]) for row in patterns),
    }
    manifest = {
        "pack_version": "0.1",
        "taxonomy_version": refs.taxonomy_version,
        "producer": "aprkb-export",
        "created_at": (created_at or datetime(1970, 1, 1, tzinfo=UTC))
        .isoformat()
        .replace("+00:00", "Z"),
        "counts": counts,
        "files": [
            {"name": "patterns.json", "sha256": hashlib.sha256(payload.encode()).hexdigest()}
        ],
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "patterns.json").write_text(payload, encoding="utf-8")
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return counts
