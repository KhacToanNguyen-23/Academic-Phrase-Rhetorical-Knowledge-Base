"""Unit tests for the pluggable guideline rule evaluation seam."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from aprkb.modules.journals.guideline_evaluators import GuidelineEvaluatorRegistry
from aprkb.modules.journals.guideline_policy import GuidelinePolicy
from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.gates.base import GateResult
from aprkb.modules.recommendation.gates.guideline import GuidelineGate
from aprkb.modules.recommendation.pattern_view import PatternView


def pattern() -> PatternView:
    return PatternView(
        pattern_version_id=uuid4(),
        status="approved",
        intent_code="report_finding",
        canonical_frame="The results {verb} that {finding}.",
        claim_type="causal",
        epistemic_strength="moderate",
        allowed_sections=("results",),
        allowed_genres=(),
        source_type="authored",
        license_allows_display=True,
    )


def context(journal_id: UUID | None) -> RecommendationContext:
    return RecommendationContext(
        intent_code="report_finding",
        section_code="results",
        genre_code=None,
        journal_id=journal_id,
        claim_type="causal",
        evidence_level="single_study",
        discipline_code=None,
        client_id=uuid4(),
    )


@dataclass
class FakeEvaluator:
    rule_type: str
    result: GateResult
    calls: list[tuple[PatternView, dict[str, object], RecommendationContext]] = field(
        default_factory=list
    )

    def evaluate(
        self,
        pattern: PatternView,
        payload: dict[str, object],
        ctx: RecommendationContext,
    ) -> GateResult:
        self.calls.append((pattern, payload, ctx))
        return self.result


def test_unknown_rule_type_fails_closed_with_existing_message() -> None:
    journal_id = uuid4()
    policy = GuidelinePolicy()
    policy.set(
        journal_id,
        ({"rule_type": "not_agreed", "payload": {}, "is_mandatory": True},),
    )

    result = GuidelineGate(policy, GuidelineEvaluatorRegistry()).check(
        pattern(), context(journal_id)
    )

    assert not result.passed
    assert result.reason == "Mandatory guideline cannot yet be evaluated"


def test_registered_evaluator_that_passes_lets_pattern_through() -> None:
    journal_id = uuid4()
    payload = {"limit": 1}
    policy = GuidelinePolicy()
    policy.set(
        journal_id,
        ({"rule_type": "fake_pass", "payload": payload, "is_mandatory": True},),
    )
    evaluator = FakeEvaluator("fake_pass", GateResult(True))
    registry = GuidelineEvaluatorRegistry()
    registry.register(evaluator)
    view = pattern()
    ctx = context(journal_id)

    result = GuidelineGate(policy, registry).check(view, ctx)

    assert result.passed
    assert evaluator.calls == [(view, payload, ctx)]


def test_registered_evaluator_that_fails_blocks_pattern() -> None:
    journal_id = uuid4()
    policy = GuidelinePolicy()
    policy.set(
        journal_id,
        ({"rule_type": "fake_fail", "payload": {}, "is_mandatory": True},),
    )
    evaluator = FakeEvaluator("fake_fail", GateResult(False, "missing statement"))
    registry = GuidelineEvaluatorRegistry()
    registry.register(evaluator)

    result = GuidelineGate(policy, registry).check(pattern(), context(journal_id))

    assert not result.passed
    assert result.reason == "missing statement"


def test_non_mandatory_rules_are_ignored() -> None:
    journal_id = uuid4()
    policy = GuidelinePolicy()
    policy.set(
        journal_id,
        (
            {"rule_type": "unknown_type", "payload": {}, "is_mandatory": False},
            {"rule_type": "fake_fail", "payload": {}, "is_mandatory": False},
        ),
    )
    evaluator = FakeEvaluator("fake_fail", GateResult(False, "should not run"))
    registry = GuidelineEvaluatorRegistry()
    registry.register(evaluator)

    result = GuidelineGate(policy, registry).check(pattern(), context(journal_id))

    assert result.passed
    assert evaluator.calls == []


def test_journal_without_rules_passes_as_today() -> None:
    result = GuidelineGate(GuidelinePolicy()).check(pattern(), context(uuid4()))

    assert result.passed
