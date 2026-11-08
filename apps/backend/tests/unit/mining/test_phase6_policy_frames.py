"""Phase-6 checks for closed lead-in policy and frame validation."""

from pathlib import Path
from uuid import uuid4

import yaml

from aprkb.modules.extraction.service import _is_safe
from aprkb.modules.mining.candidate_writer import CandidateDraft, CandidateWriter
from aprkb.modules.mining.models import Candidate
from aprkb.modules.mining.schemas import is_safe_masked_frame
from aprkb.policies.loader import load_policy_bundle

_APPROVED = {
    "in this paper",
    "however",
    "moreover",
    "furthermore",
    "in addition",
    "overall",
    "in particular",
    "for example",
    "in contrast",
}


def test_lead_ins_yaml_contains_exactly_owner_approved_set():
    policy_path = (
        Path(__file__).parents[3] / "src" / "aprkb" / "policies" / "lexicon" / "lead_ins.yaml"
    )
    payload = yaml.safe_load(policy_path.read_text(encoding="utf-8"))

    assert payload["version"] == "0.2.0"
    assert {
        value.strip().removesuffix(",").casefold() for value in payload["lead_ins"]
    } == _APPROVED


def test_safe_masked_frame_accepts_only_approved_optional_lead_in():
    policies = load_policy_bundle()
    forms = policies.reporting_verbs.all_forms
    lead_ins = policies.lead_ins.lead_ins

    assert is_safe_masked_frame("In this paper, [X] show that [Y].", forms, lead_ins)
    assert is_safe_masked_frame("[X] show that [Y].", forms, lead_ins)
    assert not is_safe_masked_frame("Recently, [X] show that [Y].", forms, lead_ins)
    assert not is_safe_masked_frame("[X] [injected] show that [Y].", forms, lead_ins)


def test_candidate_writer_and_extraction_safety_use_the_policy_lead_ins():
    policies = load_policy_bundle()

    class Repository:
        def create_candidate(self, draft):
            return draft

    writer = CandidateWriter(
        Repository(),
        reporting_policy=policies.reporting_verbs,
        lead_ins_policy=policies.lead_ins,
    )
    accepted = CandidateDraft(
        canonical_frame="In this paper, [X] show that [Y].",
        source_sentence_ids=[uuid4()],
    )
    writer.write(accepted)
    assert _is_safe(Candidate(canonical_frame=accepted.canonical_frame, slots={}))
    assert not _is_safe(Candidate(canonical_frame="Recently, [X] show that [Y].", slots={}))
