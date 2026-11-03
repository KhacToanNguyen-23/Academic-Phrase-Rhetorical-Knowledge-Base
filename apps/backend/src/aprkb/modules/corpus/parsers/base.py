"""Parser contracts shared by text and PDF ingestion."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedSection:
    heading: str | None
    text: str
    order: int
    # Offset of `text` inside ParsedDocument.raw_text, so sentence offsets stay global.
    char_start: int = 0


@dataclass(frozen=True)
class ParsedDocument:
    sections: tuple[ParsedSection, ...]
    raw_text: str


class DocumentParser(ABC):
    @abstractmethod
    def supports(self, mime_type: str) -> bool: ...

    @abstractmethod
    def parse(self, blob: bytes) -> ParsedDocument: ...
