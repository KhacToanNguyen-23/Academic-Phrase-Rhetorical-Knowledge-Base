"""Versioned validation rule registry."""

from aprkb.modules.validation.rules.base import RuleResult, Severity, ValidationRule
from aprkb.modules.validation.rules.todo import TodoValidationRule
from aprkb.modules.validation.rules.v02_claim_evidence import V02ClaimEvidenceRule
from aprkb.policies.evidence import EvidencePolicy
from aprkb.policies.schemas import EpistemicMarkersPolicy, ValidationRulesPolicy


def build_rules(
    *,
    evidence_policy: EvidencePolicy,
    lexicon: EpistemicMarkersPolicy,
    policy: ValidationRulesPolicy,
) -> list[ValidationRule]:
    rules: list[ValidationRule] = []
    for number in range(1, 9):
        code = f"V{number:02}"
        setting = policy.rules.get(code)
        if code == "V02" and setting is not None and setting.enabled:
            rules.append(
                V02ClaimEvidenceRule(
                    evidence_policy=evidence_policy,
                    lexicon=lexicon,
                    severity=Severity(setting.severity),
                )
            )
        else:
            rules.append(TodoValidationRule(code, f"PRD-6.2-{code}"))
    return rules


__all__ = ["RuleResult", "Severity", "ValidationRule", "build_rules"]
