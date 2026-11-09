"""Versioned validation rule registry."""

from aprkb.modules.validation.rules.base import RuleResult, Severity, ValidationRule
from aprkb.modules.validation.rules.not_applicable import NotApplicableValidationRule
from aprkb.modules.validation.rules.todo import TodoValidationRule
from aprkb.modules.validation.rules.v02_claim_evidence import V02ClaimEvidenceRule
from aprkb.modules.validation.rules.v03_grounding import V03GroundingRule
from aprkb.modules.validation.rules.v06_style import V06StyleRule
from aprkb.policies.evidence import EvidencePolicy
from aprkb.policies.schemas import EpistemicMarkersPolicy, ValidationRulesPolicy


def build_rules(
    *,
    evidence_policy: EvidencePolicy,
    lexicon: EpistemicMarkersPolicy,
    policy: ValidationRulesPolicy,
) -> list[ValidationRule]:
    # FR-08.6: preserve the V01–V08 response contract; unfinished checks are
    # unavailable, never passing.
    rules: list[ValidationRule] = []
    for number in range(1, 9):
        code = f"V{number:02}"
        setting = policy.rules.get(code)
        if code == "V05":
            # The Online Writer validates one sentence. Journal-wide compliance
            # is intentionally outside this flow; writers already use journal
            # guidance when choosing a target journal.
            rules.append(
                NotApplicableValidationRule(
                    code,
                    "FR-08.4",
                    "Journal guideline compliance is outside sentence validation.",
                )
            )
        elif code == "V02" and setting is not None and setting.enabled:
            rules.append(
                V02ClaimEvidenceRule(
                    evidence_policy=evidence_policy,
                    lexicon=lexicon,
                    severity=Severity(setting.severity),
                )
            )
        elif code == "V03" and setting is not None and setting.enabled:
            rules.append(V03GroundingRule(Severity(setting.severity)))
        elif code == "V06" and setting is not None and setting.enabled:
            rules.append(V06StyleRule(policy.style_warning_phrases))
        else:
            rules.append(TodoValidationRule(code, f"PRD-6.2-{code}"))
    return rules


__all__ = ["RuleResult", "Severity", "ValidationRule", "build_rules"]
