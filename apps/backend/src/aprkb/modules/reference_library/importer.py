"""Strict parser and transactional importer for the quarantined source export."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml  # type: ignore[import-untyped]
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.audit.service import record_event
from aprkb.modules.reference_library.models import (
    ReferenceCategory,
    ReferenceEntry,
    ReferenceSource,
    ReferenceTaxonomyMap,
)

SOURCE_URL = "https://www.phrasebank.manchester.ac.uk/"
NOTICE = (
    "Source: University of Manchester Academic Phrasebank. Internal reference only; "
    "reuse rights are not verified; do not redistribute."
)
_MODULE_DIR = Path(__file__).parent
_MAPPING_CONFIG = _MODULE_DIR / "taxonomy-mapping.yaml"
_ROOT_FIELDS = {
    "source",
    "status",
    "license_status",
    "page_count",
    "block_count",
    "table_count",
    "pages",
}
_OPTIONAL_PAGE_FIELDS = {"extraction_method"}
_PAGE_FIELDS = {
    "title",
    "source_url",
    "resolved_url",
    "captured_at",
    "html_sha256",
    "source_category",
    "license_status",
    "rights_status",
    "status",
    "note",
    "blocks",
}


@dataclass(frozen=True)
class ParsedEntry:
    heading: str
    heading_position: int
    block_index: int
    block_id: str | int
    kind: str
    text: str | None
    cells: list[list[str]] | None
    search_text: str
    position: int


@dataclass(frozen=True)
class ParsedCategory:
    slug: str
    title: str
    kind: str
    source_url: str
    resolved_url: str
    captured_at: str
    html_sha256: str
    source_category: str
    license_status: str
    rights_status: str
    status: str
    note: str
    extraction_method: str | None
    position: int
    entries: list[ParsedEntry]


@dataclass(frozen=True)
class ParsedLibrary:
    source_name: str
    status: str
    license_status: str
    rights_status: str
    content_sha256: str
    categories: list[ParsedCategory]
    block_count: int
    table_count: int


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid reference-library field: {field}")
    return value.strip()


def _block_id(value: Any) -> None:
    """Accept a non-empty string or a non-negative integer, as scrapers emit either."""
    if isinstance(value, bool) or not (
        (isinstance(value, int) and value >= 0) or (isinstance(value, str) and value.strip())
    ):
        raise ValueError("Invalid reference-library field: block.block_id")


def _source_block_id(value: Any) -> str | int:
    _block_id(value)
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        return value
    raise ValueError("Invalid reference-library field: block.block_id")


def _sections() -> set[str]:
    data = yaml.safe_load((_MODULE_DIR / "categories.yaml").read_text(encoding="utf-8"))
    sections = data.get("sections") if isinstance(data, dict) else None
    if not isinstance(sections, list) or not all(isinstance(item, str) for item in sections):
        raise RuntimeError("Reference category configuration is invalid")
    return set(sections)


def parse_document(payload: Any, raw: bytes) -> ParsedLibrary:
    """Validate structure and extract entry payloads without logging source text."""
    if not isinstance(payload, dict) or set(payload) != _ROOT_FIELDS:
        raise ValueError("Invalid reference-library document structure")
    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("Reference-library document must contain pages")
    source = payload["source"]
    source_name = _required_text(
        source.get("name") if isinstance(source, dict) else source, "source"
    )
    if isinstance(source, dict) and "url" in source:
        _required_text(source["url"], "source.url")
    status = _required_text(payload["status"], "status")
    license_status = _required_text(payload["license_status"], "license_status")
    for name in ("page_count", "block_count", "table_count"):
        if not isinstance(payload[name], int) or payload[name] < 0:
            raise ValueError(f"Invalid reference-library field: {name}")

    categories: list[ParsedCategory] = []
    block_total = 0
    table_total = 0
    section_titles = _sections()
    for page_position, page in enumerate(pages):
        if (
            not isinstance(page, dict)
            or not set(page) >= _PAGE_FIELDS
            or not set(page) <= _PAGE_FIELDS | _OPTIONAL_PAGE_FIELDS
        ):
            raise ValueError("Invalid reference-library page structure")
        if "extraction_method" in page:
            _required_text(page["extraction_method"], "page.extraction_method")
        try:
            datetime.fromisoformat(page["captured_at"].replace("Z", "+00:00"))
        except (KeyError, AttributeError, TypeError, ValueError) as exc:
            raise ValueError("Invalid reference-library field: page.captured_at") from exc
        digest = page.get("html_sha256")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in digest)
        ):
            raise ValueError("Invalid reference-library field: page.html_sha256")
        title = _required_text(page["title"], "page.title")
        page_url = _required_text(page["source_url"], "page.source_url")
        resolved_url = _required_text(page["resolved_url"], "page.resolved_url")
        for field in _PAGE_FIELDS - {"title", "source_url", "blocks"}:
            _required_text(page[field], f"page.{field}")
        blocks = page["blocks"]
        if not isinstance(blocks, list):
            raise ValueError("Invalid reference-library blocks")
        if not blocks or not isinstance(blocks[0], dict) or blocks[0].get("heading") != title:
            raise ValueError("First reference block heading must match page title")
        entries: list[ParsedEntry] = []
        current_heading = title
        heading_position = 0
        entry_position = 0
        for block_index, block in enumerate(blocks):
            if not isinstance(block, dict) or not {"block_id", "heading", "kind"} <= set(block):
                raise ValueError("Invalid reference-library block structure")
            _block_id(block["block_id"])
            heading = _required_text(block["heading"], "block.heading")
            kind = block["kind"]
            if kind not in {"paragraph", "table"}:
                raise ValueError("Invalid reference-library block kind")
            if heading != current_heading:
                current_heading = heading
                heading_position += 1
            if kind == "paragraph":
                if set(block) != {"block_id", "heading", "kind", "lines"}:
                    raise ValueError("Invalid paragraph block structure")
                lines = block["lines"]
                if (
                    not isinstance(lines, list)
                    or not lines
                    or not all(isinstance(line, str) and line.strip() for line in lines)
                ):
                    raise ValueError("Invalid paragraph block")
                value = "\n".join(line.strip() for line in lines)
                entries.append(
                    ParsedEntry(
                        heading,
                        heading_position,
                        block_index,
                        _source_block_id(block["block_id"]),
                        "note",
                        value,
                        None,
                        value,
                        entry_position,
                    )
                )
                entry_position += 1
            else:
                if set(block) != {"block_id", "heading", "kind", "rows"}:
                    raise ValueError("Invalid table block structure")
                rows = block["rows"]
                if not isinstance(rows, list) or not rows:
                    raise ValueError("Invalid table block")
                for row in rows:
                    if not isinstance(row, list) or not 2 <= len(row) <= 5:
                        raise ValueError("Invalid phrase row")
                    cells = [
                        [alt.strip() for alt in cell.splitlines() if alt.strip()]
                        for cell in (_required_text(cell, "table.cell") for cell in row)
                    ]
                    search_text = " ".join(alt for cell in cells for alt in cell)
                    entries.append(
                        ParsedEntry(
                            heading,
                            heading_position,
                            block_index,
                            _source_block_id(block["block_id"]),
                            "phrase",
                            None,
                            cells,
                            search_text,
                            entry_position,
                        )
                    )
                    entry_position += 1
                table_total += 1
            block_total += 1
        slug = urlparse(page_url).path.rstrip("/").split("/")[-1]
        if not slug:
            raise ValueError("Category source URL must end in a slug")
        categories.append(
            ParsedCategory(
                slug=slug,
                title=title,
                kind="section" if title in section_titles else "function",
                source_url=page_url,
                resolved_url=resolved_url,
                captured_at=page["captured_at"],
                html_sha256=page["html_sha256"],
                source_category=page["source_category"],
                license_status=page["license_status"],
                rights_status=page["rights_status"],
                status=page["status"],
                note=page["note"],
                extraction_method=page.get("extraction_method"),
                position=page_position,
                entries=entries,
            )
        )
    if block_total != payload["block_count"] or table_total != payload["table_count"]:
        raise ValueError("Reference-library declared counts do not match document")
    if len(pages) != payload["page_count"]:
        raise ValueError("Reference-library page count does not match document")
    rights = _required_text(pages[0]["rights_status"], "page.rights_status")
    return ParsedLibrary(
        source_name,
        status,
        license_status,
        rights,
        hashlib.sha256(raw).hexdigest(),
        categories,
        block_total,
        table_total,
    )


def load_document(path: Path) -> ParsedLibrary:
    raw = path.read_bytes()
    return parse_document(json.loads(raw), raw)


async def import_library(
    session: AsyncSession,
    library: ParsedLibrary,
    *,
    request_id: str,
    commit: bool = True,
    seed_mappings: bool = True,
) -> dict[str, int]:
    """Replace one named source and write a content-free audit event atomically."""
    existing = await session.scalar(
        select(ReferenceSource).where(ReferenceSource.name == library.source_name)
    )
    source = existing or ReferenceSource(name=library.source_name, source_url=SOURCE_URL)
    source.source_url = SOURCE_URL
    source.license_status = library.license_status
    source.rights_status = library.rights_status
    source.status = library.status
    source.content_sha256 = library.content_sha256
    source.imported_at = datetime.now(UTC)
    session.add(source)
    await session.flush()
    existing_categories = list(
        await session.scalars(
            select(ReferenceCategory).where(ReferenceCategory.source_id == source.id)
        )
    )
    categories_by_slug = {category.slug: category for category in existing_categories}
    retained_category_ids: set[str] = set()
    entry_count = 0
    mapping_config = (
        yaml.safe_load(_MAPPING_CONFIG.read_text(encoding="utf-8")) if seed_mappings else {}
    )
    for category in library.categories:
        row = categories_by_slug.get(category.slug)
        if row is None:
            row = ReferenceCategory(source_id=source.id, slug=category.slug)
        row.title = category.title
        row.kind = category.kind
        row.position = category.position
        row.source_url = category.source_url
        row.resolved_url = category.resolved_url
        row.captured_at = category.captured_at
        row.html_sha256 = category.html_sha256
        row.source_category = category.source_category
        row.license_status = category.license_status
        row.rights_status = category.rights_status
        row.status = category.status
        row.note = category.note
        row.extraction_method = category.extraction_method
        session.add(row)
        await session.flush()
        retained_category_ids.add(str(row.id))
        await session.execute(delete(ReferenceEntry).where(ReferenceEntry.category_id == row.id))
        session.add_all(
            [
                ReferenceEntry(
                    category_id=row.id,
                    heading=entry.heading,
                    heading_position=entry.heading_position,
                    block_index=entry.block_index,
                    block_id=entry.block_id,
                    kind=entry.kind,
                    text=entry.text,
                    cells=entry.cells,
                    search_text=entry.search_text,
                    position=entry.position,
                )
                for entry in category.entries
            ]
        )
        entry_count += len(category.entries)
        existing_mappings = {
            mapping.reference_key: mapping
            for mapping in await session.scalars(
                select(ReferenceTaxonomyMap).where(
                    ReferenceTaxonomyMap.reference_category_id == row.id
                )
            )
        }
        heading_titles = {entry.heading_position: entry.heading for entry in category.entries}
        stale_mapping_keys: list[str] = []
        for key, mapping in existing_mappings.items():
            current_title = (
                heading_titles.get(mapping.heading_position)
                if mapping.heading_position is not None
                else category.title
            )
            if current_title is None or current_title != mapping.reference_title:
                stale_mapping_keys.append(key)
        for key in stale_mapping_keys:
            await session.delete(existing_mappings.pop(key))
        for mapping in mapping_config.get("mappings", []):
            if mapping["reference_slug"] != category.slug:
                continue
            map_key = f"category:{category.slug}"
            if map_key not in existing_mappings:
                session.add(
                    ReferenceTaxonomyMap(
                        reference_category_id=row.id,
                        reference_key=map_key,
                        reference_title=category.title,
                        heading_position=None,
                        target_kind=mapping["target_kind"],
                        target_code=mapping["target_code"],
                        review_status=mapping.get("review_status", "proposed"),
                        mapped_by="seed-config",
                        note=mapping.get("note"),
                    )
                )
    stale_category_ids = [
        category.id
        for category in existing_categories
        if str(category.id) not in retained_category_ids
    ]
    if stale_category_ids:
        await session.execute(
            delete(ReferenceCategory).where(ReferenceCategory.id.in_(stale_category_ids))
        )
    counts = {
        "categories": len(library.categories),
        "entries": entry_count,
        "blocks": library.block_count,
        "tables": library.table_count,
    }
    await record_event(
        session,
        actor_id=None,
        action="reference_library.import",
        entity_type="reference_source",
        entity_id=source.id,
        after={"counts": counts, "content_sha256": library.content_sha256},
        request_id=request_id,
    )
    if commit:
        await session.commit()
    else:
        await session.flush()
    return counts


async def purge_library(session: AsyncSession, *, request_id: str) -> int:
    count = len(list(await session.scalars(select(ReferenceSource.id))))
    await record_event(
        session,
        actor_id=None,
        action="reference_library.purge",
        entity_type="reference_source",
        after={"source_count": count},
        request_id=request_id,
    )
    await session.execute(delete(ReferenceSource))
    await session.commit()
    return count
