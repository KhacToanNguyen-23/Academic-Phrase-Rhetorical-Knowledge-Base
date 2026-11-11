"""Deterministic epistemic strength tagging from the reviewed marker policy."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from aprkb.modules.mining.stages.base import MiningItem, MiningStage
from aprkb.modules.mining.stages.epistemic_scorer import (
    NO_SPACY_PROVENANCE,
    SCORED_PROVENANCES,
    EpistemicScorer,
)

if TYPE_CHECKING:
    from aprkb.policies.schemas import EpistemicScoringPolicy


class EpistemicTagger(MiningStage):
    name = "epistemic_tagger"
    requirement_id = "FR-06.2"

    def __init__(
        self,
        policy: EpistemicScoringPolicy,
        scorer: EpistemicScorer | None = None,
    ) -> None:
        self._scorer = scorer or EpistemicScorer(policy)

    def process(self, batch: list[MiningItem]) -> list[MiningItem]:
        tagged = []
        for item in batch:
            if item.epistemic_provenance in SCORED_PROVENANCES:
                tagged.append(item)
                continue
            if item.epistemic_doc is None:
                tagged.append(
                    replace(
                        item,
                        epistemic_strength=None,
                        epistemic_status="unknown",
                        epistemic_score=None,
                        epistemic_provenance=NO_SPACY_PROVENANCE,
                        epistemic_modifiers=[],
                    )
                )
                continue
            result = self._scorer.score(item.epistemic_doc)
            tagged.append(
                replace(
                    item,
                    epistemic_strength=(
                        None
                        if result.label in {"negative_refuted", "not_applicable"}
                        else result.label
                    ),
                    epistemic_status=(
                        "refuted"
                        if result.label == "negative_refuted"
                        else "neutral"
                        if result.label == "not_applicable"
                        else "assigned"
                    ),
                    epistemic_score=result.score,
                    epistemic_provenance=result.provenance,
                    epistemic_modifiers=result.detected_modifiers,
                    epistemic_lemma=result.lemma,
                    epistemic_pos=result.pos,
                    epistemic_construction_family=result.construction_family,
                    epistemic_lexicon_revision=result.lexicon_revision,
                )
            )
        return tagged
