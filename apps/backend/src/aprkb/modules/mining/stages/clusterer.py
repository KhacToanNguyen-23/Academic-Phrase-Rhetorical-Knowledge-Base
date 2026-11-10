"""Deterministic conservative keys that preserve tense and evidence distinctions."""

import hashlib
import re
from dataclasses import replace

from aprkb.modules.mining.stages.base import MiningItem, MiningStage
from aprkb.policies.loader import PolicyBundle

_REGEX_POLICY_VERSION = "0.2.0:0.2.0:0.2.0:epistemic-score-0.1.0"


class Clusterer(MiningStage):
    name = "clusterer"
    requirement_id = "FR-06.2"

    def __init__(self, policy: PolicyBundle) -> None:
        self._policy_version = ":".join(
            (
                policy.mining_filter.version,
                policy.reporting_verbs.version,
                policy.slot_abstraction.version,
                policy.epistemic_scoring.version,
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
        normalized_frame = (
            re.sub(r"\s+", " ", item.canonical_skeleton or item.text).strip().casefold()
        )
        for pattern, class_name in self._class_patterns:
            normalized_frame = pattern.sub(f"{{reporting:{class_name}}}", normalized_frame, count=1)
            if "{reporting:" in normalized_frame:
                break
        material_parts = [
            "mining-v1",
            _REGEX_POLICY_VERSION if item.locator is None else self._policy_version,
            normalized_frame,
            item.tense.value,
            (item.epistemic_strength or "unknown").casefold(),
            item.ownership.value,
            slot_signature,
            # Fixed value: slot text stays out of the key, keeping construction keys stable.
            "unknown-bindings",
        ]
        if item.locator is not None:
            material_parts.insert(2, item.locator)
        material = "|".join(material_parts)
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        if item.construction_id is not None:
            return f"construction={item.construction_id}:{item.construction_version}:{digest}"
        return digest
