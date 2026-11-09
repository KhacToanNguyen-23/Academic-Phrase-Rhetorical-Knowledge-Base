"""Database queries for the measurement catalog."""

from uuid import UUID

from sqlalchemy import String, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from aprkb.modules.measurement.metric_check import MetricTerms
from aprkb.modules.measurement.models import (
    MeasurementEntry,
    MeasurementImportRun,
    MeasurementRelation,
    MeasurementSlotLink,
)
from aprkb.modules.patterns.models import PatternVersion, PhrasePattern

# Reading order: what is measured, how it is measured, then the procedure around it.
_KIND_ORDER = {"metric": 0, "method": 1, "protocol": 2}


def _like(query: str) -> str:
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def latest_catalog_version(session: AsyncSession) -> str | None:
    return await session.scalar(
        select(MeasurementImportRun.catalog_version)
        .order_by(MeasurementImportRun.imported_at.desc())
        .limit(1)
    )


async def search_entries(
    session: AsyncSession, *, kind: str | None, query: str | None, limit: int, offset: int
) -> tuple[list[MeasurementEntry], int]:
    statement = select(MeasurementEntry)
    if kind is not None:
        statement = statement.where(MeasurementEntry.kind == kind)
    if query:
        pattern = _like(query)
        statement = statement.where(
            or_(
                MeasurementEntry.code.ilike(pattern, escape="\\"),
                MeasurementEntry.name.ilike(pattern, escape="\\"),
                MeasurementEntry.definition.ilike(pattern, escape="\\"),
                cast(MeasurementEntry.aliases, String).ilike(pattern, escape="\\"),
            )
        )
    total = await session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = await session.scalars(
        statement.order_by(
            case(_KIND_ORDER, value=MeasurementEntry.kind, else_=len(_KIND_ORDER)),
            func.lower(MeasurementEntry.name),
        )
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total


async def entry_by_code(session: AsyncSession, code: str) -> MeasurementEntry | None:
    return await session.scalar(select(MeasurementEntry).where(MeasurementEntry.code == code))


async def relations_of(
    session: AsyncSession, entry_id: UUID
) -> list[tuple[str, str, MeasurementEntry]]:
    """Return (relation, direction, other entry) for both directions."""
    other = aliased(MeasurementEntry)
    outgoing = await session.execute(
        select(MeasurementRelation.relation, other)
        .join(other, other.id == MeasurementRelation.to_entry_id)
        .where(MeasurementRelation.from_entry_id == entry_id)
    )
    incoming = await session.execute(
        select(MeasurementRelation.relation, other)
        .join(other, other.id == MeasurementRelation.from_entry_id)
        .where(MeasurementRelation.to_entry_id == entry_id)
    )
    result = [(relation, "outgoing", entry) for relation, entry in outgoing.all()]
    result += [(relation, "incoming", entry) for relation, entry in incoming.all()]
    return sorted(result, key=lambda item: (item[1] != "outgoing", item[0], item[2].name))


async def links(
    session: AsyncSession,
    *,
    entry_id: UUID | None = None,
    pattern_id: UUID | None = None,
    slot_name: str | None = None,
    status: str | None = None,
) -> list[tuple[MeasurementSlotLink, MeasurementEntry, str | None]]:
    statement = (
        select(MeasurementSlotLink, MeasurementEntry, PatternVersion.canonical_frame)
        .join(MeasurementEntry, MeasurementEntry.id == MeasurementSlotLink.entry_id)
        .join(PhrasePattern, PhrasePattern.id == MeasurementSlotLink.pattern_id)
        .outerjoin(PatternVersion, PatternVersion.id == PhrasePattern.current_version_id)
        .order_by(MeasurementSlotLink.created_at, MeasurementSlotLink.id)
    )
    if entry_id is not None:
        statement = statement.where(MeasurementSlotLink.entry_id == entry_id)
    if pattern_id is not None:
        statement = statement.where(MeasurementSlotLink.pattern_id == pattern_id)
    if slot_name is not None:
        statement = statement.where(MeasurementSlotLink.slot_name == slot_name)
    if status is not None:
        statement = statement.where(MeasurementSlotLink.review_status == status)
    rows = await session.execute(statement)
    return [(link, entry, frame) for link, entry, frame in rows.all()]


async def current_slots(session: AsyncSession, pattern_id: UUID) -> dict[str, object] | None:
    """Slots of the pattern's current version, or None if the pattern does not exist."""
    pattern = await session.get(PhrasePattern, pattern_id)
    if pattern is None:
        return None
    if pattern.current_version_id is None:
        return {}
    version = await session.get(PatternVersion, pattern.current_version_id)
    return dict(version.slots or {}) if version is not None else {}


async def find_link(
    session: AsyncSession, *, entry_id: UUID, pattern_id: UUID, slot_name: str
) -> MeasurementSlotLink | None:
    return await session.scalar(
        select(MeasurementSlotLink).where(
            MeasurementSlotLink.entry_id == entry_id,
            MeasurementSlotLink.pattern_id == pattern_id,
            MeasurementSlotLink.slot_name == slot_name,
        )
    )


async def metric_terms(session: AsyncSession) -> list[MetricTerms]:
    """Names and aliases of catalog metrics, for the FR-08.2 report-only check."""
    rows = await session.scalars(
        select(MeasurementEntry)
        .where(MeasurementEntry.kind == "metric")
        .order_by(MeasurementEntry.code)
    )
    return [
        MetricTerms(code=entry.code, name=entry.name, terms=tuple(entry.aliases)) for entry in rows
    ]
