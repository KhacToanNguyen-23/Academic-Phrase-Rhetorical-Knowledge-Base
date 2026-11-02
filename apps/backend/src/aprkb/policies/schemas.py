"""Pydantic schemas for the versioned YAML policy files."""

from math import isclose, isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class VersionedPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")


class RankingWeightsPolicy(VersionedPolicy):
    weights: dict[str, float]
    evidence_alignment_formula: Literal[
        "1 - abs(max_supported - candidate_strength) / strength_span"
    ]
    keyword_formula: Literal["matched_keywords / query_keywords"]

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, weights: dict[str, float]) -> dict[str, float]:
        expected = {"discipline", "journal_genre", "evidence", "linguistic", "provenance"}
        if set(weights) != expected:
            raise ValueError("weights must define every active scorer exactly once")
        if any(not isfinite(weight) or weight < 0 or weight > 1 for weight in weights.values()):
            raise ValueError("weights must be finite values between 0 and 1")
        if not isclose(sum(weights.values()), 1.0, abs_tol=1e-6):
            raise ValueError("weights must sum to 1")
        if not any(weight > 0 for weight in weights.values()):
            raise ValueError("at least one scorer weight must be positive")
        return weights


class LicensePolicy(VersionedPolicy):
    internal_use_codes: list[str] = Field(min_length=1)

    @field_validator("internal_use_codes")
    @classmethod
    def validate_internal_use_codes(cls, codes: list[str]) -> list[str]:
        if len(codes) != len(set(codes)) or any(not code.strip() for code in codes):
            raise ValueError("internal_use_codes must contain unique non-empty license codes")
        return codes


class FallbackTiersPolicy(VersionedPolicy):
    tiers: list[str] = Field(min_length=1)

    @field_validator("tiers")
    @classmethod
    def validate_tiers(cls, tiers: list[str]) -> list[str]:
        allowed = {
            "journal_genre",
            "similar_journal_genre",
            "subfield_genre",
            "field_genre",
            "generic_genre",
        }
        if len(tiers) != len(set(tiers)) or any(tier not in allowed for tier in tiers):
            raise ValueError("tiers must be a unique ordered subset of known fallback tiers")
        return tiers


class SentenceFilterSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_words: int = Field(ge=0)
    max_words: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_word_bounds(self) -> "SentenceFilterSettings":
        if self.min_words > self.max_words:
            raise ValueError("min_words must not exceed max_words")
        return self


class MiningFilterPolicy(VersionedPolicy):
    sentence_filter: SentenceFilterSettings


class EvidenceMatrixPolicy(VersionedPolicy):
    default_max_strength: str
    matrix: dict[str, dict[str, str]]

    @model_validator(mode="after")
    def validate_matrix(self) -> "EvidenceMatrixPolicy":
        evidence_levels = {
            "none",
            "anecdotal",
            "single_study",
            "multiple_consistent",
            "systematic_synthesis",
        }
        strengths = {"low", "moderate", "high", "absolute"}
        if self.default_max_strength not in strengths:
            raise ValueError("default_max_strength is not a known epistemic strength")
        if not self.matrix:
            raise ValueError("matrix must not be empty")
        for claim, cells in self.matrix.items():
            if claim not in {"descriptive", "causal", "comparative", "generalization"} or not cells:
                raise ValueError(f"invalid or empty claim_type: {claim}")
            for evidence, strength in cells.items():
                if evidence not in evidence_levels or strength not in strengths:
                    raise ValueError(f"invalid evidence cell: {claim}/{evidence}/{strength}")
        return self


class RuleSetting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    severity: Literal["pass", "warn", "block"]


class ValidationRulesPolicy(VersionedPolicy):
    rules: dict[str, RuleSetting]
    style_warning_phrases: list[str] = Field(default_factory=list)

    @field_validator("rules")
    @classmethod
    def validate_rules(cls, rules: dict[str, RuleSetting]) -> dict[str, RuleSetting]:
        allowed = {f"V{i:02}" for i in range(1, 9)}
        if not rules or any(code not in allowed for code in rules):
            raise ValueError("rules must contain known V01–V08 entries")
        return rules

    @field_validator("style_warning_phrases")
    @classmethod
    def validate_style_warning_phrases(cls, phrases: list[str]) -> list[str]:
        if any(not phrase.strip() for phrase in phrases):
            raise ValueError("style warning phrases must not be blank")
        return phrases


class EpistemicMarkersPolicy(VersionedPolicy):
    markers: dict[str, list[str]]

    @field_validator("markers")
    @classmethod
    def validate_markers(cls, markers: dict[str, list[str]]) -> dict[str, list[str]]:
        strengths = {"low", "moderate", "high", "absolute"}
        if set(markers) != strengths or any(
            not values or any(not marker.strip() for marker in values)
            for values in markers.values()
        ):
            raise ValueError("markers must define non-empty lists for each epistemic strength")
        if any(len(values) != len(set(values)) for values in markers.values()):
            raise ValueError("epistemic marker lists must not contain duplicates")
        return markers
