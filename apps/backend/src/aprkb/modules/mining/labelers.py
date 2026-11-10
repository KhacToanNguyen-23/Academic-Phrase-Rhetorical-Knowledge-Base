"""Batch labeler protocol and opt-in Groq adapter for masked frame metadata."""

import asyncio
import json
import time
from typing import Literal, Protocol
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from aprkb.policies.schemas import FrameLabelingPolicy, FrameLabelVocabularyPolicy

AI_LABEL_FIELDS = (
    "function_group",
    "intent",
    "move",
    "step",
    "claim_type",
    "register",
    "general_function",
    "section_scope",
)

_GUIDELINES = {
    "a": """Classify each supplied masked frame independently. Choose only listed vocabulary codes.
Prefer unclear when the frame does not support a confident choice. Keep intent under its listed
step, step under its move, and move under its function group. The section_scope is a suggested
allowed-section set member, not the observed source-section distribution. Never infer a value
from paper count or observed section counts alone. Evidence must be your own short rationale of
at most 15 words, not copied source material. Return only the requested JSON object.""",
    "b": """For every frame record, assign only codes present in the provided closed vocabulary.
Treat the frame as a pattern with masked slots. If evidence is weak, select unclear; use
none_of_these only when a different known category is indicated. Ensure the group/move/step/intent
path is consistent. Separate suggested section eligibility from the observed section counts.
Provide a brief original rationale of no more than 15 words. Do not add sentences or article
content. Return only schema-valid JSON.""",
}


class FrameLabelerError(RuntimeError):
    """Sanitized configuration/provider/response error without prompts or response content."""


class FrameLabelingRequestError(FrameLabelerError):
    """Transient request error that leaves candidates available for a later retry."""


class FrameLabelingQuotaError(FrameLabelingRequestError):
    """Provider quota exceeds the configured retry wait."""

    def __init__(self, retry_after_seconds: float) -> None:
        super().__init__("Groq frame-label quota exhausted")
        self.retry_after_seconds = retry_after_seconds


