"""Strict parser and transactional importer for the quarantined source export."""

import hashlib
import json
from dataclasses import dataclass
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
)

SOURCE_URL = "https://www.phrasebank.manchester.ac.uk/"
NOTICE = (
    "Source: University of Manchester Academic Phrasebank. Internal reference only; "
    "reuse rights are not verified; do not redistribute."
)
_MODULE_DIR = Path(__file__).parent
_ROOT_FIELDS = {
    "source",
    "status",
    "license_status",
    "page_count",
    "block_count",
    "table_count",
    "pages",
}
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
        if not isinstance(page, dict) or set(page) != _PAGE_FIELDS:
            raise ValueError("Invalid reference-library page structure")
        title = _required_text(page["title"], "page.title")
        page_url = _required_text(page["source_url"], "page.source_url")
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
        for block in blocks:
            if not isinstance(block, dict) or not {"block_id", "heading", "kind"} <= set(block):
                raise ValueError("Invalid reference-library block structure")
            _required_text(block["block_id"], "block.block_id")
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
                        heading, heading_position, "note", value, None, value, entry_position
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
    session: AsyncSession, library: ParsedLibrary, *, request_id: str
) -> dict[str, int]:
    """Replace one named source and write a content-free audit event atomically."""
    existing = await session.scalar(
        select(ReferenceSource).where(ReferenceSource.name == library.source_name)
    )
    if existing is not None:
        await session.execute(delete(ReferenceSource).where(ReferenceSource.id == existing.id))
    source = ReferenceSource(
        name=library.source_name,
        source_url=SOURCE_URL,
        license_status=library.license_status,
        rights_status=library.rights_status,
        status=library.status,
        content_sha256=library.content_sha256,
    )
    session.add(source)
    await session.flush()
    entry_count = 0
    for category in library.categories:
        row = ReferenceCategory(
            source_id=source.id,
            slug=category.slug,
            title=category.title,
            kind=category.kind,
            position=category.position,
            source_url=category.source_url,
        )
        session.add(row)
        await session.flush()
        session.add_all(
            [
                ReferenceEntry(
                    category_id=row.id,
                    heading=entry.heading,
                    heading_position=entry.heading_position,
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
    await session.commit()
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
