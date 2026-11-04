"""Deterministic, database-free validation of Offline packs."""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from aprkb.modules.pack.models import Manifest, Pattern


def _find_seed_dir() -> Path | None:
    """Locate the monorepo-root data/seed directory; absent in a standalone container checkout."""
    parents = Path(__file__).resolve().parents
    return parents[6] / "data" / "seed" if len(parents) > 6 else None


SEED_DIR = _find_seed_dir()
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")
PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z_0-9]*)\}")
BRACKET_RE = re.compile(r"\[[^\[\]]+\]")


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class References:
    taxonomy_version: str
    intent_paths: frozenset[tuple[str, str, str, str, str]]
    sections: frozenset[str]
    genres: frozenset[str]
    enums: dict[str, frozenset[str]]
    licenses: dict[str, bool]


@dataclass
class ValidationReport:
    findings: list[Finding]
    manifest: Manifest | None = None
    patterns: list[Pattern] | None = None
    pack_sha256: str | None = None

    @property
    def has_errors(self) -> bool:
        return any(item.severity == "error" for item in self.findings)

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": not self.has_errors,
            "findings": [item.as_dict() for item in self.findings],
        }


def load_references(reference_dir: Path | None = SEED_DIR) -> References:
    if reference_dir is None:
        raise RuntimeError(
            "Reference data is only available from a monorepo checkout, not a standalone "
            "backend build."
        )
    taxonomy = json.loads((reference_dir / "taxonomy.json").read_text(encoding="utf-8"))
    enums = json.loads((reference_dir / "reference_enums.json").read_text(encoding="utf-8"))
    licenses = yaml.safe_load((reference_dir / "licenses.yaml").read_text(encoding="utf-8"))
    paths: set[tuple[str, str, str, str, str]] = set()
    for section in taxonomy["sections"]:
        for move in section["moves"]:
            for step in move["steps"]:
                for intent in step["intents"]:
                    paths.add(
                        (
                            taxonomy["version"],
                            section["code"],
                            move["code"],
                            step["code"],
                            intent["code"],
                        )
                    )
    return References(
        taxonomy_version=taxonomy["version"],
        intent_paths=frozenset(paths),
        sections=frozenset(s["code"] for s in taxonomy["sections"]),
        genres=frozenset(g["code"] for g in taxonomy["article_genres"]),
        enums={key: frozenset(item["code"] for item in values) for key, values in enums.items()},
        licenses={item["code"]: item["allows_mining"] for item in licenses["licenses"]},
    )


def _finding(items: list[Finding], code: str, path: str, message: str) -> None:
    items.append(Finding(code, "warning" if code.startswith("W") else "error", path, message))


def _path(base: str, loc: tuple[str | int, ...]) -> str:
    result = base
    for part in loc:
        result += f"[{part}]" if isinstance(part, int) else f".{part}"
    return result


def _schema_findings(items: list[Finding], error: ValidationError, base: str) -> None:
    for issue in error.errors():
        path = _path(base, issue["loc"])
        if issue["type"] == "extra_forbidden":
            code = "E14"
        elif path.endswith(".type"):
            code = "E10"
        elif ".provenance" in path:
            code = "E11"
        elif path.endswith(".claim_type"):
            code = "E05"
        elif path.endswith(".epistemic_strength"):
            code = "E06"
        elif path.endswith(".allowed_sections"):
            code = "E07"
        elif path.startswith("manifest"):
            code = "E01"
        else:
            code = "E14"
        _finding(items, code, path, issue["msg"])


