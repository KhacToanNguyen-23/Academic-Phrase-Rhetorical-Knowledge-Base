"""Pack validator tests use only invented mutations of the self-authored demo pack."""

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from aprkb.modules.pack.validator import validate_pack

ROOT = Path(__file__).resolve().parents[4]
SAMPLE = ROOT / "data" / "packs" / "sample-demo"


def test_shipped_sample_matches_manifest_and_contract() -> None:
    assert not validate_pack(SAMPLE).has_errors


def first_slot(patterns: list[dict[str, Any]]) -> dict[str, Any]:
    return next(iter(patterns[0]["versions"][0]["slots"].values()))


def make_pack(tmp_path: Path, mutate: Any = None) -> Path:
    target = tmp_path / "pack"
    shutil.copytree(SAMPLE, target)
    patterns = json.loads((target / "patterns.json").read_text(encoding="utf-8"))
    if mutate:
        mutate(patterns)
    content = json.dumps(patterns, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    (target / "patterns.json").write_bytes(content.encode("utf-8"))
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    manifest["counts"] = {
        "patterns": len(patterns),
        "versions": sum(len(p["versions"]) for p in patterns),
    }
    manifest["files"][0]["sha256"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return target


def has_code(path: Path, code: str) -> bool:
    return code in {finding.code for finding in validate_pack(path).findings}


@pytest.mark.parametrize(
    "code,mutate",
    [
        ("E02", lambda p: p[0]["intent"].update(taxonomy_version="9.9")),
        ("E03", lambda p: p[0]["intent"].update(intent="MISSING")),
        ("E04", lambda p: p[0].update(status="draft")),
        ("E05", lambda p: p[0]["versions"][0].update(claim_type="unknown")),
        ("E06", lambda p: p[0]["versions"][0].update(epistemic_strength="unknown")),
        ("E07", lambda p: p[0]["versions"][0]["usage"].update(allowed_sections=[])),
        ("E08", lambda p: p[0]["versions"][0]["usage"].update(allowed_genres=["NOPE"])),
        ("E09", lambda p: p[0]["versions"][0].update(canonical_frame="[topic]")),
        ("E10", lambda p: first_slot(p).pop("type")),
        ("E11", lambda p: p[0]["versions"][0]["provenance"].update(source_type="other")),
        (
            "E12",
            lambda p: p[0]["versions"][0]["provenance"].update(
                source_type="mined",
                license_code="DEV-UNVERIFIED",
                article={"doi": "10.0000/invented"},
                source_sentence_count=1,
                reviews=[],
            ),
        ),
        (
            "E13",
            lambda p: p[0]["versions"][0]["provenance"].update(
                source_type="mined",
                license_code="CC-BY",
                article={"doi": "10.0000/invented"},
                source_sentence_count=1,
            ),
        ),
        ("E14", lambda p: p[0]["versions"][0]["provenance"].update(article_text="invented text")),
        ("E16", lambda p: p[0]["versions"][0].update(version_no=2)),
        ("W01", lambda p: p[0]["versions"][0].update(variants=[])),
        ("W02", lambda p: p[0]["versions"][0]["usage"].update(evidence_min=None)),
        ("W03", lambda p: first_slot(p).pop("label")),
        ("W04", lambda p: p[0]["versions"][0]["usage"].update(allowed_genres=[])),
        ("W05", lambda p: None),
        ("W06", lambda p: p[0]["versions"][0]["usage"].update(forbidden_contexts=["invented"])),
    ],
)
def test_code_findings(tmp_path: Path, code: str, mutate: Any) -> None:
    assert has_code(make_pack(tmp_path, mutate), code)


def test_manifest_digest_error(tmp_path: Path) -> None:
    pack = make_pack(tmp_path)
    (pack / "patterns.json").write_text("[]", encoding="utf-8")
    assert has_code(pack, "E01")


def test_unknown_fields_and_provenance_uuid_are_e14(tmp_path: Path) -> None:
    pack = make_pack(
        tmp_path,
        lambda p: p[0]["versions"][0]["provenance"].update(
            article_id="11111111-1111-4111-8111-111111111111"
        ),
    )
    assert has_code(pack, "E14")
