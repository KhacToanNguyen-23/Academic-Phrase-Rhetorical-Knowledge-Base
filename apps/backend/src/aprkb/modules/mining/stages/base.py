"""Pure batch stage interface for the mining pipeline."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class MiningItem:
    text: str
    source_sentence_ids: list[UUID]


class MiningStage(ABC):
    name: str
    requirement_id: str

    @abstractmethod
    def process(self, batch: list[MiningItem]) -> list[MiningItem]: ...
