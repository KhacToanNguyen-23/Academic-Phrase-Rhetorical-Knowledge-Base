"""Candidate writer port that refuses unsourced mined output."""

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from aprkb.modules.mining.schemas import SlotDefinition, is_safe_masked_frame
from aprkb.policies.schemas import (
    ConstructionsPolicy,
    ConstructionVerbGroupPolicy,
    HybridConstructionsPolicy,
    LeadInsPolicy,
    ReportingVerbsPolicy,
    is_safe_construction_frame,
    is_safe_hybrid_frame,
)


@dataclass(frozen=True)
class CandidateDraft:
    canonical_frame: str
    source_sentence_ids: list[UUID]
    slots: dict[str, SlotDefinition] = field(default_factory=dict)
    confidence: float | None = None
    epistemic_strength: str | None = None
    cluster_key: str | None = None
    occurrences: list[dict[str, object]] = field(default_factory=list)
    construction_id: str | None = None


class CandidateRepository(Protocol):
    def create_candidate(self, draft: CandidateDraft) -> object: ...


class CandidateWriter:
    def __init__(
        self,
        repository: CandidateRepository | None,
        *,
        reporting_policy: ReportingVerbsPolicy | None = None,
        constructions_policy: ConstructionsPolicy | None = None,
        verb_group_policy: ConstructionVerbGroupPolicy | None = None,
        lead_ins_policy: LeadInsPolicy | None = None,
        hybrid_policy: HybridConstructionsPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._reporting_forms = (
            reporting_policy.all_forms if reporting_policy is not None else set()
        )
        self._constructions = constructions_policy
        self._verb_group_policy = verb_group_policy
        self._lead_ins = lead_ins_policy.lead_ins if lead_ins_policy is not None else []
        self._hybrid = hybrid_policy

    def write(self, draft: CandidateDraft) -> object:
        if not draft.source_sentence_ids:
            raise ValueError("source_sentence_ids are required for every mined candidate")
        reporting_safe = is_safe_masked_frame(
            draft.canonical_frame, self._reporting_forms, self._lead_ins
        )
        construction_safe = (
            draft.construction_id is not None
            and self._constructions is not None
            and is_safe_construction_frame(
                draft.canonical_frame,
                self._constructions,
                construction_id=draft.construction_id,
                verb_group_policy=self._verb_group_policy,
            )
        )
        hybrid_safe = self._hybrid is not None and is_safe_hybrid_frame(
            draft.canonical_frame, self._hybrid, draft.cluster_key
        )
        if not reporting_safe and not construction_safe and not hybrid_safe:
            raise ValueError("canonical_frame must be a masked positional frame")
        if self._repository is None:
            raise RuntimeError("Candidate repository is not configured")
        try:
            typed_slots = {
                name: SlotDefinition.model_validate(slot) for name, slot in draft.slots.items()
            }
        except (TypeError, ValueError) as error:
            raise ValueError("slots must contain typed slot definitions") from error
        if any(not name or len(name) > 16 for name in typed_slots):
            raise ValueError("slot names must be short positional names")
        draft = CandidateDraft(
            canonical_frame=draft.canonical_frame,
            source_sentence_ids=draft.source_sentence_ids,
            slots=typed_slots,
            confidence=None,
            epistemic_strength=draft.epistemic_strength,
            cluster_key=draft.cluster_key,
            occurrences=draft.occurrences,
            construction_id=draft.construction_id,
        )
        return self._repository.create_candidate(draft)
