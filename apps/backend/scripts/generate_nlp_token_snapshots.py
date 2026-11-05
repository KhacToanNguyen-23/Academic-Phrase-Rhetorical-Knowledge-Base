"""Generate committed spaCy token snapshots for phase-3 mining tests."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from aprkb.nlp import SpacyEngine

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "nlp_spike" / "sentences.yaml"
OUTPUT = ROOT / "tests" / "fixtures" / "nlp_spike" / "token_snapshots.json"


def main() -> None:
    with FIXTURE.open(encoding="utf-8") as fixture:
        payload = yaml.safe_load(fixture)
    texts = (
        payload["slot_cases"]
        + payload["phase3_cases"]
        + payload["filter_cases"]
        + payload["construction_cases"]
        + payload.get("phase6_cases", [])
        + payload.get("phase7_cases", [])
    )
    engine = SpacyEngine("en_core_web_sm")
    cases = []
    for text in texts:
        analyses = engine.analyze(text)
        if len(analyses) != 1:
            raise ValueError("snapshot inputs must contain exactly one sentence")
        cases.append({"text": text, "analysis": analyses[0].to_json()})
    snapshot = {
        "model_name": engine.info.model_name,
        "model_version": engine.info.model_version,
        "spacy_version": engine.info.spacy_version,
        "cases": cases,
    }
    OUTPUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
