from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from aprkb.core.config import Settings, settings
from aprkb.modules.mining.epistemic_labelers import (
    EpistemicAssessment,
    EpistemicLabelerError,
    EpistemicPredicate,
    GroqEpistemicLabeler,
)
from aprkb.modules.mining.epistemic_lexicon_service import external_epistemic_processing_enabled
from aprkb.policies.loader import load_policy_bundle
from aprkb.policies.schemas import EpistemicScoringPolicy


def _batch_content(*, tier: str = "moderate", confidence: float = 0.97) -> str:
    return json.dumps(
        {
            "items": [
                {
                    "lemma": "postulate",
                    "pos": "verb",
                    "construction_family": "ccomp",
                    "tier": tier,
                    "confidence": confidence,
                    "rationale": "Conventional academic usage presents a tentative premise.",
                }
            ]
        }
    )


@pytest.mark.asyncio
async def test_groq_batch_uses_two_passes_metadata_only_and_retains_each_result() -> None:
    seen: list[dict[str, object]] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.append(payload)
        user_content = json.loads(payload["messages"][1]["content"])
        assert len(user_content["items"]) == 2
        assert "sentence" not in json.dumps(user_content).casefold()
        response_items = [
            {
                **item,
                "tier": "moderate",
                "confidence": 0.97,
                "rationale": "A reasoned academic claim.",
            }
            for item in user_content["items"]
        ]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps({"items": response_items})}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        labeler = GroqEpistemicLabeler(
            api_key="test-key",
            model="test-model",
            prompt_version="epistemic-dual-v1",
            client=client,
        )
        results = await labeler.assess_batch(
            [
                EpistemicPredicate(lemma="postulate", pos="verb", construction_family="ccomp"),
                EpistemicPredicate(lemma="posit", pos="verb", construction_family="ccomp"),
            ]
        )

    assert len(seen) == 2
    assert {payload["temperature"] for payload in seen} == {0.1, 0.3}
    result = results[("postulate", "verb", "ccomp")]
    assert result.run1.tier == result.run2.tier == "moderate"
    assert result.run1.confidence == result.run2.confidence == 0.97
    assert result.run1.rationale == "A reasoned academic claim."
    assert results[("posit", "verb", "ccomp")].run1.tier == "moderate"


@pytest.mark.asyncio
async def test_groq_batch_keeps_disagreeing_runs_for_review() -> None:
    async def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        tier = "high" if payload["temperature"] == 0.1 else "moderate"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": _batch_content(tier=tier)}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        labeler = GroqEpistemicLabeler(
            api_key="test-key",
            model="test-model",
            prompt_version="epistemic-dual-v1",
            client=client,
        )
        results = await labeler.assess_batch(
            [EpistemicPredicate(lemma="postulate", pos="verb", construction_family="ccomp")]
        )

    result = results[("postulate", "verb", "ccomp")]
    assert result.run1.tier == "high"
    assert result.run2.tier == "moderate"


@pytest.mark.asyncio
async def test_groq_batch_rejects_omitted_keys_and_long_rationales() -> None:
    async def omitted(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"items": []}'}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(omitted)) as client:
        labeler = GroqEpistemicLabeler(
            api_key="test-key",
            model="test-model",
            prompt_version="epistemic-dual-v1",
            client=client,
        )
        with pytest.raises(EpistemicLabelerError) as error:
            await labeler.assess_batch(
                [EpistemicPredicate(lemma="postulate", pos="verb", construction_family="ccomp")]
            )
    assert error.value.safe_code == "epistemic_invalid_response"

    with pytest.raises(ValidationError, match="15 words"):
        EpistemicAssessment(
            tier="high",
            confidence=0.99,
            rationale=(
                "This rationale intentionally contains more than fifteen words so the parser "
                "rejects this verbose response immediately."
            ),
        )


@pytest.mark.asyncio
async def test_groq_batch_sanitizes_provider_errors() -> None:
    async def malformed(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "secret body"}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(malformed)) as client:
        labeler = GroqEpistemicLabeler(
            api_key="test-key",
            model="test-model",
            prompt_version="epistemic-dual-v1",
            client=client,
        )
        with pytest.raises(EpistemicLabelerError) as error:
            await labeler.assess_batch(
                [EpistemicPredicate(lemma="postulate", pos="verb", construction_family="ccomp")]
            )
    assert "secret body" not in str(error.value)


def test_external_provider_requires_all_explicit_opt_in_gates(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_env", "test")
    monkeypatch.setattr(settings, "epistemic_labeler", "groq")
    monkeypatch.setattr(settings, "groq_allow_external_processing", True)
    monkeypatch.setattr(settings, "groq_api_key", SecretStr("test-only"))
    assert external_epistemic_processing_enabled()

    monkeypatch.setattr(settings, "app_env", "production")
    assert not external_epistemic_processing_enabled()
    monkeypatch.setattr(settings, "app_env", "test")
    monkeypatch.setattr(settings, "groq_allow_external_processing", False)
    assert not external_epistemic_processing_enabled()
    monkeypatch.setattr(settings, "groq_allow_external_processing", True)
    monkeypatch.setattr(settings, "groq_api_key", None)
    assert not external_epistemic_processing_enabled()


def test_dual_consensus_threshold_is_policy_configured_without_calibration() -> None:
    assert Settings(_env_file=None).epistemic_labeler == "null"
    assert load_policy_bundle().epistemic_scoring.oov_activation_confidence_threshold == 0.90
    assert (
        EpistemicScoringPolicy.model_validate(
            {
                **load_policy_bundle().epistemic_scoring.model_dump(),
                "oov_activation_confidence_threshold": 0.9,
            }
        ).oov_activation_confidence_threshold
        == 0.9
    )
