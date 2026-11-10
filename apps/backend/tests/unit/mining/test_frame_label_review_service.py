from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from aprkb.modules.identity.models import ApiClient
from aprkb.modules.mining import label_review_service
from aprkb.modules.mining.label_review_schemas import (
    BulkFrameLabelReviewCreate,
    FrameLabelDecision,
)
from aprkb.modules.mining.models import Candidate, CandidateLabel


@pytest.mark.asyncio
async def test_bulk_review_edit_confirms_value_and_audits_only_label_data(monkeypatch) -> None:
    candidate_id = uuid4()
    reviewer_id = uuid4()
    row = CandidateLabel(
        candidate_id=candidate_id,
        label_code="intent",
        value=None,
        status="proposed",
        source="ai:2pass",
        confidence=None,
        options=[{"pass": "a", "value": "unclear"}],
        needs_attention=True,
        agreement="disagree",
    )
    candidate = Candidate(
        id=candidate_id,
        canonical_frame="[X] report [Y]",
        slots={},
        source_sentence_ids=[],
        status="pending",
    )
    monkeypatch.setattr(label_review_service, "lock_candidate", AsyncMock(return_value=candidate))
    monkeypatch.setattr(
        label_review_service.repository,
        "lock_candidate_label",
        AsyncMock(return_value=row),
    )
    audit = AsyncMock()
    monkeypatch.setattr(label_review_service, "record_event", audit)
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    reviewer = ApiClient(id=reviewer_id, name="reviewer", role="reviewer", is_active=True)

    result = await label_review_service.decide_frame_labels(
        session,
        payload=BulkFrameLabelReviewCreate(
            decisions=[
                FrameLabelDecision(
                    candidate_id=candidate_id,
                    label_code="intent",
                    decision="edit",
                    value="report_finding",
                )
            ]
        ),
        reviewer=reviewer,
        request_id="request-id",
    )

    assert result.decisions_applied == 1
    assert row.status == "confirmed"
    assert row.value == "report_finding"
    assert row.source == "human"
    assert row.reviewer_id == reviewer_id
    assert isinstance(row.reviewed_at, datetime) and row.reviewed_at.tzinfo == UTC
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()
    after = audit.await_args.kwargs["after"]
    assert after["labels"] == [
        {
            "label_code": "intent",
            "before_value": None,
            "after_value": "report_finding",
        }
    ]


@pytest.mark.asyncio
async def test_review_reject_clears_value_and_invalid_code_rolls_back(monkeypatch) -> None:
    candidate_id = uuid4()
    reviewer = ApiClient(id=uuid4(), name="reviewer", role="reviewer", is_active=True)
    row = CandidateLabel(
        candidate_id=candidate_id,
        label_code="intent",
        value="report_finding",
        status="proposed",
        source="ai:2pass",
    )
    monkeypatch.setattr(
        label_review_service,
        "lock_candidate",
        AsyncMock(
            return_value=Candidate(
                id=candidate_id,
                canonical_frame="[X] report [Y]",
                slots={},
                source_sentence_ids=[],
                status="pending",
            )
        ),
    )
    monkeypatch.setattr(
        label_review_service.repository,
        "lock_candidate_label",
        AsyncMock(return_value=row),
    )
    monkeypatch.setattr(label_review_service, "record_event", AsyncMock())
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    await label_review_service.decide_frame_labels(
        session,
        payload=BulkFrameLabelReviewCreate(
            decisions=[
                FrameLabelDecision(
                    candidate_id=candidate_id, label_code="intent", decision="reject"
                )
            ]
        ),
        reviewer=reviewer,
        request_id="request-id",
    )
    assert row.status == "rejected" and row.value is None

    invalid_session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    with pytest.raises(HTTPException) as error:
        await label_review_service.decide_frame_labels(
            invalid_session,
            payload=BulkFrameLabelReviewCreate(
                decisions=[
                    FrameLabelDecision(
                        candidate_id=candidate_id,
                        label_code="intent",
                        decision="edit",
                        value="made_up_intent",
                    )
                ]
            ),
            reviewer=reviewer,
            request_id="request-id",
        )
    assert error.value.status_code == 422
    invalid_session.rollback.assert_awaited_once()
