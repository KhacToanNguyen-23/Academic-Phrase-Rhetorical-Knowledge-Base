"""Canonical spacing for masked frame surfaces."""

import re
from dataclasses import replace

from aprkb.modules.mining.stages.base import MiningItem, MiningStage


class FrameNormalizer(MiningStage):
    name = "frame_normalizer"
    requirement_id = "FR-06.2"

    def process(self, batch: list[MiningItem]) -> list[MiningItem]:
        return [replace(item, text=re.sub(r"\s+", " ", item.text).strip()) for item in batch]
