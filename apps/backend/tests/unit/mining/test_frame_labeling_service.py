from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql

from aprkb.modules.mining.candidate_label_repository import proposal_upsert_statement
from aprkb.modules.mining.label_merge import MergedFrameLabel
from aprkb.modules.mining.labelers import (
    AI_LABEL_FIELDS,
    FrameLabelingQuotaError,
    FrameLabelOutput,
    FrameLabelPayload,
    ProposedFrameLabel,
)
from aprkb.modules.mining.labeling_service import (
    CandidateSourceMetadata,
    _pass_order,
    _run_two_passes,
    frame_label_eligibility,
)
from aprkb.policies.loader import load_policy_bundle


class FakeFrameLabeler:
    model = "fake"
    prompt_version = "fake-a-b"
    total_tokens = 0

    def __init__(self, failure: str | None = None) -> None:
        self.failure = failure
        self.calls: list[tuple[str, list[UUID]]] = []

    async def label_batch(self, *, frames: list[FrameLabelPayload], prompt_variant: str):
        self.calls.append((prompt_variant, [frame.candidate_id for frame in frames]))
        if self.failure == "quota" and prompt_variant == "a":
            raise FrameLabelingQuotaError(3600)
        if self.failure == "missing_frame" and prompt_variant == "b":
            return []
        outputs = []
        for frame in frames:
            labels = {
                field: ProposedFrameLabel(
                    value="unclear", confidence=0.5, evidence="Not enough context"
                )
                for field in AI_LABEL_FIELDS
            }
            if self.failure == "invalid_code":
                labels["intent"] = ProposedFrameLabel(value="not_a_vocabulary_code", confidence=0.9)
            outputs.append(FrameLabelOutput(candidate_id=frame.candidate_id, labels=labels))
        return outputs


def _source(
    sentence_id: UUID,
    article_id: UUID,
    section: str | None,
    *,
    allows_mining: bool = True,
    allows_display: bool = True,
) -> CandidateSourceMetadata:
    return CandidateSourceMetadata(
        sentence_id=sentence_id,
        article_id=article_id,
        section_code=section,
        genre_code=None,
        license_code="CC-BY",
        allows_mining=allows_mining,
        allows_display=allows_display,
    )


def test_label_job_skips_rights_denied_and_ii2_frames_before_payload_build() -> None:
    first, second = uuid4(), uuid4()
    denied = frame_label_eligibility(
        source_sentence_ids=[first, second],
        source_rows=[
            _source(first, uuid4(), "RESULTS"),
            _source(second, uuid4(), "RESULTS", allows_display=False),
        ],
        threshold=0.6,
    )
    assert denied.eligible is False
    assert denied.reason == "rights_denied_or_source_missing"

    one_article = uuid4()
    ii2 = frame_label_eligibility(
        source_sentence_ids=[first],
        source_rows=[_source(first, one_article, None)],
        threshold=0.6,
    )
    assert ii2.eligible is False
    assert ii2.reason == "unknown_single_paper"

    valid = frame_label_eligibility(
        source_sentence_ids=[first, second],
        source_rows=[_source(first, uuid4(), "METHODS"), _source(second, uuid4(), "RESULTS")],
        threshold=0.6,
    )
    assert valid.eligible is True


def test_independent_passes_use_distinct_order_and_batch_composition() -> None:
    payloads = [
        FrameLabelPayload(
            candidate_id=UUID(int=index + 1),
            canonical_frame="[X] report [Y]",
            family="Tier 1",
            epistemic_strength=None,
            paper_count=2,
            observed_section_counts={"RESULTS": 2},
        )
        for index in range(5)
    ]
    pass_a = _pass_order(payloads, 2, "a")
    pass_b = _pass_order(payloads, 2, "b")
    assert pass_a[0] != pass_b[0]
    assert {item.candidate_id for item in pass_a[0]} != {item.candidate_id for item in pass_b[0]}


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["invalid_code", "missing_frame"])
async def test_fake_labeler_invalid_or_missing_frame_is_label_failed(failure: str) -> None:
    candidate_id = uuid4()
    payload = FrameLabelPayload(
        candidate_id=candidate_id,
        canonical_frame="[X] report [Y]",
        family="Tier 1",
        epistemic_strength=None,
        paper_count=2,
        observed_section_counts={"RESULTS": 2},
    )
    result_a, result_b, _calls, failed, _stopped = await _run_two_passes(
        [(None, payload, {})],  # type: ignore[list-item]
        labeler=FakeFrameLabeler(failure=failure),
        batch_size=4,
        vocabulary=load_policy_bundle().frame_label_vocabulary,
    )
    assert candidate_id in failed
    if failure == "invalid_code":
        assert candidate_id not in result_a or candidate_id not in result_b


@pytest.mark.asyncio
async def test_fake_labeler_quota_failure_is_sanitized_and_resumable() -> None:
    candidate_id = uuid4()
    payload = FrameLabelPayload(
        candidate_id=candidate_id,
        canonical_frame="[X] report [Y]",
        family="Tier 1",
        epistemic_strength=None,
        paper_count=2,
        observed_section_counts={"RESULTS": 2},
    )
    _pass_a, _pass_b, _calls, _failed, stopped = await _run_two_passes(
        [(None, payload, {})],  # type: ignore[list-item]
        labeler=FakeFrameLabeler(failure="quota"),
        batch_size=4,
        vocabulary=load_policy_bundle().frame_label_vocabulary,
    )
    assert stopped == "quota"


def test_proposal_upsert_conflict_update_preserves_confirmed_and_rejected_rows() -> None:
    statement = proposal_upsert_statement(
        uuid4(),
        MergedFrameLabel(
            label_code="intent",
            value="report_finding",
            status="proposed",
            source="ai:2pass",
            confidence=0.8,
            options=[],
            needs_attention=False,
            agreement="both_agree",
        ),
        run_id="fake-run",
    )
    compiled = statement.compile(dialect=postgresql.dialect())
    assert "WHERE candidate_labels.status =" in str(compiled)
    assert "proposed" in compiled.params.values()
