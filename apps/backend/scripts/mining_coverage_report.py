"""Produce a hash-only, rights-checked corpus coverage manifest for Tier 1/2.

Identity recipe: SHA-256 of ``blob_key \x1f sentence_ordinal \x1f char_start`` (UTF-8).
Output recipe: SHA-256 of ``frame \x1f sorted slot name:type \x1f tense \x1f ownership
\x1f construction_id \x1f cluster_key`` (UTF-8). The script verifies mining rights
before reading any blob and refuses database URLs other than ``aprkb_test`` on port 55433.
Rights may instead come from ``--rights-file``: UTF-8 lines of ``blob_key<TAB>license_code``,
exported read-only by the operator for mining-allowed articles only. The script then opens no
database connection at all.
``--article-ids`` optionally maps ``blob_key<TAB>article_id`` so that two blobs of one article
count once in recurrence figures. ``--exclude-cluster-key`` drops the key from the output hash,
for comparing extraction content across a change to the key recipe. Recurrence uses the canonical
frame: whitespace collapsed,
final period removed, case folded, and the skeleton instead of the surface text where present.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from uuid import uuid4

from mining_trial_report import _spacy_section_analyser, _verify_rights
from sqlalchemy.engine import make_url

from aprkb.core.config import settings
from aprkb.modules.corpus.ingest import parse_and_analyze
from aprkb.modules.corpus.parsers import parser_for_key
from aprkb.modules.mining.pipeline import MiningPipeline
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.modules.mining.stages.construction_matcher import ReportingWithConstruction
from aprkb.modules.mining.stages.sentence_filter import SentenceFilter
from aprkb.nlp import SentenceAnalysis, SpacyEngine
from aprkb.nlp.syntax import usable_tokens
from aprkb.policies.loader import load_policy_bundle


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _database_url(value: str) -> str:
    url = make_url(value)
    if url.database != "aprkb_test" or url.port != 55433:
        raise ValueError("coverage runs require aprkb_test on port 55433")
    return value


def _verify_rights_file(files: list[Path], blob_root: Path, rights_file: Path) -> tuple[str, ...]:
    """Check every file's blob key against an exported mining-allowed snapshot."""
    root = blob_root.resolve()
    keys: set[str] = set()
    for path in files:
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("coverage files must be inside the blob root")
        keys.add(resolved.relative_to(root).as_posix())
    authorized = dict(
        line.split("	", 1)
        for line in rights_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    missing = keys - authorized.keys()
    if missing:
        raise ValueError(f"{len(missing)} coverage files lack a mining-allowed record")
    return tuple(sorted({authorized[key] for key in keys}))


def _canonical_frame(frame: str, skeleton: str | None) -> str:
    """Comparison form of a frame; report-only, so Tier 1 output hashes stay untouched."""
    normalized = re.sub(r"\s+", " ", skeleton or frame).strip()
    return normalized.removesuffix(".").rstrip().casefold()


def _article_ids(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    return dict(
        line.split("	", 1) for line in path.read_text(encoding="utf-8").splitlines() if line
    )


async def _run(
    directory: Path,
    blob_root: Path,
    *,
    hybrid: bool,
    model: str,
    database_url: str | None,
    rights_file: Path | None,
    article_ids: dict[str, str] | None = None,
    exclude_cluster_key: bool = False,
) -> tuple[list[dict[str, str]], dict[str, object]]:
    files = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.casefold() in {".txt", ".md"}
    )
    if len(files) != 51:
        raise ValueError("the reproducible coverage set must contain exactly 51 blobs")
    if rights_file is not None:
        licenses = _verify_rights_file(files, blob_root, rights_file)
    elif database_url is not None:
        settings.database_url = _database_url(database_url)
        licenses = await _verify_rights(files, blob_root)
    else:
        raise ValueError("a rights source is required")
    policies = load_policy_bundle()
    nlp = SpacyEngine(model)
    stages = build_stages(policy_bundle=policies, hybrid_enabled=hybrid)
    sentence_filter = next(stage for stage in stages if isinstance(stage, SentenceFilter))
    extractor = next(stage for stage in stages if isinstance(stage, ReportingWithConstruction))
    pipeline = MiningPipeline(stages=stages)

    manifests: list[dict[str, str]] = []
    tiers: Counter[str] = Counter()
    families: Counter[str] = Counter()
    rejections: Counter[str] = Counter()
    frames: defaultdict[str, set[str]] = defaultdict(set)
    canonical: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    articles = article_ids or {}
    keys: set[str] = set()
    scanned = kept = extracted = 0

    for path in files:
        blob_key = path.resolve().relative_to(blob_root.resolve()).as_posix()
        parser = parser_for_key(path.name)
        if parser is None:
            raise ValueError(f"no parser for extension {path.suffix}")
        prepared = parse_and_analyze(
            parser,
            path.read_bytes(),
            section_headings=policies.section_headings,
            analyse_section=lambda text: _spacy_section_analyser(nlp, text),
        )
        previous_text: str | None = None
        previous_section: str | None = None
        for ordinal, sentence in enumerate(prepared.sentences):
            scanned += 1
            analysis = (
                SentenceAnalysis.from_json(sentence.nlp_features)
                if sentence.nlp_features is not None
                else None
            )
            tokens = usable_tokens(analysis) if analysis is not None else None
            context = (
                previous_text
                if sentence.section_code is not None and sentence.section_code == previous_section
                else None
            )
            item = MiningItem(
                text=sentence.text,
                source_sentence_ids=[uuid4()],
                section_code=sentence.section_code,
                char_start=sentence.char_start,
                previous_text=context,
                tokens=tokens,
                locator=f"syntax:{nlp.info.model_name}:{nlp.info.model_version}"
                if tokens is not None
                else None,
            )
            rejection = sentence_filter.reject_reason(item)
            if rejection is not None:
                rejections[rejection] += 1
            else:
                kept += 1
                construction_before = extractor.constructions.rejection_counts
                hybrid_before = (
                    extractor.hybrid.rejection_counts if extractor.hybrid is not None else {}
                )
                result = pipeline.process([item])
                if result:
                    output = result[0]
                    extracted += 1
                    tier = (
                        "tier2" if (output.construction_id or "").startswith("hybrid_") else "tier1"
                    )
                    family = output.construction_id or "reporting"
                    tiers[tier] += 1
                    families[family] += 1
                    frames[output.text].add(blob_key)
                    canonical[(tier, _canonical_frame(output.text, output.canonical_skeleton))].add(
                        articles.get(blob_key, blob_key)
                    )
                    if output.cluster_key:
                        keys.add(output.cluster_key)
                    slot_sig = ",".join(
                        f"{name}:{definition.type.value}"
                        for name, definition in sorted(output.slots.items())
                    )
                    material = "\x1f".join(
                        (
                            output.text,
                            slot_sig,
                            output.tense.value,
                            output.ownership.value,
                            output.construction_id or "",
                            "" if exclude_cluster_key else output.cluster_key or "",
                        )
                    )
                    identity = "\x1f".join((blob_key, str(ordinal), str(sentence.char_start)))
                    manifests.append(
                        {
                            "identity_sha256": _sha256(identity),
                            "output_sha256": _sha256(material),
                            "tier": tier,
                            "family": family,
                        }
                    )
                else:
                    reason = extractor.reporting.extractability_reason(sentence.text, tokens)
                    if reason is not None:
                        rejections[reason] += 1
                    else:
                        construction_delta = _counter_delta(
                            construction_before, extractor.constructions.rejection_counts
                        )
                        hybrid_delta = (
                            _counter_delta(hybrid_before, extractor.hybrid.rejection_counts)
                            if extractor.hybrid is not None
                            else {}
                        )
                        reasons = construction_delta or hybrid_delta
                        if reasons:
                            rejections[sorted(reasons)[0]] += 1
                        else:
                            rejections["no_tier_match"] += 1
            previous_text, previous_section = sentence.text, sentence.section_code

    counts: dict[str, object] = {
        "files": len(files),
        "licenses": len(licenses),
        "sentences_scanned": scanned,
        "sentences_kept": kept,
        "extractions": extracted,
        "distinct_frames": len(frames),
        "distinct_cluster_keys": len(keys),
        "frames_document_frequency_ge_2": sum(len(blobs) >= 2 for blobs in frames.values()),
        "articles": len(
            {articles.get(_key(path, blob_root), _key(path, blob_root)) for path in files}
        ),
        "canonical_frames": {
            tier: {
                "distinct": sum(key[0] == tier for key in canonical),
                "recurring_ge_2_articles": sum(
                    key[0] == tier and len(ids) >= 2 for key, ids in canonical.items()
                ),
            }
            for tier in sorted({key[0] for key in canonical})
        },
        "tiers": dict(sorted(tiers.items())),
        "families": dict(sorted(families.items())),
        "rejection_reasons": dict(sorted(rejections.items())),
        "hybrid_gate_rejections": extractor.hybrid.rejection_counts
        if extractor.hybrid is not None
        else {},
        "hybrid": hybrid,
        "model": nlp.info.model_name,
        "model_version": nlp.info.model_version,
        "spacy_version": nlp.info.spacy_version,
    }
    return sorted(manifests, key=lambda row: row["identity_sha256"]), counts


def _key(path: Path, blob_root: Path) -> str:
    return path.resolve().relative_to(blob_root.resolve()).as_posix()


def _counter_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    return {
        name: count - before.get(name, 0)
        for name, count in after.items()
        if count > before.get(name, 0)
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--blob-root", type=Path, required=True)
    rights = parser.add_mutually_exclusive_group(required=True)
    rights.add_argument("--database-url")
    rights.add_argument("--rights-file", type=Path)
    parser.add_argument("--article-ids", type=Path)
    parser.add_argument("--exclude-cluster-key", action="store_true")
    parser.add_argument("--model", default="en_core_web_sm")
    parser.add_argument("--hybrid", choices=("on", "off"), required=True)
    parser.add_argument("--output", type=Path, required=True, help="hash-only JSONL manifest")
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    if not args.directory.is_dir():
        parser.error("directory does not exist")
    try:
        manifest, counts = asyncio.run(
            _run(
                args.directory,
                args.blob_root,
                hybrid=args.hybrid == "on",
                model=args.model,
                database_url=args.database_url,
                rights_file=args.rights_file,
                article_ids=_article_ids(args.article_ids),
                exclude_cluster_key=args.exclude_cluster_key,
            )
        )
        if args.baseline is not None:
            baseline_rows = [
                json.loads(line)
                for line in args.baseline.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            baseline = {row["identity_sha256"]: row["output_sha256"] for row in baseline_rows}
            current_rows = [
                row for row in manifest if args.hybrid == "off" or row["tier"] == "tier1"
            ]
            current = {row["identity_sha256"]: row["output_sha256"] for row in current_rows}
            counts["baseline_differences"] = sum(
                baseline.get(identity) != value for identity, value in current.items()
            ) + len(baseline.keys() - current.keys())
        args.output.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in manifest),
            encoding="utf-8",
        )
        print(json.dumps(counts, sort_keys=True, indent=2))
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
