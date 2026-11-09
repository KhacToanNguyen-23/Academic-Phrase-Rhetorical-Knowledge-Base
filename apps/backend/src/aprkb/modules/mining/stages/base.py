"""Pure batch stage interface for the mining pipeline."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from aprkb.modules.mining.schemas import Ownership, SlotDefinition, Tense
from aprkb.nlp.features import TokenFeature


@dataclass(frozen=True)
class ExtractionOccurrence:
    """Private offsets for one source occurrence; deliberately contains no source text."""

    sentence_id: UUID
    sentence_start: int
    sentence_end: int
    slot_spans: dict[str, tuple[int, int]]


@dataclass(frozen=True)
class MiningItem:
    text: str
    source_sentence_ids: list[UUID]
    section_code: str | None = None
    char_start: int = 0
    previous_text: str | None = None
    tokens: tuple[TokenFeature, ...] | None = None
    locator: str | None = None
    slots: dict[str, SlotDefinition] = field(default_factory=dict)
    occurrences: list[ExtractionOccurrence] = field(default_factory=list)
    tense: Tense = Tense.UNKNOWN
    modality: str | None = None
    ownership: Ownership = Ownership.UNCLEAR
    epistemic_strength: str | None = None
    epistemic_status: Literal["assigned", "neutral", "ambiguous", "unknown"] = "unknown"
    cluster_key: str | None = None
    confidence: float | None = None
    construction_id: str | None = None
    construction_version: str | None = None
    canonical_skeleton: str | None = None


class MiningStage(ABC):
    name: str
    requirement_id: str

    @abstractmethod
    def process(self, batch: list[MiningItem]) -> list[MiningItem]: ...
