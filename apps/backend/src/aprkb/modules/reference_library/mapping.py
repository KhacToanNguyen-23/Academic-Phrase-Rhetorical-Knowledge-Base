"""Reviewed mappings between removable reference groups and AP-RKB taxonomy codes."""

from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.reference_library.models import (
    ReferenceCategory,
    ReferenceEntry,
    ReferenceSource,
    ReferenceTaxonomyMap,
)
from aprkb.modules.taxonomy.models import Intent, Move, Section, Step, TaxonomyRelease
from aprkb.shared.models import RefEnum


def _reference_rows(
    categories: list[ReferenceCategory], entries: list[ReferenceEntry]
) -> dict[str, tuple[ReferenceCategory, int | None, str]]:
    rows: dict[str, tuple[ReferenceCategory, int | None, str]] = {}
    by_category: dict[object, list[ReferenceEntry]] = {}
    for entry in entries:
        by_category.setdefault(entry.category_id, []).append(entry)
    for category in categories:
        rows[f"category:{category.slug}"] = (category, None, category.title)
        seen: set[int] = set()
        for entry in sorted(by_category.get(category.id, []), key=lambda item: item.position):
            if entry.heading_position in seen:
                continue
            key = f"heading:{category.slug}:{entry.heading_position}"
            rows[key] = (category, entry.heading_position, entry.heading)
            seen.add(entry.heading_position)
    return rows


async def export_template(session: AsyncSession) -> str:
    source = await session.scalar(
        select(ReferenceSource).order_by(ReferenceSource.imported_at.desc()).limit(1)
    )
    if source is None:
        return cast(str, yaml.safe_dump({"mappings": []}, sort_keys=False))
    categories = list(
        await session.scalars(
            select(ReferenceCategory)
            .where(ReferenceCategory.source_id == source.id)
            .order_by(ReferenceCategory.position, ReferenceCategory.slug)
        )
    )
    category_ids = [category.id for category in categories]
    entries = list(
        await session.scalars(
            select(ReferenceEntry)
            .where(ReferenceEntry.category_id.in_(category_ids))
            .order_by(ReferenceEntry.category_id, ReferenceEntry.position)
        )
    )
    rows = _reference_rows(categories, entries)
    document = {
        "mappings": [
            {
                "reference_key": key,
                "reference_title": title,
                "target_kind": None,
                "target_code": None,
                "review_status": None,
                "mapped_by": None,
                "note": None,
            }
            for key, (_category, _heading_position, title) in rows.items()
        ]
    }
    return cast(str, yaml.safe_dump(document, sort_keys=False, allow_unicode=True))


def _parse_file(path: Path) -> list[dict[str, Any]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or set(document) != {"mappings"}:
        raise ValueError("Mapping file must contain only a mappings list")
    mappings = document["mappings"]
    if not isinstance(mappings, list):
        raise ValueError("Mapping file mappings must be a list")
    allowed_fields = {
        "reference_key",
        "reference_title",
        "target_kind",
        "target_code",
        "review_status",
        "mapped_by",
        "note",
    }
    for item in mappings:
        if not isinstance(item, dict) or set(item) != allowed_fields:
            raise ValueError("Invalid reference mapping row structure")
        for name in ("reference_key", "reference_title"):
            if not isinstance(item[name], str) or not item[name].strip():
                raise ValueError(f"Invalid reference mapping field: {name}")
        if item["target_code"] is None:
            if any(item[name] is not None for name in ("target_kind", "review_status")):
                raise ValueError("Unmapped rows must leave target_kind and review_status empty")
        else:
            if item["target_kind"] not in {"section", "intent", "general_function"}:
                raise ValueError("Invalid reference mapping target_kind")
            if item["review_status"] not in {"proposed", "approved"}:
                raise ValueError("Invalid reference mapping review_status")
            if not isinstance(item["target_code"], str) or not item["target_code"].strip():
                raise ValueError("Invalid reference mapping target_code")
        for name in ("mapped_by", "note"):
            if item[name] is not None and not isinstance(item[name], str):
                raise ValueError(f"Invalid reference mapping field: {name}")
    if len({item["reference_key"] for item in mappings}) != len(mappings):
        raise ValueError("Reference mapping keys must be unique")
    return mappings


async def _taxonomy_codes(session: AsyncSession) -> dict[str, set[str]]:
    release_id = await session.scalar(
        select(TaxonomyRelease.id)
        .where(TaxonomyRelease.status == "published")
        .order_by(TaxonomyRelease.published_at.desc(), TaxonomyRelease.version.desc())
        .limit(1)
    )
    if release_id is None:
        return {"section": set(), "intent": set(), "general_function": set()}
    sections = set(
        await session.scalars(select(Section.code).where(Section.release_id == release_id))
    )
    intents = set(
        await session.scalars(
            select(Intent.code)
            .join(Step, Intent.step_id == Step.id)
            .join(Move, Step.move_id == Move.id)
            .join(Section, Move.section_id == Section.id)
            .where(Section.release_id == release_id)
        )
    )
    general_functions = set(
        await session.scalars(select(RefEnum.code).where(RefEnum.group == "general_function"))
    )
    return {"section": sections, "intent": intents, "general_function": general_functions}


async def import_mapping_file(session: AsyncSession, path: Path) -> int:
    mappings = _parse_file(path)
    source = await session.scalar(
        select(ReferenceSource).order_by(ReferenceSource.imported_at.desc()).limit(1)
    )
    categories = (
        list(
            await session.scalars(
                select(ReferenceCategory).where(ReferenceCategory.source_id == source.id)
            )
        )
        if source is not None
        else []
    )
    category_ids = [category.id for category in categories]
    entries = (
        list(
            await session.scalars(
                select(ReferenceEntry).where(ReferenceEntry.category_id.in_(category_ids))
            )
        )
        if category_ids
        else []
    )
    reference_rows = _reference_rows(categories, entries)
    codes = await _taxonomy_codes(session)
    existing = {
        (item.reference_category_id, item.reference_key): item
        for item in await session.scalars(select(ReferenceTaxonomyMap))
    }
    for item in mappings:
        key = item["reference_key"]
        reference = reference_rows.get(key)
        if reference is None or reference[2] != item["reference_title"]:
            raise ValueError("Reference mapping key/title does not match the current library")
        category, heading_position, title = reference
        identity = (category.id, key)
        row = existing.get(identity)
        if item["target_code"] is None:
            continue
        kind = item["target_kind"]
        code = item["target_code"]
        if code not in codes[kind]:
            raise ValueError(f"Unknown {kind} taxonomy code")
        if (key.startswith("category:") and kind == "intent") or (
            key.startswith("heading:") and kind != "intent"
        ):
            raise ValueError(
                "Category groups map to sections/general functions; headings map to intents"
            )
        if row is None:
            row = ReferenceTaxonomyMap(
                reference_category_id=category.id,
                reference_key=key,
                reference_title=title,
                heading_position=heading_position,
            )
            session.add(row)
            existing[identity] = row
        row.reference_title = title
        row.target_kind = kind
        row.target_code = code
        row.review_status = item["review_status"]
        row.mapped_by = item["mapped_by"]
        row.note = item["note"]
    await session.commit()
    return len(mappings)
