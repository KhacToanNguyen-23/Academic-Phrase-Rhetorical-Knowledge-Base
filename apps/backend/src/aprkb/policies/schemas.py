"""Pydantic schemas for the versioned YAML policy files."""

import re
from math import isclose, isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class VersionedPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")


class LicenseEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    allows_mining: bool
    allows_display: bool


class LicensesPolicy(VersionedPolicy):
    licenses: list[LicenseEntry] = Field(min_length=1)
    source_aliases: dict[str, str]
    slr_license_paths: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> "LicensesPolicy":
        codes = [entry.code for entry in self.licenses]
        if len(codes) != len(set(codes)):
            raise ValueError("license codes must be unique")
        aliases = [" ".join(alias.split()).casefold() for alias in self.source_aliases]
        if any(not alias for alias in aliases) or len(aliases) != len(set(aliases)):
            raise ValueError("license aliases must be non-empty and unique after normalization")
        if any(code not in codes for code in self.source_aliases.values()):
            raise ValueError("license aliases must reference known codes")
        if any(
            not path or any(not part for part in path.split(".")) for path in self.slr_license_paths
        ):
            raise ValueError("license paths must contain non-empty keys")
        return self


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


class NoiseFilterSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    excluded_sections: list[str]
    min_table_pipes: int = Field(ge=1)
    max_math_symbol_ratio: float = Field(gt=0, le=1)
    max_numeric_token_ratio: float = Field(gt=0, le=1)


class MiningFilterPolicy(VersionedPolicy):
    sentence_filter: SentenceFilterSettings
    noise_filter: NoiseFilterSettings


class ReportingVerbForms(BaseModel):
    model_config = ConfigDict(extra="forbid")

    present: list[str] = Field(min_length=1)
    past: list[str] = Field(min_length=1)
    present_perfect: list[str] = Field(min_length=1)


class ReportingVerbsPolicy(VersionedPolicy):
    classes: dict[str, ReportingVerbForms] = Field(min_length=1)

    @property
    def all_forms(self) -> set[str]:
        return {
            form
            for forms in self.classes.values()
            for form in forms.present + forms.past + forms.present_perfect
        }

    @field_validator("classes")
    @classmethod
    def validate_verb_forms(
        cls, classes: dict[str, ReportingVerbForms]
    ) -> dict[str, ReportingVerbForms]:
        seen: set[str] = set()
        for class_name, forms in classes.items():
            if not class_name.isidentifier():
                raise ValueError("reporting verb class names must be identifiers")
            for form in forms.present + forms.past + forms.present_perfect:
                normalized = form.strip().casefold()
                if not normalized or normalized in seen:
                    raise ValueError("reporting verb forms must be non-empty and unique")
                seen.add(normalized)
        return classes


class SlotAbstractionPolicy(VersionedPolicy):
    max_subject_words: int = Field(ge=1, le=16)
    min_clause_words: int = Field(ge=1, le=20)
    own_determiners: list[str] = Field(min_length=1)
    prior_determiners: list[str] = Field(min_length=1)
    # Single words between subject and reporting verb that are kept literal in the frame.
    verb_modifiers: list[str] = Field(default_factory=list)

    @field_validator("verb_modifiers")
    @classmethod
    def validate_verb_modifiers(cls, values: list[str]) -> list[str]:
        if any(not re.fullmatch(r"[A-Za-z]+", value) for value in values):
            raise ValueError("verb modifiers must be single words")
        return values

    @model_validator(mode="after")
    def validate_determiners(self) -> "SlotAbstractionPolicy":
        own = {value.strip().casefold() for value in self.own_determiners}
        prior = {value.strip().casefold() for value in self.prior_determiners}
        if not own or not prior or own & prior:
            raise ValueError("own and prior determiners must be non-empty and disjoint")
        return self


class GoldSamplingPolicy(VersionedPolicy):
    filtered_fraction: float = Field(ge=0, le=1)
    test_fraction: float = Field(ge=0, le=1)


class GoldLabelingPolicy(VersionedPolicy):
    provider: Literal["null", "groq"]
    model: str = Field(min_length=1, max_length=128)
    temperature: float = Field(ge=0, le=2)
    max_tokens: int = Field(ge=1, le=32768)
    reasoning_effort: Literal["low", "medium", "high"]
    max_rate_limit_wait_seconds: float = Field(ge=0, le=600)
    sentences_per_request: int = Field(ge=1, le=20)
    max_concurrency: int = Field(ge=1, le=1)
    requests_per_minute: int = Field(ge=1, le=1000)
    prompt_version: str = Field(min_length=1, max_length=32)
    guideline_version: str = Field(min_length=1, max_length=32)


class AbbreviationsPolicy(VersionedPolicy):
    abbreviations: list[str] = Field(min_length=1)

    @field_validator("abbreviations")
    @classmethod
    def validate_abbreviations(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().casefold() for value in values]
        if any(not value or value.endswith(".") or " " in value for value in normalized):
            raise ValueError("abbreviations must be single tokens without the final period")
        if len(normalized) != len(set(normalized)):
            raise ValueError("abbreviations must not contain duplicates")
        return normalized


_SECTION_CODE = re.compile(r"^[A-Z][A-Z_]*$")


def _validate_pattern_map(patterns: dict[str, list[str]]) -> dict[str, list[str]]:
    for code, values in patterns.items():
        if not _SECTION_CODE.match(code) or not values:
            raise ValueError("section codes must be upper-case and have at least one pattern")
        for value in values:
            try:
                re.compile(value)
            except re.error as error:
                raise ValueError(f"invalid heading pattern for {code}: {error}") from error
    return patterns


class SectionHeadingsPolicy(VersionedPolicy):
    sections: dict[str, list[str]] = Field(min_length=1)
    non_rhetorical: dict[str, list[str]]
    reset: list[str]

    @field_validator("sections", "non_rhetorical")
    @classmethod
    def validate_patterns(cls, patterns: dict[str, list[str]]) -> dict[str, list[str]]:
        return _validate_pattern_map(patterns)

    @field_validator("reset")
    @classmethod
    def validate_reset(cls, patterns: list[str]) -> list[str]:
        _validate_pattern_map({"RESET": patterns} if patterns else {})
        return patterns

    @model_validator(mode="after")
    def validate_disjoint_codes(self) -> "SectionHeadingsPolicy":
        if set(self.sections) & set(self.non_rhetorical):
            raise ValueError("a section code cannot be both rhetorical and non-rhetorical")
        return self


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
    # Base verb -> irregular inflected forms that suffix rules cannot derive.
    irregular_forms: dict[str, list[str]] = Field(default_factory=dict)
    # Declared markers that are not verbs and must keep exact matching.
    non_inflecting: list[str] = Field(default_factory=list)

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

    @field_validator("irregular_forms")
    @classmethod
    def validate_irregular_forms(cls, forms: dict[str, list[str]]) -> dict[str, list[str]]:
        if any(
            not base.strip() or not values or any(not form.strip() for form in values)
            for base, values in forms.items()
        ):
            raise ValueError("irregular_forms must map each base verb to non-empty forms")
        return forms

    @model_validator(mode="after")
    def validate_non_inflecting(self) -> "EpistemicMarkersPolicy":
        declared = {marker.casefold() for values in self.markers.values() for marker in values}
        names = [name.casefold() for name in self.non_inflecting]
        if len(names) != len(set(names)) or any(not name.strip() for name in names):
            raise ValueError("non_inflecting must be unique, non-empty markers")
        if not set(names) <= declared:
            raise ValueError("non_inflecting entries must be declared markers")
        return self
