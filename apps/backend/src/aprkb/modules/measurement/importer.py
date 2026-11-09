"""Strict parser and idempotent importer for the self-authored measurement catalog."""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.audit.service import record_event
from aprkb.modules.measurement.models import (
    MeasurementEntry,
    MeasurementImportRun,
    MeasurementRelation,
)
from aprkb.policies.schemas import MeasurementPolicy

_CODE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_ROOT_FIELDS = {"catalog_version", "entries", "relations"}
_REQUIRED = {"code", "kind", "name", "definition"}
_OPTIONAL_TEXT = ("formula", "scale", "value_range", "usage_note", "example")
_ENTRY_FIELDS = _REQUIRED | {"aliases", *_OPTIONAL_TEXT}
_TEXT_LIMITS = {"name": 200, "scale": 200, "value_range": 120}


@dataclass(frozen=True)
class ParsedEntry:
    code: str
    kind: str
    name: str
    aliases: list[str]
    definition: str
    formula: str | None
    scale: str | None
    value_range: str | None
    usage_note: str | None
    example: str | None


@dataclass(frozen=True)
class ParsedCatalog:
    catalog_version: str
    content_sha256: str
    entries: list[ParsedEntry]
    relations: list[tuple[str, str, str]]


def _text(value: Any, field: str, *, required: bool) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid measurement field: {field}")
    text = value.strip()
    limit = _TEXT_LIMITS.get(field)
    if limit is not None and len(text) > limit:
        raise ValueError(f"Measurement field too long: {field}")
    return text


def parse_catalog(raw: bytes, policy: MeasurementPolicy) -> ParsedCatalog:
    """Validate the whole document before any database write."""
    if len(raw) > policy.max_import_bytes:
        raise ValueError("Measurement catalog exceeds the configured size limit")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Measurement catalog is not valid UTF-8 JSON") from error
    if not isinstance(payload, dict) or set(payload) != _ROOT_FIELDS:
        raise ValueError("Measurement catalog must have catalog_version, entries and relations")
    version = payload["catalog_version"]
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("catalog_version must be a semantic version")
    raw_entries = payload["entries"]
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("Measurement catalog must contain entries")

    entries: list[ParsedEntry] = []
    kinds: dict[str, str] = {}
    for item in raw_entries:
        if not isinstance(item, dict) or not _REQUIRED <= set(item) <= _ENTRY_FIELDS:
            raise ValueError("Invalid measurement entry structure")
        code = item["code"]
        if not isinstance(code, str) or not _CODE.fullmatch(code):
            raise ValueError(f"Invalid measurement code: {code!r}")
        if code in kinds:
            raise ValueError(f"Duplicate measurement code: {code}")
        kind = item["kind"]
        if kind not in policy.kinds:
            raise ValueError(f"Unknown measurement kind for {code}")
        aliases = item.get("aliases", [])
        if not isinstance(aliases, list) or not all(
            isinstance(alias, str) and alias.strip() for alias in aliases
        ):
            raise ValueError(f"Invalid aliases for {code}")
        optional = {
            field: _text(item.get(field), field, required=False) for field in _OPTIONAL_TEXT
        }
        kinds[code] = kind
        entries.append(
            ParsedEntry(
                code=code,
                kind=kind,
                name=_text(item["name"], "name", required=True) or "",
                aliases=sorted({alias.strip() for alias in aliases}, key=str.casefold),
                definition=_text(item["definition"], "definition", required=True) or "",
                **optional,
            )
        )

    raw_relations = payload["relations"]
    if not isinstance(raw_relations, list):
        raise ValueError("relations must be a list")
    relations: set[tuple[str, str, str]] = set()
    for item in raw_relations:
        if not isinstance(item, dict) or set(item) != {"from", "relation", "to"}:
            raise ValueError("Invalid measurement relation structure")
        source, relation, target = item["from"], item["relation"], item["to"]
        if source not in kinds or target not in kinds or source == target:
            raise ValueError(f"Relation references an unknown or same code: {source}->{target}")
        if not policy.relation_allowed(relation, kinds[source], kinds[target]):
            raise ValueError(f"Relation not allowed by policy: {source} {relation} {target}")
        if (source, relation, target) in relations:
            raise ValueError(f"Duplicate relation: {source} {relation} {target}")
        relations.add((source, relation, target))

    return ParsedCatalog(
        catalog_version=version,
        content_sha256=hashlib.sha256(raw).hexdigest(),
        entries=entries,
        relations=sorted(relations),
    )


def load_catalog(path: Path, policy: MeasurementPolicy) -> ParsedCatalog:
    return parse_catalog(path.read_bytes(), policy)


async def import_catalog(
    session: AsyncSession,
    catalog: ParsedCatalog,
    *,
    actor_id: UUID | None,
    request_id: str,
) -> dict[str, Any]:
    """Upsert entries by code and replace relations in one transaction.

    Entries missing from the new catalog are kept because approved slot links may
    reference them; they are reported so a curator can decide.
    """
    last_run = await session.scalar(
        select(MeasurementImportRun).order_by(MeasurementImportRun.imported_at.desc()).limit(1)
    )
    existing = {
        entry.code: entry for entry in (await session.scalars(select(MeasurementEntry))).all()
    }
    new_codes = {entry.code for entry in catalog.entries}
    missing = sorted(set(existing) - new_codes)
    if last_run is not None and last_run.content_sha256 == catalog.content_sha256:
        return {
            "status": "unchanged",
            "catalog_version": catalog.catalog_version,
            "entries_created": 0,
            "entries_updated": 0,
            "relations": len(catalog.relations),
            "missing_codes": missing,
        }

    created = updated = 0
    for parsed in catalog.entries:
        values = {
            "kind": parsed.kind,
            "name": parsed.name,
            "aliases": parsed.aliases,
            "definition": parsed.definition,
            "formula": parsed.formula,
            "scale": parsed.scale,
            "value_range": parsed.value_range,
            "usage_note": parsed.usage_note,
            "example": parsed.example,
            "catalog_version": catalog.catalog_version,
        }
        entry = existing.get(parsed.code)
        if entry is None:
            entry = MeasurementEntry(code=parsed.code, **values)
            session.add(entry)
            existing[parsed.code] = entry
            created += 1
        else:
            for field, value in values.items():
                setattr(entry, field, value)
            updated += 1
    await session.flush()

    await session.execute(delete(MeasurementRelation))
    for source, relation, target in catalog.relations:
        session.add(
            MeasurementRelation(
                from_entry_id=existing[source].id,
                relation=relation,
                to_entry_id=existing[target].id,
            )
        )
    run = MeasurementImportRun(
        content_sha256=catalog.content_sha256,
        catalog_version=catalog.catalog_version,
        entry_count=len(catalog.entries),
        relation_count=len(catalog.relations),
        imported_by=actor_id,
    )
    session.add(run)
    await session.flush()
    await record_event(
        session,
        actor_id=actor_id,
        action="measurement.catalog_imported",
        entity_type="measurement_import_run",
        entity_id=run.id,
        after={
            "catalog_version": catalog.catalog_version,
            "content_sha256": catalog.content_sha256,
            "created": created,
            "updated": updated,
            "relations": len(catalog.relations),
            "missing_codes": len(missing),
        },
        request_id=request_id,
    )
    await session.commit()
    return {
        "status": "imported",
        "catalog_version": catalog.catalog_version,
        "entries_created": created,
        "entries_updated": updated,
        "relations": len(catalog.relations),
        "missing_codes": missing,
    }
