"""Typed draft and approved labels for the development gold set."""

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NoiseReason(StrEnum):
    CAPTION = "caption"
    TABLE = "table"
    FORMULA = "formula"
    REFERENCE = "reference"
    ACKNOWLEDGEMENT = "acknowledgement"
    FRAGMENT = "fragment"
    METADATA = "metadata"
    OTHER = "other"


class Strength(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    ABSOLUTE = "absolute"
    NONE = "none"


class Tense(StrEnum):
    PAST = "past"
    PRESENT = "present"
    PRESENT_PERFECT = "present_perfect"
    NONE = "none"


class Ownership(StrEnum):
    OWN = "own"
    PRIOR = "prior"
    UNCLEAR = "unclear"


class SlotLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=16)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self) -> "SlotLabel":
        if self.char_end <= self.char_start:
            raise ValueError("slot range must be a non-empty half-open span")
        return self


class GoldLabels(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keep: bool
    noise_reason: NoiseReason | None = None
    section: str = Field(default="OTHER", pattern=r"^[A-Z][A-Z0-9_]{0,63}$")
    epistemic_strength: Strength = Strength.NONE
    tense: Tense = Tense.NONE
    frame: str | None = None
    slots: list[SlotLabel] = Field(default_factory=list)
    ownership: Ownership = Ownership.UNCLEAR
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_keep_reason(self) -> "GoldLabels":
        if not self.keep and self.noise_reason is None:
            raise ValueError("noise_reason is required when keep is false")
        if self.keep and self.noise_reason is not None:
            raise ValueError("noise_reason must be omitted when keep is true")
        return self

    def validate_source_offsets(self, source_text: str) -> "GoldLabels":
        for slot in self.slots:
            if slot.char_end > len(source_text):
                raise ValueError("slot range is outside the source sentence")
        return self

    def validate_frame_matches_source(self, source_text: str) -> "GoldLabels":
        """Require ``frame`` to be the sentence with each slot span replaced by ``[name]``.

        Applied to AI drafts only; a human reviewer may deliberately trim a frame.
        """
        if not self.keep:
            return self
        if self.frame is None:
            raise ValueError("kept label requires a frame")
        rebuilt: list[str] = []
        position = 0
        for slot in sorted(self.slots, key=lambda item: item.char_start):
            if slot.char_start < position:
                raise ValueError("slot ranges overlap")
            rebuilt.append(source_text[position : slot.char_start])
            rebuilt.append(f"[{slot.name}]")
            position = slot.char_end
        rebuilt.append(source_text[position:])
        if _squash("".join(rebuilt)) != _squash(self.frame):
            raise ValueError("frame does not match the source sentence with slots replaced")
        return self


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
