"""Typed mining output schemas. Public slot values describe types, never source text."""

import re
from collections.abc import Iterable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SlotType(StrEnum):
    NOUN_PHRASE = "noun_phrase"
    CLAUSE = "clause"
    DETERMINER_OWN = "determiner_own"
    DETERMINER_PRIOR = "determiner_prior"


class ProtectedSignal(StrEnum):
    CITATION = "citation"
    NUMBER = "number"
    PERCENTAGE = "percentage"
    UNIT = "unit"
    YEAR = "year"
    ACRONYM = "acronym"
    NEGATION = "negation"
    MODAL = "modal"
    COMPARISON = "comparison"


class SlotDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: SlotType
    signals: list[ProtectedSignal] = Field(default_factory=list)


class Tense(StrEnum):
    PRESENT = "present"
    PAST = "past"
    PRESENT_PERFECT = "present_perfect"
    PAST_PERFECT = "past_perfect"
    UNKNOWN = "unknown"


class Ownership(StrEnum):
    OWN = "own"
    PRIOR = "prior"
    UNCLEAR = "unclear"


def is_safe_masked_frame(
    frame: str, reporting_forms: Iterable[str], lead_ins: Iterable[str] = ()
) -> bool:
    """Accept only the extractor's positional grammar and a reviewed reporting verb."""
    normalized = frame.strip().casefold().rstrip(".!?").strip()
    allowed_lead_ins = {value.strip().casefold().removesuffix(",") for value in lead_ins}
    if ", " in normalized:
        possible_lead_in, remainder = normalized.split(", ", 1)
        if possible_lead_in not in allowed_lead_ins:
            return False
        normalized = remainder
    if ", " in normalized:
        return False
    known_forms = {form.strip().casefold() for form in reporting_forms}
    if normalized.startswith("[x] [y] "):
        prefix, separator, suffix = normalized.partition(" that [z]")
        verb = prefix.removeprefix("[x] [y] ")
    elif normalized.startswith("[x] "):
        prefix, separator, suffix = normalized.partition(" that [y]")
        verb = prefix.removeprefix("[x] ")
    else:
        return False
    return bool(
        separator and not suffix and verb in known_forms and not re.search(r"\[[^]]+\]", verb)
    )
