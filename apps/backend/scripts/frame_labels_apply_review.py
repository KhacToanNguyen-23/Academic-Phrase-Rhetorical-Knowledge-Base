"""Apply local workbook decisions through the authenticated label-review service."""

import argparse
import asyncio
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from aprkb.core.config import settings
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.mining.label_review_schemas import BulkFrameLabelReviewCreate
from aprkb.modules.mining.label_review_service import decide_frame_labels
from aprkb.modules.mining.labelers import vocabulary_codes
from aprkb.modules.mining.review_workbook import read_review_decisions
from aprkb.policies.loader import load_policy_bundle

DEFAULT_WORKBOOK = Path(__file__).resolve().parents[3] / "tmp" / "shared-frames-curation.xlsx"


async def apply_review(*, workbook_path: Path, reviewer_id: UUID, dry_run: bool) -> int:
    decisions = read_review_decisions(workbook_path)
    if dry_run:
        valid_codes = vocabulary_codes(load_policy_bundle().frame_label_vocabulary)
        if any(
            decision.label_code not in valid_codes
            or (
                decision.value is not None
                and decision.value not in valid_codes[decision.label_code]
            )
            for decision in decisions
        ):
            raise ValueError("Workbook contains a label outside the approved vocabulary")
        return len(decisions)
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    applied = 0
    try:
        async with factory() as session:
            reviewer = await session.get(ApiClient, reviewer_id)
            if (
                reviewer is None
                or not reviewer.is_active
                or reviewer.role not in {"reviewer", "curator", "admin"}
            ):
                raise ValueError("Reviewer id is not an active review-capable API client")
            for offset in range(0, len(decisions), 200):
                payload = BulkFrameLabelReviewCreate(decisions=decisions[offset : offset + 200])
                result = await decide_frame_labels(
                    session,
                    payload=payload,
                    reviewer=reviewer,
                    request_id="frame-label-workbook-review",
                )
                applied += result.decisions_applied
    finally:
        await engine.dispose()
    return applied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewer-id", type=UUID, required=True)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    count = asyncio.run(
        apply_review(
            workbook_path=args.workbook,
            reviewer_id=args.reviewer_id,
            dry_run=args.dry_run,
        )
    )
    action = "would apply" if args.dry_run else "applied"
    print(f"{action} {count} frame-label decisions.")


if __name__ == "__main__":
    main()
