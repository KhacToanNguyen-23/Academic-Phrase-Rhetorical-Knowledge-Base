"""Deterministic conservative keys that preserve tense and evidence distinctions."""

import hashlib
import re
from dataclasses import replace

from aprkb.modules.mining.stages.base import MiningItem, MiningStage
from aprkb.policies.loader import PolicyBundle


class Clusterer(MiningStage):
    name = "clusterer"
    requirement_id = "FR-06.2"

    def __init__(self, policy: PolicyBundle) -> None:
        self._policy_version = ":".join(
            (
                policy.mining_filter.version,
                policy.reporting_verbs.version,
                policy.slot_abstraction.version,
                policy.epistemic_markers.version,
            )
        )
        self._class_patterns = [
            (
                re.compile(rf"(?<!\w){re.escape(form)}(?!\w)", re.I),
                class_name,
            )
            for class_name, forms in policy.reporting_verbs.classes.items()
            for form in forms.present + forms.past + forms.present_perfect
        ]

    def process(self, batch: list[MiningItem]) -> list[MiningItem]:
        return [replace(item, cluster_key=self._key(item)) for item in batch]

    def _key(self, item: MiningItem) -> str:
        slot_signature = ",".join(
            f"{name}:{definition.type.value}" for name, definition in sorted(item.slots.items())
        )
        normalized_frame = re.sub(r"\s+", " ", item.text).strip().casefold()
        for pattern, class_name in self._class_patterns:
            normalized_frame = pattern.sub(f"{{reporting:{class_name}}}", normalized_frame, count=1)
            if "{reporting:" in normalized_frame:
                break
        material = "|".join(
            (
                "mining-v1",
                self._policy_version,
                normalized_frame,
                item.tense.value,
                (item.epistemic_strength or "unknown").casefold(),
                item.ownership.value,
                slot_signature,
                item.slot_binding_fingerprint or "unknown-bindings",
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()
