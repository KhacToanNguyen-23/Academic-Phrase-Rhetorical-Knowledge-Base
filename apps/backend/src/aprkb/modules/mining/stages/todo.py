"""Pass-through mining stage until its algorithm is approved."""

from aprkb.modules.mining.stages.base import MiningItem, MiningStage


class TodoMiningStage(MiningStage):
    def __init__(self, name: str, requirement_id: str) -> None:
        self.name = name
        self.requirement_id = requirement_id

    def process(self, batch: list[MiningItem]) -> list[MiningItem]:
        # TODO(owner, PRD-6.3): implement this stage after the mining algorithm is approved.
        return batch
