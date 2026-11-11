"""Dual-pass, closed-vocabulary AI assessment for epistemic OOV predicates."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

StrengthTier = Literal["low", "moderate", "high", "absolute"]
EpistemicKey = tuple[str, str, str]


@dataclass(frozen=True)
class EpistemicPredicate:
    lemma: str
    pos: str
    construction_family: str

    @property
    def key(self) -> EpistemicKey:
        return (
            self.lemma.strip().casefold(),
            self.pos.strip().casefold(),
            self.construction_family.strip().casefold(),
        )


class EpistemicAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: StrengthTier
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=240)

    @field_validator("rationale")
    @classmethod
    def rationale_is_concise(cls, value: str) -> str:
        if len(value.split()) > 15:
            raise ValueError("rationale must contain at most 15 words")
        return value


class EpistemicBatchItem(EpistemicAssessment):
    lemma: str
    pos: str
    construction_family: str

    @property
    def key(self) -> EpistemicKey:
        return (
            self.lemma.strip().casefold(),
            self.pos.strip().casefold(),
            self.construction_family.strip().casefold(),
        )


class EpistemicBatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[EpistemicBatchItem]


@dataclass(frozen=True)
class DualEpistemicAssessment:
    run1: EpistemicAssessment
    run2: EpistemicAssessment


class EpistemicLabelerError(RuntimeError):
    """Sanitized provider or response error; never includes request/response contents."""

    def __init__(self, message: str, *, safe_code: str = "epistemic_provider_error") -> None:
        super().__init__(message)
        self.safe_code = safe_code


class EpistemicLabeler(Protocol):
    model: str
    prompt_version: str
    provider: str

    async def assess_batch(
        self, predicates: list[EpistemicPredicate]
    ) -> dict[EpistemicKey, DualEpistemicAssessment]:
        """Assess a batch using two separate, metadata-only evaluation passes."""


class NullEpistemicLabeler:
    provider = "null"
    model = "null"
    prompt_version = "v0"

    async def assess_batch(
        self, predicates: list[EpistemicPredicate]
    ) -> dict[EpistemicKey, DualEpistemicAssessment]:
        del predicates
        raise EpistemicLabelerError(
            "Epistemic enrichment provider is disabled", safe_code="epistemic_provider_disabled"
        )


class GroqEpistemicLabeler:
    provider = "groq"
    MAX_BATCH_ITEMS = 20

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        prompt_version: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise EpistemicLabelerError("GROQ_API_KEY is required")
        self.model = model
        self.prompt_version = prompt_version
        self._api_key = api_key
        self._client = client

    async def assess_batch(
        self, predicates: list[EpistemicPredicate]
    ) -> dict[EpistemicKey, DualEpistemicAssessment]:
        if not predicates:
            return {}
        if len(predicates) > self.MAX_BATCH_ITEMS:
            raise ValueError(f"epistemic assessment batch exceeds {self.MAX_BATCH_ITEMS} items")
        keys = [predicate.key for predicate in predicates]
        if len(keys) != len(set(keys)):
            raise ValueError("epistemic assessment batch contains duplicate keys")

        run1, run2 = await asyncio.gather(
            self._assess_once(predicates, run=1), self._assess_once(predicates, run=2)
        )
        return {key: DualEpistemicAssessment(run1=run1[key], run2=run2[key]) for key in keys}

    async def _assess_once(
        self, predicates: list[EpistemicPredicate], *, run: Literal[1, 2]
    ) -> dict[EpistemicKey, EpistemicAssessment]:
        item_schema = {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "lemma",
                "pos",
                "construction_family",
                "tier",
                "confidence",
                "rationale",
            ],
            "properties": {
                "lemma": {"type": "string"},
                "pos": {"type": "string"},
                "construction_family": {"type": "string"},
                "tier": {"type": "string", "enum": ["absolute", "high", "moderate", "low"]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "rationale": {"type": "string"},
            },
        }
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["items"],
            "properties": {"items": {"type": "array", "items": item_schema}},
        }
        system_prompt = (
            "You are a computational linguist classifying conventional epistemic force in "
            "academic reporting predicates. Independently evaluate each supplied lemma, POS, "
            "and construction family; do not infer or invent a source sentence. Assign absolute "
            "to deductive proof, high to direct empirical observation or strong demonstration, "
            "moderate to evidence-based inference or a reasoned claim, and low to speculation, "
            "hypothesis, assumption, or weakly supported assertion. Return one item for every "
            "input key. Keep each rationale at most 15 words. Confidence is your estimate, not a "
            "calibrated probability. The application maps tiers to configured scores. "
            "Return JSON only."
            if run == 1
            else "Reconsider each academic reporting predicate independently from its lemma, POS, "
            "and construction family. Use absolute only for deductive proof; high for direct "
            "empirical observation or strong demonstration; moderate for evidence-based inference "
            "or reasoned claims; low for speculative premises, hypotheses, and assumptions. "
            "Do not infer a source sentence. Return exactly one result per input key with a "
            "rationale at most 15 words. Confidence is an estimate, not a calibrated probability. "
            "The application maps tiers to configured scores. Return JSON only."
        )
        payload = {
            "model": self.model,
            "temperature": 0.1 if run == 1 else 0.3,
            "seed": 27183 if run == 1 else 31415,
            "max_tokens": min(4096, max(512, len(predicates) * 160)),
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "epistemic_batch", "strict": True, "schema": schema},
            },
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "items": [
                                {
                                    "lemma": predicate.lemma,
                                    "pos": predicate.pos,
                                    "construction_family": predicate.construction_family,
                                }
                                for predicate in predicates
                            ]
                        },
                        ensure_ascii=True,
                    ),
                },
            ],
        }
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=45)
        try:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise EpistemicLabelerError(
                    "Provider response did not contain JSON text",
                    safe_code="epistemic_invalid_response",
                )
            parsed = EpistemicBatchResponse.model_validate_json(content)
            assessments: dict[EpistemicKey, EpistemicAssessment] = {}
            for item in parsed.items:
                if item.key in assessments:
                    raise EpistemicLabelerError(
                        "Provider response repeated an assessment key",
                        safe_code="epistemic_invalid_response",
                    )
                assessments[item.key] = EpistemicAssessment(
                    tier=item.tier, confidence=item.confidence, rationale=item.rationale
                )
            expected = {predicate.key for predicate in predicates}
            if assessments.keys() != expected:
                raise EpistemicLabelerError(
                    "Provider response omitted or changed an assessment key",
                    safe_code="epistemic_invalid_response",
                )
            return assessments
        except EpistemicLabelerError:
            raise
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as error:
            raise EpistemicLabelerError(
                f"Epistemic provider response invalid ({type(error).__name__})",
                safe_code="epistemic_invalid_response",
            ) from None
        finally:
            if owns_client:
                await client.aclose()