class FrameLabelPayload(BaseModel):
    """Closed input contract: no fields can carry source-sentence text."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    canonical_frame: str
    family: str
    epistemic_strength: str | None
    paper_count: int = Field(ge=0)
    observed_section_counts: dict[str, int]
    anchor_proposal: dict[str, str] | None = None


class ProposedFrameLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str | None
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: str | None = None

    @field_validator("evidence")
    @classmethod
    def evidence_is_short(cls, evidence: str | None) -> str | None:
        if evidence is not None and len(evidence.split()) > 15:
            raise ValueError("label evidence must be no more than 15 words")
        return evidence


class FrameLabelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    labels: dict[str, ProposedFrameLabel]


class FrameLabelBatchOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frames: list[FrameLabelOutput]


class FrameLabeler(Protocol):
    model: str
    prompt_version: str
    total_tokens: int

    async def label_batch(
        self,
        *,
        frames: list[FrameLabelPayload],
        prompt_variant: Literal["a", "b"],
    ) -> list[FrameLabelOutput]: ...


class NullFrameLabeler:
    model = "null"
    prompt_version = "v0"
    total_tokens = 0

    async def label_batch(
        self,
        *,
        frames: list[FrameLabelPayload],
        prompt_variant: Literal["a", "b"],
    ) -> list[FrameLabelOutput]:
        del frames, prompt_variant
        return []


def vocabulary_codes(vocabulary: FrameLabelVocabularyPolicy) -> dict[str, list[str]]:
    return {
        "function_group": [entry.code for entry in vocabulary.function_groups],
        "intent": [entry.code for entry in vocabulary.intents],
        "move": [entry.code for entry in vocabulary.moves],
        "step": [entry.code for entry in vocabulary.steps],
        "claim_type": [entry.code for entry in vocabulary.claim_types],
        "register": [entry.code for entry in vocabulary.registers],
        "general_function": [entry.code for entry in vocabulary.general_functions],
        "section_scope": [entry.code for entry in vocabulary.allowed_sections],
    }


def validate_frame_label_output(
    output: FrameLabelOutput,
    *,
    vocabulary: FrameLabelVocabularyPolicy,
) -> FrameLabelOutput:
    valid_codes = vocabulary_codes(vocabulary)
    if set(output.labels) - set(AI_LABEL_FIELDS):
        raise FrameLabelerError("Provider returned an unsupported label field")
    for field, label in output.labels.items():
        if label.value is not None and label.value not in valid_codes[field]:
            raise FrameLabelerError("Provider returned a code outside the frame-label vocabulary")
    return output


def frame_label_json_schema(vocabulary: FrameLabelVocabularyPolicy) -> dict[str, object]:
    def nullable(schema: dict[str, object]) -> dict[str, object]:
        return {"anyOf": [schema, {"type": "null"}]}

    code_fields = vocabulary_codes(vocabulary)
    labels = {
        field: {
            "type": "object",
            "additionalProperties": False,
            "required": ["value", "confidence", "evidence"],
            "properties": {
                "value": nullable({"type": "string", "enum": code_fields[field]}),
                "confidence": nullable({"type": "number", "minimum": 0, "maximum": 1}),
                "evidence": nullable({"type": "string"}),
            },
        }
        for field in AI_LABEL_FIELDS
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["frames"],
        "properties": {
            "frames": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["candidate_id", "labels"],
                    "properties": {
                        "candidate_id": {"type": "string", "format": "uuid"},
                        "labels": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": list(AI_LABEL_FIELDS),
                            "properties": labels,
                        },
                    },
                },
            }
        },
    }


class GroqFrameLabeler:
    def __init__(
        self,
        *,
        api_key: str,
        policy: FrameLabelingPolicy,
        vocabulary: FrameLabelVocabularyPolicy,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise FrameLabelerError("GROQ_API_KEY is required")
        self.model = policy.model
        self._policy = policy
        self._vocabulary = vocabulary
        self._api_key = api_key
        self._client = client
        self._schema = frame_label_json_schema(vocabulary)
        self._rate_lock = asyncio.Lock()
        self._next_request_at = 0.0
        self.total_tokens = 0
        self.prompt_version = policy.prompt_version_a

    async def label_batch(
        self,
        *,
        frames: list[FrameLabelPayload],
        prompt_variant: Literal["a", "b"],
    ) -> list[FrameLabelOutput]:
        if not frames:
            return []
        await self._wait_for_rate_limit()
        self.prompt_version = (
            self._policy.prompt_version_a
            if prompt_variant == "a"
            else self._policy.prompt_version_b
        )
        payload = {
            "model": self._policy.model,
            "temperature": self._policy.temperature,
            "max_tokens": self._policy.max_tokens,
            "reasoning_effort": "low",
            "include_reasoning": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "frame_label_batch",
                    "strict": True,
                    "schema": self._schema,
                },
            },
            "messages": [
                {"role": "system", "content": _GUIDELINES[prompt_variant]},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "vocabulary": self._vocabulary.model_dump(mode="json"),
                            "frames": [frame.model_dump(mode="json") for frame in frames],
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
                raise FrameLabelerError("Provider returned no label JSON")
            parsed = FrameLabelBatchOutput.model_validate_json(content)
        except FrameLabelerError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, ValidationError):
            raise FrameLabelerError("Groq frame-label request returned invalid data") from None
        finally:
            if owns_client:
                await client.aclose()

        expected_ids = {frame.candidate_id for frame in frames}
        result_ids = [item.candidate_id for item in parsed.frames]
        if len(result_ids) != len(set(result_ids)) or set(result_ids) != expected_ids:
            raise FrameLabelerError("Provider returned missing or unexpected frame records")
        return [
            validate_frame_label_output(item, vocabulary=self._vocabulary) for item in parsed.frames
        ]

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
                raise FrameLabelingRequestError("Groq frame-label request failed") from None
            if response.status_code == 429:
                try:
                    retry_after = max(0.0, float(response.headers.get("retry-after", "1")))
                except ValueError:
                    retry_after = 1.0
                if retry_after > self._policy.max_rate_limit_wait_seconds:
                    raise FrameLabelingQuotaError(retry_after)
                if attempt == 3:
                    raise FrameLabelingRequestError("Groq rate-limit retry limit reached")
                await asyncio.sleep(retry_after)
                continue
            if response.status_code == 401:
                raise FrameLabelingRequestError("Groq credentials were rejected")
            if response.is_error:
                raise FrameLabelingRequestError("Groq frame-label request failed")
            return response
        raise FrameLabelerError("Groq frame-label request failed")

    async def _wait_for_rate_limit(self) -> None:
        interval = 60.0 / self._policy.requests_per_minute
        async with self._rate_lock:
            now = time.monotonic()
            delay = max(0.0, self._next_request_at - now)
            if delay:
                await asyncio.sleep(delay)
                now = time.monotonic()
            self._next_request_at = max(now, self._next_request_at) + interval
