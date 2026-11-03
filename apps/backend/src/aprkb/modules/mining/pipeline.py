"""Pure sequential mining pipeline over an injected ordered stage registry."""

from aprkb.modules.mining.stages.base import MiningItem, MiningStage


class MiningPipeline:
    def __init__(self, *, stages: list[MiningStage]) -> None:
        self._stages = tuple(stages)

    def process(self, batch: list[MiningItem]) -> list[MiningItem]:
        result = batch
        for stage in self._stages:
            result = stage.process(result)
        return result
