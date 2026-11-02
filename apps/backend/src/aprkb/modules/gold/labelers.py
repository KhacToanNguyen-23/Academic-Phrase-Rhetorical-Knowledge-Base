"""Provider-neutral draft labeler and an opt-in Groq HTTP adapter."""

import asyncio
import json
import time
from typing import Protocol

import httpx

from aprkb.modules.gold.labels import GoldLabels, NoiseReason, Ownership, Strength, Tense
from aprkb.policies.schemas import GoldLabelingPolicy

_GUIDELINE = """Classify one academic sentence. Return only JSON matching the requested schema.
Use adjacent sentences only as context for ownership. Do not label them or include them in slots.
keep means the sentence is clean running prose; it does not mean a slot can be extracted.
If it is a caption, table row, formula, reference, acknowledgement, fragment or metadata,
set keep=false and give noise_reason; otherwise noise_reason must be null.
Offsets are zero-based and end-exclusive into the target sentence; do not invent spans.
The frame must be the whole sentence with each slot span replaced by [X], [Y] or [Z]; every
character outside the slots stays exactly as written. Never shorten, reword or drop text.
Slots are non-overlapping spans named X, Y, Z in order of appearance. Put sentence-specific
content (topic nouns, domain terms, content clauses) in slots and keep the reporting verb,
hedges, negation, modals and comparison words in the frame.
Set epistemic_strength from the marker words in the guideline only; otherwise use none.
For keep=false set frame to null and slots to an empty list.
Labels: keep, noise_reason, section, epistemic_strength, tense, frame, slots, ownership, notes.
"""


class GoldLabelerError(RuntimeError):
    """Sanitized provider/configuration failure without source or response content."""


class GoldLabelingRequestError(GoldLabelerError):
    """Request-level provider failure; the job should fail and keep items retryable."""


class GoldLabelingQuotaError(GoldLabelingRequestError):
    """Provider quota is exhausted for longer than the policy is willing to wait."""

    def __init__(self, retry_after_seconds: float) -> None:
        super().__init__("Groq quota exhausted")
        self.retry_after_seconds = retry_after_seconds


def _nullable(schema: dict[str, object]) -> dict[str, object]:
    return {"anyOf": [schema, {"type": "null"}]}


# Groq strict mode: every property is required, objects forbid extra keys, and optional
# values are unions with null. Pydantic (GoldLabels) still validates the result.
_LABEL_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "keep",
        "noise_reason",
        "section",
        "epistemic_strength",
        "tense",
        "frame",
        "slots",
        "ownership",
        "notes",
    ],
    "properties": {
        "keep": {"type": "boolean"},
        "noise_reason": _nullable({"type": "string", "enum": [v.value for v in NoiseReason]}),
        "section": {"type": "string"},
        "epistemic_strength": {"type": "string", "enum": [v.value for v in Strength]},
        "tense": {"type": "string", "enum": [v.value for v in Tense]},
        "frame": _nullable({"type": "string"}),
        "slots": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "char_start", "char_end"],
                "properties": {
                    "name": {"type": "string"},
                    "char_start": {"type": "integer"},
                    "char_end": {"type": "integer"},
                },
            },
        },
        "ownership": {"type": "string", "enum": [v.value for v in Ownership]},
        "notes": _nullable({"type": "string"}),
    },
}


class GoldLabeler(Protocol):
    model: str
    prompt_version: str
    total_tokens: int

    async def label(
        self,
        *,
        sentence: str,
        section: str,
        previous_sentence: str | None = None,
        next_sentence: str | None = None,
    ) -> GoldLabels: ...


class NullGoldLabeler:
    model = "null"
    prompt_version = "v0"
    total_tokens = 0

    async def label(
        self,
        *,
        sentence: str,
        section: str,
        previous_sentence: str | None = None,
        next_sentence: str | None = None,
    ) -> GoldLabels:
        del sentence, section, previous_sentence, next_sentence
        raise GoldLabelerError("Gold labeler is disabled")


class GroqGoldLabeler:
    def __init__(
        self,
        *,
        api_key: str,
        policy: GoldLabelingPolicy,
        guideline: str = "",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise GoldLabelerError("GROQ_API_KEY is required")
        self.model = policy.model
        self.prompt_version = policy.prompt_version
        self._api_key = api_key
        self._policy = policy
        self._guideline = guideline
        self._client = client
        self.total_tokens = 0  # provider-reported usage; counts only, never content
        self._rate_lock = asyncio.Lock()
        self._next_request_at = 0.0

    async def label(
        self,
        *,
        sentence: str,
        section: str,
        previous_sentence: str | None = None,
        next_sentence: str | None = None,
    ) -> GoldLabels:
        await self._wait_for_rate_limit()
        payload = {
            "model": self._policy.model,
            "temperature": self._policy.temperature,
            "max_tokens": self._policy.max_tokens,
            "reasoning_effort": self._policy.reasoning_effort,
            "include_reasoning": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "gold_labels",
                    "strict": True,
                    "schema": _LABEL_JSON_SCHEMA,
                },
            },
            "messages": [
                {"role": "system", "content": f"{self._guideline}\n\n{_GUIDELINE}"},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "section": section,
                            "previous_sentence": previous_sentence,
                            "sentence": sentence,
                            "next_sentence": next_sentence,
                            "slot_offsets_are_relative_to": "sentence",
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=45)
        try:
            response = await self._request(client, payload)
            body = response.json()
            usage = body.get("usage")
            if isinstance(usage, dict) and isinstance(usage.get("total_tokens"), int):
                self.total_tokens += usage["total_tokens"]
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise GoldLabelerError("Provider returned no label JSON")
            decoded = json.loads(content)
            if not isinstance(decoded, dict):
                raise GoldLabelerError("Provider returned invalid label JSON")
            return GoldLabels.model_validate(decoded)
        except GoldLabelerError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
            # Do not include provider payloads, response bodies, or source text.
            raise GoldLabelerError("Groq labeling request failed") from None
        finally:
            if owns_client:
                await client.aclose()

    async def _request(
        self, client: httpx.AsyncClient, payload: dict[str, object]
    ) -> httpx.Response:
        for attempt in range(4):
            try:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
            except httpx.HTTPError:
                raise GoldLabelingRequestError("Groq labeling request failed") from None
            if response.status_code == 429:
                try:
                    retry_after = max(0.0, float(response.headers.get("retry-after", "1")))
                except ValueError:
                    retry_after = 1.0
                if retry_after > self._policy.max_rate_limit_wait_seconds:
                    raise GoldLabelingQuotaError(retry_after)
                if attempt == 3:
                    raise GoldLabelingRequestError("Groq rate limit retry limit reached")
                await asyncio.sleep(retry_after)
                continue
            if response.status_code == 401:
                raise GoldLabelingRequestError("Groq credentials were rejected")
            if response.is_error:
                raise GoldLabelingRequestError("Groq labeling request failed")
            return response
        raise GoldLabelerError("Groq labeling request failed")

    async def _wait_for_rate_limit(self) -> None:
        interval = 60.0 / self._policy.requests_per_minute
        async with self._rate_lock:
            now = time.monotonic()
            delay = max(0.0, self._next_request_at - now)
            if delay:
                await asyncio.sleep(delay)
                now = time.monotonic()
            self._next_request_at = max(now, self._next_request_at) + interval
