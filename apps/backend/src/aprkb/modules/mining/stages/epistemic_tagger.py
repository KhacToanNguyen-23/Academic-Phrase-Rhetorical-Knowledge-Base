"""Deterministic epistemic strength tagging from the reviewed marker policy."""

import re
from dataclasses import replace
from typing import Literal

from aprkb.modules.mining.stages.base import MiningItem, MiningStage
from aprkb.policies.schemas import EpistemicMarkersPolicy


class EpistemicTagger(MiningStage):
    name = "epistemic_tagger"
    requirement_id = "FR-06.2"

    def __init__(self, policy: EpistemicMarkersPolicy) -> None:
        markers_by_strength = policy.mining_markers
        irregular_strength = {
            base.casefold(): strength
            for strength, markers in markers_by_strength.items()
            for base in markers
        }
        self._markers = {
            strength: tuple(
                re.compile(rf"(?<!\w){re.escape(marker)}(?!\w)", re.IGNORECASE)
                for marker in sorted(
                    [
                        *values,
                        *(
                            form
                            for base, forms in policy.irregular_forms.items()
                            if irregular_strength.get(base.casefold()) == strength
                            for form in forms
                        ),
                    ],
                    key=len,
                    reverse=True,
                )
            )
            for strength, values in markers_by_strength.items()
        }
        self._neutral = tuple(
            re.compile(rf"(?<!\w){re.escape(verb)}(?!\w)", re.IGNORECASE)
            for verb in sorted(policy.neutral_verbs, key=len, reverse=True)
        )

    def process(self, batch: list[MiningItem]) -> list[MiningItem]:
        tagged = []
        for item in batch:
            strength, status = self._tags(item.text)
            tagged.append(replace(item, epistemic_strength=strength, epistemic_status=status))
        return tagged

    def _tags(
        self, text: str
    ) -> tuple[str | None, Literal["assigned", "neutral", "ambiguous", "unknown"]]:
        strengths = self._strengths(text)
        if len(strengths) == 1:
            return next(iter(strengths)), "assigned"
        if len(strengths) > 1:
            return None, "ambiguous"
        if any(pattern.search(text) for pattern in self._neutral):
            return None, "neutral"
        return None, "unknown"

    def _strength(self, text: str) -> str | None:
        found = self._strengths(text)
        return next(iter(found)) if len(found) == 1 else None

    def _strengths(self, text: str) -> set[str]:
        found: set[str] = set()
        for strength, patterns in self._markers.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    prefix = text[: match.start()]
                    if re.search(r"\b(?:not|never|no)\b(?:\W+\w+){0,2}\W*$", prefix, re.I):
                        continue
                    found.add(strength)
                    break
        return found
