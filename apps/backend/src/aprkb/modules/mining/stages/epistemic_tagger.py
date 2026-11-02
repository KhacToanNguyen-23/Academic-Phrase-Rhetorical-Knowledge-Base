"""Deterministic epistemic strength tagging from the reviewed marker policy."""

import re
from dataclasses import replace

from aprkb.modules.mining.stages.base import MiningItem, MiningStage
from aprkb.policies.schemas import EpistemicMarkersPolicy


class EpistemicTagger(MiningStage):
    name = "epistemic_tagger"
    requirement_id = "FR-06.2"

    def __init__(self, policy: EpistemicMarkersPolicy) -> None:
        self._markers = {
            strength: tuple(
                re.compile(rf"(?<!\w){re.escape(marker)}(?!\w)", re.IGNORECASE)
                for marker in sorted(values, key=len, reverse=True)
            )
            for strength, values in policy.markers.items()
        }

    def process(self, batch: list[MiningItem]) -> list[MiningItem]:
        return [replace(item, epistemic_strength=self._strength(item.text)) for item in batch]

    def _strength(self, text: str) -> str | None:
        found: set[str] = set()
        for strength, patterns in self._markers.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    prefix = text[: match.start()]
                    if re.search(r"\b(?:not|never|no)\b(?:\W+\w+){0,2}\W*$", prefix, re.I):
                        continue
                    found.add(strength)
                    break
        return next(iter(found)) if len(found) == 1 else None
