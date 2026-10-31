"""Recommendation hard gates in PRD order."""

from aprkb.modules.journals.guideline_policy import GuidelinePolicy
from aprkb.modules.recommendation.gates.approval import ApprovalGate
from aprkb.modules.recommendation.gates.base import GateResult, HardGate
from aprkb.modules.recommendation.gates.evidence import EvidenceGate
from aprkb.modules.recommendation.gates.guideline import GuidelineGate
from aprkb.modules.recommendation.gates.intent_section import IntentSectionGate
from aprkb.modules.recommendation.gates.license import LicenseGate
from aprkb.modules.recommendation.gates.retired import RetiredGate
from aprkb.policies.evidence import EvidencePolicy


def build_gates(
    *, evidence_policy: EvidencePolicy, guideline_policy: GuidelinePolicy | None = None
) -> list[HardGate]:
    return [
        ApprovalGate(),
        RetiredGate(),
        LicenseGate(),
        IntentSectionGate(),
        EvidenceGate(evidence_policy),
        GuidelineGate(guideline_policy),
    ]


__all__ = ["GateResult", "HardGate", "build_gates"]
