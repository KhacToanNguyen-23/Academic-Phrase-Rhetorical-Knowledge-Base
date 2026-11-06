"""Pydantic schemas for the versioned YAML policy files."""

import re
from math import isclose, isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class VersionedPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")


class VocabularySourceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sheet: str = Field(min_length=1)
    required_headers: list[str] = Field(min_length=1)
    columns: dict[str, str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_headers(self) -> "VocabularySourceProfile":
        if any(not header.strip() for header in self.required_headers):
            raise ValueError("vocabulary required_headers must not contain blank values")
        if len(self.required_headers) != len(set(self.required_headers)):
            raise ValueError("vocabulary required_headers must not contain duplicates")
        if any(not field.strip() or not header.strip() for field, header in self.columns.items()):
            raise ValueError("vocabulary columns must contain non-empty field and header names")
        return self


class VocabularyLabels(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pos: dict[str, str] = Field(min_length=1)
    status: dict[str, str] = Field(min_length=1)
    category: dict[str, str] = Field(min_length=1)
    domains: dict[str, str] = Field(min_length=1)


class VocabularyImportPolicy(VersionedPolicy):
    max_upload_bytes: int = Field(gt=0)
    sources: dict[str, VocabularySourceProfile] = Field(min_length=1)
    domain_codes: list[str] = Field(min_length=1)
    domain_groups: list[str] = Field(min_length=1)
    labels: VocabularyLabels
    family_domain_aliases: dict[str, str]

    @model_validator(mode="after")
    def validate_references(self) -> "VocabularyImportPolicy":
        if len(self.domain_codes) != len(set(self.domain_codes)) or any(
            not code.strip() for code in self.domain_codes
        ):
            raise ValueError("vocabulary domain_codes must be unique and non-empty")
        if self.domain_groups != ["freq", "ratio"]:
            raise ValueError("vocabulary domain_groups must be [freq, ratio]")
        expected_sources = {"all_words", "acad_core", "families"}
        if set(self.sources) != expected_sources:
            raise ValueError("vocabulary sources must define all_words, acad_core, and families")
        invalid_aliases = sorted(
            alias
            for alias, code in self.family_domain_aliases.items()
            if code not in self.domain_codes
        )
        if invalid_aliases:
            raise ValueError(
                "family_domain_aliases reference unknown domain codes: "
                + ", ".join(invalid_aliases)
            )
        if set(self.labels.domains) != set(self.domain_codes):
            raise ValueError("vocabulary domain labels must define every domain code exactly once")
        return self


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
    provenance_scores: dict[str, float]
    evidence_alignment_formula: Literal[
        "1 - abs(max_supported - candidate_strength) / strength_span"
    ]
    keyword_formula: Literal["matched_keywords / query_keywords"]

    @field_validator("provenance_scores")
    @classmethod
    def validate_provenance_scores(cls, scores: dict[str, float]) -> dict[str, float]:
        if set(scores) != {"authored", "mined"} or any(
            not isfinite(score) or score < 0 or score > 1 for score in scores.values()
        ):
            raise ValueError("provenance_scores must define authored and mined values in [0, 1]")
        return scores

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


class SyntaxFilterSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    require_finite_verb: bool = True
    allow_imperatives: bool = False


class NoiseFilterSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    excluded_sections: list[str]
    min_table_pipes: int = Field(ge=1)
    max_math_symbol_ratio: float = Field(gt=0, le=1)
    max_numeric_token_ratio: float = Field(gt=0, le=1)


class MiningFilterPolicy(VersionedPolicy):
    sentence_filter: SentenceFilterSettings
    syntax_filter: SyntaxFilterSettings = Field(default_factory=SyntaxFilterSettings)
    noise_filter: NoiseFilterSettings


class ReportingVerbForms(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lemmas: list[str] = Field(min_length=1)
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

    @property
    def all_lemmas(self) -> set[str]:
        return {
            lemma.strip().casefold() for forms in self.classes.values() for lemma in forms.lemmas
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
            lemmas = {lemma.strip().casefold() for lemma in forms.lemmas}
            if not lemmas or any(not lemma for lemma in lemmas):
                raise ValueError("reporting verb lemmas must be non-empty")
            for form in forms.present + forms.past + forms.present_perfect:
                normalized = form.strip().casefold()
                if not normalized or normalized in seen:
                    raise ValueError("reporting verb forms must be non-empty and unique")
                seen.add(normalized)
        return classes


class ConstructionChild(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: list[list[str]] = Field(min_length=1)
    path_lemmas: list[list[str]] = Field(default_factory=list)
    mode: Literal["literal", "slot", "literal_optional", "head_literal_modifiers_slot"]
    slot: str | None = None
    lemmas: list[str] = Field(default_factory=list)
    include_descendant_deps: list[str] = Field(default_factory=list)
    modifier_deps: list[str] = Field(default_factory=list)
    optional: bool = False

    @model_validator(mode="after")
    def validate_shape(self) -> "ConstructionChild":
        if any(not hop or any(not dep.strip() for dep in hop) for hop in self.path):
            raise ValueError("construction paths must contain non-empty dependency labels")
        if self.path_lemmas and len(self.path_lemmas) != len(self.path):
            raise ValueError(
                "construction path lemma constraints must align with its dependency path"
            )
        if self.mode in {"slot", "head_literal_modifiers_slot"} and not self.slot:
            raise ValueError("slot construction children require a slot name")
        if self.mode == "literal_optional" and not self.optional:
            raise ValueError("literal_optional children must be marked optional")
        return self


class ConstructionAdjuncts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prepositions: list[str] = Field(min_length=1)
    purpose_deps: list[str] = Field(min_length=1)
    max_count: Literal[2] = 2
    literal_in_objects: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_adjunct_lists(self) -> "ConstructionAdjuncts":
        allowed = {
            "prepositions": {"in", "for", "with", "as", "on", "by"},
            "purpose_deps": {"advcl", "xcomp"},
            "literal_in_objects": {"paper", "study", "work", "article", "research"},
        }
        for field, permitted in allowed.items():
            values = getattr(self, field)
            normalized = [value.strip().casefold() for value in values]
            if any(not value for value in normalized) or len(normalized) != len(set(normalized)):
                raise ValueError(f"construction adjunct {field} must be non-empty and unique")
            if set(normalized) - permitted:
                raise ValueError(f"construction adjunct {field} contains an unknown entry")
        return self


class ConstructionRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    function: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    anchor_lemmas: list[str] = Field(min_length=1)
    children: list[ConstructionChild] = Field(min_length=1)
    allowed_literal: list[str] = Field(default_factory=list)
    frame_templates: list[str] = Field(default_factory=list)
    adjuncts: ConstructionAdjuncts | None = None
    subject_phrases: list[str] = Field(default_factory=list)

    @field_validator("subject_phrases")
    @classmethod
    def validate_subject_phrases(cls, phrases: list[str]) -> list[str]:
        allowed = {"we", "this paper", "this study", "this article"}
        normalized = [phrase.strip().casefold() for phrase in phrases]
        if len(normalized) != len(set(normalized)):
            raise ValueError("construction subject phrases must be unique")
        if any(not phrase for phrase in normalized) or set(normalized) - allowed:
            raise ValueError("construction subject phrase is not approved")
        return normalized

    @field_validator("frame_templates")
    @classmethod
    def validate_frame_templates(cls, templates: list[str]) -> list[str]:
        for template in templates:
            compile_construction_template(template)
        return templates

    @model_validator(mode="after")
    def validate_frame_validation(self) -> "ConstructionRule":
        if not self.frame_templates and self.adjuncts is None:
            raise ValueError("construction rules require frame_templates or adjuncts")
        if self.subject_phrases and self.function != "author_action":
            raise ValueError("subject phrases are only valid for author_action constructions")
        return self


class ConstructionsPolicy(VersionedPolicy):
    constructions: list[ConstructionRule] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_ids(self) -> "ConstructionsPolicy":
        identifiers = [rule.id for rule in self.constructions]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("construction ids must be unique")
        if tuple(map(int, self.version.split("."))) >= (0, 3, 0) and any(
            rule.id == "author_action" and rule.adjuncts is not None and not rule.subject_phrases
            for rule in self.constructions
        ):
            raise ValueError("version 0.3.0+ author_action requires its subject phrase allowlist")
        return self


class ConstructionVerbGroupPolicy(VersionedPolicy):
    """Closed candidate lists for literal modifiers and auxiliaries on author-action frames."""

    modifier_positions: dict[
        str,
        list[Literal["before_subject", "between_subject_and_anchor", "after_anchor_before_object"]],
    ] = Field(min_length=1)
    auxiliary_lemmas: list[str] = Field(min_length=1)

    @field_validator("modifier_positions")
    @classmethod
    def validate_modifier_positions(cls, values: dict[str, list[str]]) -> dict[str, list[str]]:
        normalized: dict[str, list[str]] = {}
        for lemma, positions in values.items():
            key = lemma.strip().casefold()
            if (
                not key
                or " " in key
                or key in normalized
                or not positions
                or len(positions) != len(set(positions))
            ):
                raise ValueError(
                    "modifier positions require unique single-word entries and positions"
                )
            normalized[key] = positions
        return normalized

    @field_validator("auxiliary_lemmas")
    @classmethod
    def validate_auxiliary_lemmas(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().casefold() for value in values]
        if any(not value or " " in value for value in normalized) or len(normalized) != len(
            set(normalized)
        ):
            raise ValueError("auxiliary_lemmas must contain unique single-word entries")
        return normalized


class PhraseStatsPolicy(VersionedPolicy):
    smoothing_alpha: float = Field(gt=0, le=100)
    min_focal_docs: int = Field(ge=1)
    warn_below_focal_articles: int = Field(ge=1)
    top_n: int = Field(ge=1, le=500)


def is_safe_construction_frame(
    frame: str,
    policy: ConstructionsPolicy,
    *,
    construction_id: str | None = None,
    verb_group_policy: ConstructionVerbGroupPolicy | None = None,
) -> bool:
    """Accept only a complete masked-frame grammar declared by the construction registry."""
    normalized = re.sub(r"\s+", " ", frame).strip()
    return any(
        _is_safe_adjunct_frame(normalized, rule, verb_group_policy)
        if rule.adjuncts is not None
        else any(
            re.fullmatch(compile_construction_template(template), normalized, flags=re.IGNORECASE)
            is not None
            for template in rule.frame_templates
        )
        for rule in policy.constructions
        if construction_id is None or rule.id == construction_id
    )


def _is_safe_adjunct_frame(
    frame: str,
    rule: ConstructionRule,
    verb_group_policy: ConstructionVerbGroupPolicy | None = None,
) -> bool:
    if rule.adjuncts is None:
        return False
    adjuncts = rule.adjuncts
    forms: set[str] = set()
    for lemma in rule.anchor_lemmas:
        base = lemma.casefold()
        forms.add(base)
        if base.endswith("y") and len(base) > 1 and base[-2] not in "aeiou":
            forms.update((base[:-1] + "ies", base[:-1] + "ied"))
        else:
            forms.add(base + ("es" if base.endswith(("s", "x", "z", "ch", "sh", "o")) else "s"))
            forms.add(base + ("d" if base.endswith("e") else "ed"))
    verb = (
        "(?:" + "|".join(re.escape(value) for value in sorted(forms, key=len, reverse=True)) + ")"
    )
    preps = "(?:" + "|".join(re.escape(value) for value in adjuncts.prepositions) + "|to)"
    literal_phrases = "(?:paper|study|work|article|research)"
    modifiers = verb_group_policy.modifier_positions if verb_group_policy is not None else {}
    before_subject = [
        lemma for lemma, positions in modifiers.items() if "before_subject" in positions
    ]
    between_subject_and_anchor = [
        lemma for lemma, positions in modifiers.items() if "between_subject_and_anchor" in positions
    ]
    after_anchor_before_object = [
        lemma for lemma, positions in modifiers.items() if "after_anchor_before_object" in positions
    ]

    def alternatives(values: list[str]) -> str:
        return (
            "(?:"
            + "|".join(re.escape(value) for value in sorted(values, key=len, reverse=True))
            + ")"
        )

    prefix_values = [rf"in this {literal_phrases},"]
    if before_subject:
        prefix_values.append(rf"{alternatives(before_subject)},?")
    prefix = rf"(?:(?:{'|'.join(prefix_values)}) )?"
    literal_phrase = rf"(?: in this {literal_phrases})?"
    subject_phrases = rule.subject_phrases or ["we"]
    subject = (
        "(?:"
        + "|".join(re.escape(value) for value in sorted(subject_phrases, key=len, reverse=True))
        + ")"
    )
    subject_modifier = (
        rf"(?: {alternatives(between_subject_and_anchor)})?" if between_subject_and_anchor else ""
    )
    auxiliary = (
        rf"(?: {alternatives(verb_group_policy.auxiliary_lemmas)})?"
        if verb_group_policy is not None and verb_group_policy.auxiliary_lemmas
        else ""
    )
    anchor_modifier = (
        rf"(?: {alternatives(after_anchor_before_object)})?" if after_anchor_before_object else ""
    )
    after_x = rf"{subject}{subject_modifier}{auxiliary} {verb}{anchor_modifier} \[X\]"
    adjunct_y = rf"(?: {preps} \[Y\]"
    adjunct_z = rf"(?: {preps} \[Z\])?"
    body = after_x + literal_phrase + adjunct_y + literal_phrase + adjunct_z + literal_phrase + ")?"
    suffix = r"[.!?]*"
    return re.fullmatch(prefix + body + suffix, frame, flags=re.IGNORECASE) is not None


def compile_construction_template(template: str) -> str:
    """Compile literal text, positional slots, and simple `{a|b}` alternatives safely."""
    parts: list[str] = []
    position = 0
    marker = re.compile(r"\[([XYZ])\]|\{([^{}]*)\}")
    for match in marker.finditer(template):
        literal = template[position : match.start()]
        if any(char in literal for char in "[]{}"):
            raise ValueError("construction templates may only use positional slot markers")
        parts.append(re.escape(literal))
        slot, alternatives = match.groups()
        if slot is not None:
            parts.append(re.escape(f"[{slot}]"))
        else:
            choices = alternatives.split("|")
            if any(not re.fullmatch(r"[A-Za-z]+", choice) for choice in choices):
                raise ValueError("construction template alternatives must be single words")
            parts.append("(?:" + "|".join(re.escape(choice) for choice in choices) + ")")
        position = match.end()
    tail = template[position:]
    if any(char in tail for char in "[]{}"):
        raise ValueError("construction templates may only use positional slot markers")
    parts.append(re.escape(tail))
    return "".join(parts)


class SlotAbstractionPolicy(VersionedPolicy):
    max_subject_words: int = Field(ge=1, le=16)
    min_clause_words: int = Field(ge=1, le=20)
    own_determiners: list[str] = Field(min_length=1)
    prior_determiners: list[str] = Field(min_length=1)
    own_head_nouns: list[str] = Field(min_length=1)
    contextual_own_pairs: list[str] = Field(min_length=1)
    prior_head_pairs: list[str] = Field(min_length=1)
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
        lists = (self.own_head_nouns, self.contextual_own_pairs, self.prior_head_pairs)
        if any(not value.strip() for values in lists for value in values):
            raise ValueError("ownership tier entries must be non-empty")
        return self


class HybridFamilyPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^hybrid_[a-z][a-z0-9_]{1,55}$")
    # A disabled family is neither mined nor accepted by the review safety check.
    enabled: bool = True
    min_content_tokens: int = Field(default=3, ge=1, le=20)
    patterns: list[str] = Field(default_factory=list)
    allowed_deps: list[str] = Field(default_factory=lambda: ["ROOT", "nsubj", "nsubjpass"])
    allowed_pos: list[str] = Field(default_factory=lambda: ["NOUN", "VERB", "AUX", "ADJ"])
    slot_strategy: Literal["dependency_subtrees"] = "dependency_subtrees"

    @field_validator("patterns")
    @classmethod
    def compile_patterns(cls, patterns: list[str]) -> list[str]:
        for pattern in patterns:
            re.compile(pattern)
        return patterns

    @model_validator(mode="after")
    def validate_labels(self) -> "HybridFamilyPolicy":
        known_deps = {
            "ROOT",
            "acl",
            "acomp",
            "advcl",
            "advmod",
            "agent",
            "amod",
            "appos",
            "attr",
            "aux",
            "auxpass",
            "case",
            "cc",
            "ccomp",
            "compound",
            "conj",
            "csubj",
            "csubjpass",
            "dative",
            "dep",
            "det",
            "dobj",
            "expl",
            "intj",
            "mark",
            "meta",
            "neg",
            "nmod",
            "npadvmod",
            "nsubj",
            "nsubjpass",
            "nummod",
            "obj",
            "obl",
            "oprd",
            "parataxis",
            "pcomp",
            "pobj",
            "poss",
            "preconj",
            "prep",
            "prt",
            "punct",
            "quantmod",
            "relcl",
            "xcomp",
        }
        known_pos = {
            "ADJ",
            "ADP",
            "ADV",
            "AUX",
            "CCONJ",
            "DET",
            "INTJ",
            "NOUN",
            "NUM",
            "PART",
            "PRON",
            "PROPN",
            "PUNCT",
            "SCONJ",
            "SPACE",
            "SYM",
            "VERB",
            "X",
        }
        if (
            len(self.allowed_deps) != len(set(self.allowed_deps))
            or any(not value.strip() for value in self.allowed_deps)
            or set(self.allowed_deps) - known_deps
        ):
            raise ValueError("hybrid dependency labels must be known, unique, and non-empty")
        if (
            len(self.allowed_pos) != len(set(self.allowed_pos))
            or any(not value.strip() for value in self.allowed_pos)
            or set(self.allowed_pos) - known_pos
        ):
            raise ValueError("hybrid POS labels must be known, unique, and non-empty")
        return self


# A placeholder glued to punctuation or a word, or punctuation set off by a space, marks a span
# cut inside a token or text damaged by extraction.
HYBRID_SLOT_BOUNDARY = re.compile(r"[,;:.!?/-]\[[XYZ]\]|\[[XYZ]\][A-Za-z0-9/-]|\s[,;:!?]|\s\.$")


class HybridConstructionsPolicy(VersionedPolicy):
    meta_np: dict[str, list[str]]
    boundary: dict[str, bool]
    # Literal words allowed around the slots; a longer frame is a sentence, not a reusable phrase.
    max_literal_words: int = Field(default=12, ge=4, le=40)
    # A frame ending in one of these has lost the object of its preposition.
    dangling_tail_words: list[str] = Field(default_factory=list)
    # Inline abbreviations that introduce a side remark rather than part of a reusable pattern.
    abbreviation_markers: list[str] = Field(default_factory=list)
    families: list[HybridFamilyPolicy] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_policy(self) -> "HybridConstructionsPolicy":
        identifiers = [family.id for family in self.families]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("hybrid family ids must be unique")
        if set(self.meta_np) != {"heads", "connectors"} or any(
            not values or any(not value.strip() for value in values)
            for values in self.meta_np.values()
        ):
            raise ValueError("hybrid meta_np must define non-empty heads and connectors")
        if set(self.boundary) != {"pre_comma_frontier"}:
            raise ValueError("hybrid boundary settings contain unknown keys")
        return self


def hybrid_frame_has_dangling_tail(frame: str, policy: HybridConstructionsPolicy) -> bool:
    """True when the last literal word of a frame still expects an object."""
    words = frame.rstrip(" .").split()
    return bool(words) and words[-1].casefold() in {
        word.casefold() for word in policy.dangling_tail_words
    }


def hybrid_frame_has_abbreviation(frame: str, policy: HybridConstructionsPolicy) -> bool:
    """True when literal frame text contains a side-remark abbreviation."""
    literal = re.sub(r"\[[XYZ]\]", " ", frame).casefold()
    return any(
        re.search(rf"(?<!\w){re.escape(marker.casefold())}", literal)
        for marker in policy.abbreviation_markers
    )


def is_safe_hybrid_frame(
    frame: str, policy: HybridConstructionsPolicy, cluster_key: str | None
) -> bool:
    """Fail closed on hybrid candidate frames and unknown construction identities."""
    if not cluster_key:
        return False
    match = re.fullmatch(r"construction=([^:]+):([^:]+):([0-9a-f]{64})", cluster_key)
    if match is None or match.group(2) != policy.version:
        return False
    identity = match.group(1)
    if identity not in {family.id for family in policy.families if family.enabled}:
        return False
    placeholders = list(re.finditer(r"\[([XYZ])\]", frame))
    if not placeholders or len(placeholders) > 3:
        return False
    names = [match.group(1) for match in placeholders]
    if names != list("XYZ"[: len(names)]):
        return False
    for left, right in zip(placeholders, placeholders[1:], strict=False):
        if not frame[left.end() : right.start()].strip():
            return False
    if re.search(r"\[[^XYZ\]]+\]", frame):
        return False
    literal = re.sub(r"\[[XYZ]\]", " ", frame)
    if len(literal.split()) > policy.max_literal_words or re.search(r"[;:\[\]]", literal):
        return False
    if (
        HYBRID_SLOT_BOUNDARY.search(frame)
        or hybrid_frame_has_dangling_tail(frame, policy)
        or hybrid_frame_has_abbreviation(frame, policy)
    ):
        return False
    return not (
        re.search(r"\d", literal)
        or re.search(r"\[(?:\s*\d+\s*(?:[,;–-]\s*\d+\s*)*)\]", literal)
        or re.search(r"\b[A-Z]{2,}\b", literal)
    )


class LeadInsPolicy(VersionedPolicy):
    """Closed, owner-reviewed discourse lead-ins retained literally in frames."""

    lead_ins: list[str] = Field(min_length=1)

    @field_validator("lead_ins")
    @classmethod
    def validate_lead_ins(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().casefold() for value in values]
        if any(not value or value.endswith(",") for value in normalized):
            raise ValueError("lead-ins must be non-empty and omit a trailing comma")
        if len(normalized) != len(set(normalized)):
            raise ValueError("lead-ins must not contain duplicates")
        return values


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


class SentenceRulesPolicy(VersionedPolicy):
    """Provisional vocabulary and limits for shared sentence-boundary rules."""

    sentence_starters: list[str] = Field(min_length=1)
    unit_tokens: list[str] = Field(min_length=1)
    heading_max_chars: int = Field(ge=1, le=240)
    heading_max_words: int = Field(ge=1, le=40)

    @field_validator("sentence_starters", "unit_tokens")
    @classmethod
    def validate_tokens(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().casefold() for value in values]
        if any(not value or " " in value for value in normalized):
            raise ValueError("sentence rule vocabularies must contain non-empty single tokens")
        if len(normalized) != len(set(normalized)):
            raise ValueError("sentence rule vocabularies must not contain duplicates")
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
    # Shared by mining and V02.
    markers: dict[str, list[str]]
    # Strength markers read by exactly one consumer; see the merged properties below.
    validator_only_markers: dict[str, list[str]] = Field(default_factory=dict)
    mining_only_markers: dict[str, list[str]] = Field(default_factory=dict)
    # Base verb -> irregular inflected forms that suffix rules cannot derive.
    irregular_forms: dict[str, list[str]] = Field(default_factory=dict)
    neutral_verbs: list[str] = Field(default_factory=list)
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

    @field_validator("validator_only_markers", "mining_only_markers")
    @classmethod
    def validate_scoped_markers(cls, markers: dict[str, list[str]]) -> dict[str, list[str]]:
        if not set(markers) <= {"low", "moderate", "high", "absolute"} or any(
            not values
            or any(not marker.strip() for marker in values)
            or len(values) != len(set(values))
            for values in markers.values()
        ):
            raise ValueError("scoped markers must be unique, non-empty, known-strength lists")
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

    @field_validator("neutral_verbs")
    @classmethod
    def validate_neutral_verbs(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().casefold() for value in values]
        if any(not value for value in normalized) or len(normalized) != len(set(normalized)):
            raise ValueError("neutral_verbs must contain unique non-empty entries")
        return values

    @model_validator(mode="after")
    def validate_non_inflecting(self) -> "EpistemicMarkersPolicy":
        declared = {marker.casefold() for values in self.markers.values() for marker in values}
        names = [name.casefold() for name in self.non_inflecting]
        if len(names) != len(set(names)) or any(not name.strip() for name in names):
            raise ValueError("non_inflecting must be unique, non-empty markers")
        if not set(names) <= declared:
            raise ValueError("non_inflecting entries must be declared markers")
        validator_only = {
            marker.casefold()
            for values in self.validator_only_markers.values()
            for marker in values
        }
        mining_only = {
            marker.casefold() for values in self.mining_only_markers.values() for marker in values
        }
        if (validator_only | mining_only) & declared or validator_only & mining_only:
            raise ValueError("scoped markers must not repeat shared or other-scope markers")
        return self

    @property
    def validator_markers(self) -> dict[str, list[str]]:
        """Markers V02 enforces: scoped entries first, then the shared list."""
        return {
            strength: [*self.validator_only_markers.get(strength, []), *values]
            for strength, values in self.markers.items()
        }

    @property
    def mining_markers(self) -> dict[str, list[str]]:
        """Markers EpistemicTagger assigns: the shared list plus mining-only entries."""
        return {
            strength: [*values, *self.mining_only_markers.get(strength, [])]
            for strength, values in self.markers.items()
        }
