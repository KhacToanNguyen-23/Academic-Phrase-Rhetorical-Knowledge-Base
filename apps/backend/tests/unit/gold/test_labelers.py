"""Provider adapter tests use mocked HTTP only and never contact Groq."""

import json

import httpx
import pytest

from aprkb.modules.gold.labelers import (
    GoldLabelerError,
    GoldLabelingQuotaError,
    GoldLabelingRequestError,
    GroqGoldLabeler,
    NullGoldLabeler,
)
from aprkb.policies.schemas import GoldLabelingPolicy


def _policy() -> GoldLabelingPolicy:
    return GoldLabelingPolicy.model_validate(
        {
            "version": "0.1.0",
            "provider": "groq",
            "model": "test-model",
            "temperature": 0,
            "max_tokens": 500,
            "reasoning_effort": "low",
            "max_rate_limit_wait_seconds": 5,
            "sentences_per_request": 1,
            "max_concurrency": 1,
            "requests_per_minute": 1000,
            "prompt_version": "test-v0",
            "guideline_version": "v0",
        }
    )


@pytest.mark.asyncio
async def test_groq_adapter_validates_mocked_json_without_network_request() -> None:
    source = "Our results suggest that this method improves retrieval quality."
    response_body = {
        "keep": True,
        "section": "RESULTS",
        "epistemic_strength": "moderate",
        "tense": "present",
        "frame": "[X] suggest that [Y]",
        "slots": [{"name": "X", "char_start": 0, "char_end": 11}],
        "ownership": "own",
    }
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(response_body)}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        labeler = GroqGoldLabeler(api_key="mock-key", policy=_policy(), client=client)
        labels = await labeler.label(sentence=source, section="RESULTS")

    assert labels.keep is True
    assert labeler.model == "test-model"
    assert len(seen) == 1
    assert json.loads(seen[0].content)["messages"][1]["content"].find(source) >= 0


@pytest.mark.asyncio
async def test_groq_adapter_does_not_expose_provider_body_in_errors() -> None:
    source = "A private mock sentence must not appear in an error."

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=source)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        labeler = GroqGoldLabeler(api_key="mock-key", policy=_policy(), client=client)
        with pytest.raises(GoldLabelingRequestError) as error:
            await labeler.label(sentence=source, section="RESULTS")

    assert source not in str(error.value)


@pytest.mark.asyncio
async def test_null_gold_labeler_fails_without_forwarding_sentence() -> None:
    source = "Private fixture text."
    with pytest.raises(GoldLabelerError) as error:
        await NullGoldLabeler().label(sentence=source, section="RESULTS")
    assert source not in str(error.value)


@pytest.mark.asyncio
async def test_groq_adapter_retries_429_after_retry_after_header() -> None:
    response_body = {
        "keep": False,
        "noise_reason": "fragment",
        "section": "OTHER",
        "slots": [],
    }
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(response_body)}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        labeler = GroqGoldLabeler(api_key="mock-key", policy=_policy(), client=client)
        labels = await labeler.label(sentence="A short fixture.", section="OTHER")

    assert calls == 2
    assert labels.keep is False


@pytest.mark.asyncio
async def test_groq_request_uses_strict_schema_and_low_cost_reasoning() -> None:
    seen: list[dict[str, object]] = []
    body = {"keep": False, "noise_reason": "fragment", "section": "OTHER", "slots": []}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(body)}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        labeler = GroqGoldLabeler(api_key="mock-key", policy=_policy(), client=client)
        await labeler.label(sentence="A short fixture.", section="OTHER")

    payload = seen[0]
    assert payload["reasoning_effort"] == "low"
    assert payload["include_reasoning"] is False
    response_format = payload["response_format"]
    assert response_format["type"] == "json_schema"
    schema = response_format["json_schema"]
    assert schema["strict"] is True
    root = schema["schema"]
    assert root["additionalProperties"] is False
    assert set(root["required"]) == set(root["properties"])
    slot = root["properties"]["slots"]["items"]
    assert slot["additionalProperties"] is False
    assert set(slot["required"]) == set(slot["properties"])


@pytest.mark.asyncio
async def test_groq_adapter_raises_quota_error_when_wait_exceeds_policy_limit() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"retry-after": "3600"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        labeler = GroqGoldLabeler(api_key="mock-key", policy=_policy(), client=client)
        with pytest.raises(GoldLabelingQuotaError) as error:
            await labeler.label(sentence="A short fixture.", section="OTHER")

    assert calls == 1
    assert error.value.retry_after_seconds == 3600
