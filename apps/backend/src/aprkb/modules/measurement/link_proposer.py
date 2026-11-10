"""Propose pattern-level links between catalog entries and slot-less Methods patterns.

Rule-based and review-gated (ADR-0015): a catalog name or alias in the pattern's current
frame creates a *proposed* link with ``origin="term_match"``. Nothing becomes public until
a curator approves it, and an existing link (including a rejected one) is never recreated.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.audit.service import record_event
from aprkb.modules.measurement import repository
from aprkb.modules.measurement.metric_check import MetricTerms, find_mentions
from aprkb.modules.measurement.models import MeasurementSlotLink
from aprkb.policies.schemas import MeasurementPolicy


@dataclass(frozen=True)
class LinkCandidate:
    pattern_id: UUID
    entry_code: str


def match_frames(
    frames: list[tuple[UUID, str]], entries: list[MetricTerms], *, min_term_length: int
) -> list[LinkCandidate]:
    """Pure step: every (pattern, entry) whose frame names the entry."""
    return [
        LinkCandidate(pattern_id, mention.code)
        for pattern_id, frame in frames
        for mention in find_mentions(frame, entries, min_term_length=min_term_length)
    ]


async def propose_links(
    session: AsyncSession,
    policy: MeasurementPolicy,
    *,
    request_id: str,
    dry_run: bool = False,
) -> dict[str, int]:
    frames = await repository.method_pattern_frames(session, policy.link_proposal_function_codes)
    entries = await repository.entry_terms(session)
    candidates = match_frames(frames, entries, min_term_length=policy.metric_check_min_term_length)
    created = existing = 0
    for candidate in candidates:
        entry = await repository.entry_by_code(session, candidate.entry_code)
        if entry is None:
            continue
        if dry_run:
            if await repository.find_link(
                session, entry_id=entry.id, pattern_id=candidate.pattern_id, slot_name=None
            ):
                existing += 1
            else:
                created += 1
            continue
        # ON CONFLICT DO NOTHING: a concurrent run or a manual proposal for the same
        # (entry, pattern, no slot) wins without failing this run.
        inserted = await session.scalar(
            insert(MeasurementSlotLink)
            .values(
                id=uuid4(),
                entry_id=entry.id,
                pattern_id=candidate.pattern_id,
                slot_name=None,
                review_status="proposed",
                origin="term_match",
            )
            .on_conflict_do_nothing()
            .returning(MeasurementSlotLink.id)
        )
        if inserted is None:
            existing += 1
        else:
            created += 1
    counts = {
        "patterns_scanned": len(frames),
        "matches": len(candidates),
        "created": created,
        "already_linked": existing,
    }
    if dry_run:
        await session.rollback()
        return counts
    await session.flush()
    await record_event(
        session,
        actor_id=None,
        action="measurement.links_proposed",
        entity_type="measurement_catalog",
        after=counts,
        request_id=request_id,
    )
    await session.commit()
    return counts
