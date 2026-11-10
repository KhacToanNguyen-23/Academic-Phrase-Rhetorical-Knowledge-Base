"""Parser and policy rules for the self-authored measurement catalog (ADR-0015)."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aprkb.modules.measurement.importer import load_catalog, parse_catalog
from aprkb.policies.loader import load_policy_bundle
from aprkb.policies.schemas import MeasurementPolicy

SEED = Path(__file__).resolve().parents[5] / "data/seed/measurement_catalog.json"
POLICY = load_policy_bundle().measurement


def _doc(**overrides) -> bytes:
    payload = {
        "catalog_version": "0.1.0",
        "entries": [
            {"code": "accuracy", "kind": "metric", "name": "Accuracy", "definition": "Share."},
            {"code": "held_out", "kind": "method", "name": "Held out", "definition": "Score."},
        ],
        "relations": [{"from": "accuracy", "relation": "uses_method", "to": "held_out"}],
    }
    payload.update(overrides)
    return json.dumps(payload).encode()


def test_seed_catalog_parses_and_covers_all_kinds():
    catalog = load_catalog(SEED, POLICY)
    assert {entry.kind for entry in catalog.entries} == {"metric", "method", "protocol"}
    assert len(catalog.entries) >= 20
    assert len({entry.code for entry in catalog.entries}) == len(catalog.entries)


def test_parse_is_deterministic_and_hashes_raw_bytes():
    first, second = parse_catalog(_doc(), POLICY), parse_catalog(_doc(), POLICY)
    assert first == second
    assert len(first.content_sha256) == 64


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"catalog_version": "v1"}, "semantic version"),
        ({"entries": []}, "contain entries"),
        (
            {"entries": [{"code": "x", "kind": "metric", "name": "X", "definition": "D"}]},
            "Invalid measurement code",
        ),
        (
            {"entries": [{"code": "abc", "kind": "score", "name": "X", "definition": "D"}]},
            "Unknown measurement kind",
        ),
        (
            {
                "entries": [
                    {"code": "abc", "kind": "metric", "name": "X", "definition": "D"},
                    {"code": "abc", "kind": "metric", "name": "Y", "definition": "D"},
                ],
                "relations": [],
            },
            "Duplicate measurement code",
        ),
        (
            {
                "entries": [{"code": "abc", "kind": "metric", "name": " ", "definition": "D"}],
                "relations": [],
            },
            "Invalid measurement field: name",
        ),
        (
            {
                "entries": [
                    {
                        "code": "abc",
                        "kind": "metric",
                        "name": "X",
                        "definition": "D",
                        "copied_from": "book",
                    }
                ],
                "relations": [],
            },
            "entry structure",
        ),
        ({"relations": [{"from": "accuracy", "relation": "uses_method", "to": "nope"}]}, "unknown"),
        (
            {"relations": [{"from": "held_out", "relation": "uses_method", "to": "accuracy"}]},
            "not allowed by policy",
        ),
        (
            {"relations": [{"from": "accuracy", "relation": "uses_method", "to": "held_out"}] * 2},
            "Duplicate relation",
        ),
    ],
)
def test_invalid_catalogs_are_rejected_before_any_write(overrides, message):
    with pytest.raises(ValueError, match=message):
        parse_catalog(_doc(**overrides), POLICY)


def test_size_limit_and_non_json_are_rejected():
    small = POLICY.model_copy(update={"max_import_bytes": 10})
    with pytest.raises(ValueError, match="size limit"):
        parse_catalog(_doc(), small)
    with pytest.raises(ValueError, match="UTF-8 JSON"):
        parse_catalog(b"\xff\xfe", POLICY)


def test_aliases_are_trimmed_deduplicated_and_sorted():
    entries = [
        {
            "code": "f1_score",
            "kind": "metric",
            "name": "F1",
            "definition": "D",
            "aliases": [" F1 ", "F-measure", "F1"],
        },
    ]
    catalog = parse_catalog(_doc(entries=entries, relations=[]), POLICY)
    assert catalog.entries[0].aliases == ["F-measure", "F1"]


@pytest.mark.parametrize(
    "payload",
    [
        {"kinds": ["metric", "metric"]},
        {"link_statuses": ["proposed", "approved", "approved"]},
        {"relations": {"Bad-Name": {"from": ["metric"], "to": ["method"]}}},
        {"relations": {"uses": {"from": ["score"], "to": ["method"]}}},
        {"max_import_bytes": 0},
        {"unused_setting": True},
    ],
)
def test_invalid_measurement_policy_is_rejected(payload):
    base = POLICY.model_dump(by_alias=True)
    base.update(payload)
    with pytest.raises(ValidationError):
        MeasurementPolicy.model_validate(base)


def test_relation_rules_follow_direction():
    assert POLICY.relation_allowed("uses_method", "metric", "method")
    assert not POLICY.relation_allowed("uses_method", "method", "metric")
    assert not POLICY.relation_allowed("unknown", "metric", "method")


@pytest.mark.parametrize("codes", [[], ["DEFINE_METRIC", "DEFINE_METRIC"], ["define_metric"]])
def test_invalid_link_proposal_function_codes_are_rejected(codes):
    base = POLICY.model_dump(by_alias=True)
    base["link_proposal_function_codes"] = codes
    with pytest.raises(ValidationError):
        MeasurementPolicy.model_validate(base)