def _scan_provenance(items: list[Finding], value: Any, path: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if re.search(
                r"(?:source|article|sentence).*(?:text|body|content)|(?:text|body|content)",
                key,
                re.I,
            ):
                _finding(items, "E14", child_path, "Source or article text is forbidden")
            _scan_provenance(items, child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_provenance(items, child, f"{path}[{index}]")
    elif isinstance(value, str) and UUID_RE.fullmatch(value):
        _finding(items, "E14", path, "UUID values are forbidden in provenance")


def validate_pack(path: Path, references: References | None = None) -> ValidationReport:
    """Return all actionable findings; missing/unreadable files raise OSError/ValueError."""
    references = references or load_references()
    patterns_bytes = (path / "patterns.json").read_bytes()
    patterns_raw = json.loads(patterns_bytes)
    if not isinstance(patterns_raw, list):
        raise ValueError("patterns.json must be a JSON array")
    items: list[Finding] = []
    try:
        manifest_bytes = (path / "manifest.json").read_bytes()
        manifest_raw = json.loads(manifest_bytes)
    except (OSError, ValueError):
        manifest_bytes = b""
        _finding(items, "E01", "manifest", "manifest.json is missing or invalid")
        manifest = None
    else:
        try:
            manifest = Manifest.model_validate_json(json.dumps(manifest_raw))
        except ValidationError as error:
            _schema_findings(items, error, "manifest")
            manifest = None
    patterns: list[Pattern] = []
    for index, raw in enumerate(patterns_raw):
        try:
            patterns.append(Pattern.model_validate_json(json.dumps(raw)))
        except ValidationError as error:
            _schema_findings(items, error, f"patterns[{index}]")
        if not isinstance(raw, dict):
            continue
        base = f"patterns[{index}]"
        if raw.get("status") != "approved":
            _finding(items, "E04", f"{base}.status", "Only approved patterns may be imported")
        intent = raw.get("intent", {})
        if isinstance(intent, dict):
            keys = (
                intent.get("taxonomy_version"),
                intent.get("section"),
                intent.get("move"),
                intent.get("step"),
                intent.get("intent"),
            )
            if intent.get("taxonomy_version") != references.taxonomy_version:
                _finding(
                    items,
                    "E02",
                    f"{base}.intent.taxonomy_version",
                    "Taxonomy version is unavailable",
                )
            if not all(isinstance(key, str) for key in keys) or keys not in references.intent_paths:
                _finding(items, "E03", f"{base}.intent", "Full intent path is unresolved")
        versions = raw.get("versions", [])
        if not isinstance(versions, list):
            continue
        numbers = [v.get("version_no") for v in versions if isinstance(v, dict)]
        if numbers != list(range(1, len(versions) + 1)):
            _finding(
                items,
                "E16",
                f"{base}.versions",
                "Version numbers must be unique and consecutive from 1",
            )
        if raw.get("current_version_no") != (numbers[-1] if numbers else None):
            _finding(
                items,
                "E16",
                f"{base}.current_version_no",
                "Current version must be the latest version",
            )
        for j, version in enumerate(versions):
            if isinstance(version, dict):
                _check_version(items, version, f"{base}.versions[{j}]", references)
    if manifest is not None:
        if manifest.taxonomy_version != references.taxonomy_version:
            _finding(items, "E02", "manifest.taxonomy_version", "Taxonomy version is unavailable")
        if (
            manifest.files[0].name != "patterns.json"
            or manifest.files[0].sha256 != hashlib.sha256(patterns_bytes).hexdigest()
        ):
            _finding(items, "E01", "manifest.files[0].sha256", "patterns.json SHA-256 mismatch")
        if manifest.counts.patterns != len(patterns_raw) or manifest.counts.versions != sum(
            len(p.get("versions", [])) for p in patterns_raw if isinstance(p, dict)
        ):
            _finding(items, "E01", "manifest.counts", "Manifest counts do not match patterns.json")
    items.sort(key=lambda item: (item.path, item.code, item.message))
    digest = hashlib.sha256(manifest_bytes + patterns_bytes).hexdigest()
    return ValidationReport(
        items, manifest, patterns if len(patterns) == len(patterns_raw) else None, digest
    )


def _check_version(
    items: list[Finding], version: dict[str, Any], base: str, refs: References
) -> None:
    for field, code, group in (
        ("claim_type", "E05", "claim_type"),
        ("epistemic_strength", "E06", "epistemic_strength"),
    ):
        if (
            not isinstance(version.get(field), str)
            or version.get(field) not in refs.enums.get(group, ())
            or version.get(field) == "unknown"
        ):
            _finding(items, code, f"{base}.{field}", f"Invalid {field}")
    frame = version.get("canonical_frame", "")
    slots = version.get("slots", {})
    if isinstance(frame, str) and isinstance(slots, dict):
        names = set(PLACEHOLDER_RE.findall(frame))
        residue = PLACEHOLDER_RE.sub("", frame)
        if BRACKET_RE.search(frame) or "{" in residue or "}" in residue or names != set(slots):
            _finding(
                items,
                "E09",
                f"{base}.canonical_frame",
                "Frame placeholders must exactly match slot keys and use braces",
            )
        for name, slot in slots.items():
            if not isinstance(slot, dict) or not slot.get("type"):
                _finding(items, "E10", f"{base}.slots.{name}.type", "Slot type is required")
            if isinstance(slot, dict):
                for field in ("label", "instruction", "example"):
                    if not slot.get(field):
                        _finding(
                            items, "W03", f"{base}.slots.{name}.{field}", f"Slot {field} is missing"
                        )
    usage = version.get("usage", {})
    if isinstance(usage, dict):
        sections = usage.get("allowed_sections")
        if (
            not isinstance(sections, list)
            or not sections
            or any(not isinstance(s, str) or s not in refs.sections for s in sections)
        ):
            _finding(
                items,
                "E07",
                f"{base}.usage.allowed_sections",
                "Allowed sections must be nonempty and known",
            )
        genres = usage.get("allowed_genres", [])
        if isinstance(genres, list):
            if any(not isinstance(g, str) or g not in refs.genres for g in genres):
                _finding(items, "E08", f"{base}.usage.allowed_genres", "Unknown genre")
            if not genres:
                _finding(
                    items, "W04", f"{base}.usage.allowed_genres", "Empty genres means all genres"
                )
        if not usage.get("evidence_min"):
            _finding(items, "W02", f"{base}.usage.evidence_min", "No minimum evidence level")
        elif not isinstance(usage["evidence_min"], str) or usage[
            "evidence_min"
        ] not in refs.enums.get("evidence_level", ()):
            _finding(items, "E05", f"{base}.usage.evidence_min", "Unknown evidence level")
        if usage.get("forbidden_contexts"):
            _finding(
                items,
                "W06",
                f"{base}.usage.forbidden_contexts",
                "Forbidden contexts have no defined matching semantics",
            )
    if not version.get("variants"):
        _finding(items, "W01", f"{base}.variants", "No phrase variants")
    _finding(items, "W05", f"{base}.provenance", "No discipline metadata in pack v0.1")
    provenance = version.get("provenance", {})
    if not isinstance(provenance, dict):
        _finding(items, "E11", f"{base}.provenance", "Provenance must be an object")
        return
    _scan_provenance(items, provenance, f"{base}.provenance")
    kind = provenance.get("source_type")
    if kind not in ("authored", "mined"):
        _finding(
            items, "E11", f"{base}.provenance.source_type", "Source type must be authored or mined"
        )
    if provenance.get("section_code") and (
        not isinstance(provenance["section_code"], str)
        or provenance["section_code"] not in refs.sections
    ):
        _finding(items, "E07", f"{base}.provenance.section_code", "Unknown source section")
    if kind == "mined":
        license_code = provenance.get("license_code")
        article = provenance.get("article")
        count = provenance.get("source_sentence_count")
        if (
            not license_code
            or not isinstance(article, dict)
            or not (article.get("doi") or (article.get("source") and article.get("external_id")))
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count < 1
        ):
            _finding(
                items,
                "E11",
                f"{base}.provenance",
                "Mined source needs license, article key and positive sentence count",
            )
        if license_code == "DEV-UNVERIFIED" or not refs.licenses.get(str(license_code), False):
            _finding(
                items,
                "E12",
                f"{base}.provenance.license_code",
                "License is unknown or forbids mining",
            )
        reviews = version.get("reviews", [])
        rounds = (
            [(r.get("round"), r.get("decision")) for r in reviews]
            if isinstance(reviews, list) and all(isinstance(r, dict) for r in reviews)
            else []
        )
        if rounds not in (
            [(1, "approve"), (2, "approve")],
            [(2, "approve"), (1, "approve")],
        ):
            _finding(
                items,
                "E13",
                f"{base}.reviews",
                "Mined version requires exactly two approving rounds",
            )
    elif kind == "authored" and version.get("reviews"):
        _finding(items, "E13", f"{base}.reviews", "Authored version may not carry mining reviews")
