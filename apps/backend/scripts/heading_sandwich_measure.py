"""Produce aggregate, rights-checked heading, sandwich and read-filter measurements."""

# ruff: noqa: E501

from __future__ import annotations

import argparse
import hashlib
import re
import string
from collections import Counter, defaultdict
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from mining_trial_report import _spacy_section_analyser

from aprkb.modules.corpus.parsers import parser_for_key
from aprkb.modules.corpus.section_detector import _SUB_NUMBER, SectionDetector, SectionLabel
from aprkb.modules.corpus.sentence_splitter import split_sentences
from aprkb.modules.mining.frame_sections import summarize_frame_sections
from aprkb.modules.mining.pipeline import MiningPipeline
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.modules.mining.stages.sentence_filter import SentenceFilter
from aprkb.nlp import SentenceAnalysis, SpacyEngine
from aprkb.nlp.syntax import usable_tokens
from aprkb.policies.loader import load_policy_bundle
from aprkb.policies.schemas import SectionHeadingsPolicy


def _files(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}
    )


def _rights(files: list[Path], root: Path, rights_file: Path) -> None:
    root = root.resolve()
    keys = {path.resolve().relative_to(root).as_posix() for path in files}
    authorized = {
        line.split("\t", 1)[0]
        for line in rights_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    if keys - authorized:
        raise ValueError(f"{len(keys - authorized)} corpus blobs lack a mining-allowed record")


def _article_map(path: Path) -> dict[str, str]:
    return {
        key: hashlib.sha256(title.encode("utf-8")).hexdigest()[:16]
        for key, title in (
            line.split("\t", 1) for line in path.read_text(encoding="utf-8").splitlines() if line
        )
    }


def _unique_articles(files: list[Path], root: Path, article_ids: dict[str, str]) -> list[Path]:
    representatives: dict[str, Path] = {}
    for path in files:
        key = path.resolve().relative_to(root.resolve()).as_posix()
        representatives.setdefault(article_ids.get(key, key), path)
    return sorted(representatives.values())


def _heading_key(value: str | None) -> str:
    return " ".join((value or "").casefold().split()).rstrip(".: ")


def _frame_key(output: MiningItem) -> str:
    """Use the clusterer's stored identity; normalize only when no key exists."""
    if output.cluster_key:
        return output.cluster_key
    normalized = re.sub(r"\s+", " ", output.canonical_skeleton or output.text)
    return normalized.casefold().rstrip(string.punctuation + string.whitespace)


def _part1_effects(
    files: list[Path], policy: SectionHeadingsPolicy
) -> tuple[dict[str, int], dict[str, list[str]], dict[str, int]]:
    additions = {
        "numerical results": "RESULTS",
        "summary and outlook": "CONCLUSION",
        "artifact appendix": "APPENDIX",
        "reproducibility statement": "BACK_MATTER",
        "checklist": "APPENDIX",
    }
    counts: Counter[str] = Counter()
    headings: defaultdict[str, set[str]] = defaultdict(set)
    article_counts: Counter[str] = Counter()
    detector = SectionDetector(policy)
    pattern = re.compile(
        r"^\s*(numerical results|summary and outlook|artifact appendix|"
        r"reproducibility statement|checklist)",
        re.I,
    )
    for path in files:
        parser = parser_for_key(path.name)
        parsed = parser.parse(path.read_bytes()) if parser else None
        if parsed is None:
            continue
        labels = detector.detect_with_provenance(parsed.sections)
        for section, label in zip(parsed.sections, labels, strict=True):
            match = pattern.match(_heading_key(section.heading))
            if match is None:
                continue
            keyword = match.group(1).casefold()
            code = additions[keyword]
            headings[keyword].add(section.heading or "")
            if label.code == code and label.source == "heading":
                counts[keyword] += len(split_sentences(section.text))
                article_counts[keyword] += 1
    return (
        dict(counts),
        {key: sorted(value) for key, value in headings.items()},
        dict(article_counts),
    )


def _validation(files: list[Path], policy: SectionHeadingsPolicy):
    correct: Counter[str] = Counter()
    predicted: Counter[str] = Counter()
    cases: list[tuple[str, str, str]] = []
    headings_total: Counter[str] = Counter()
    detector = SectionDetector(policy)
    for path in files:
        parser = parser_for_key(path.name)
        parsed = parser.parse(path.read_bytes()) if parser else None
        if parsed is None:
            continue
        gold = detector.detect_with_provenance(parsed.sections)
        top = [
            i
            for i, section in enumerate(parsed.sections)
            if section.heading and not _SUB_NUMBER.match(section.heading)
        ]
        for index in top:
            expected = gold[index]
            if expected.source != "heading" or expected.code is None:
                continue
            headings_total[expected.code] += 1
            if expected.code not in {
                "INTRO",
                "RELATED_WORK",
                "RESULTS",
                "DISCUSSION",
                "CONCLUSION",
            }:
                continue
            hidden = list(gold)
            hidden[index] = SectionLabel(None, expected.secondary_code, "none")
            result = hidden
            # Apply the rule to the withheld labels without changing other headings.
            from aprkb.modules.corpus.section_detector import _apply_sandwich

            result = _apply_sandwich(parsed.sections, result)
            got = result[index]
            if got.source == "sandwich" and got.code is not None:
                predicted[expected.code] += 1
                if got.code == expected.code:
                    correct[expected.code] += 1
                else:
                    cases.append((parsed.sections[index].heading or "", expected.code, got.code))
    return {
        "correct": dict(correct),
        "predicted": dict(predicted),
        "headings_total": dict(headings_total),
        "wrong": sorted(set(cases)),
    }


def _measure(
    files: list[Path],
    root: Path,
    article_ids: dict[str, str],
    policy: SectionHeadingsPolicy,
    model: str,
) -> dict[str, object]:
    policies = load_policy_bundle()
    nlp = SpacyEngine(model)
    stages = build_stages(policy_bundle=policies, hybrid_enabled=True)
    sentence_filter = next(stage for stage in stages if isinstance(stage, SentenceFilter))
    pipeline = MiningPipeline(stages=stages)
    detector = SectionDetector(policy)
    shares: defaultdict[str, set[str]] = defaultdict(set)
    rows: Counter[str] = Counter()
    row_tiers: Counter[tuple[str, str]] = Counter()
    frame_texts: dict[str, str] = {}
    frame_sources: defaultdict[str, list[tuple[str, str | None]]] = defaultdict(list)
    frame_sections: defaultdict[str, set[tuple[str, int]]] = defaultdict(set)
    raw_shares: defaultdict[str, set[str]] = defaultdict(set)
    raw_rows: Counter[str] = Counter()
    raw_unknown_sources: defaultdict[str, list[tuple[str, str | None]]] = defaultdict(list)
    total = pass_total = unknown_total = unknown_pass = 0
    sandwich_section_sentences: Counter[str] = Counter()
    sandwich_sections: Counter[str] = Counter()
    sandwich_pass_sentences: Counter[str] = Counter()
    sandwich_articles: defaultdict[str, set[str]] = defaultdict(set)
    sandwich_frames: defaultdict[str, set[str]] = defaultdict(set)
    sandwich_frame_articles: defaultdict[str, defaultdict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    sandwich_frame_rows: Counter[str] = Counter()
    default_frames: defaultdict[str, set[str]] = defaultdict(set)

    for path in files:
        blob_key = path.resolve().relative_to(root.resolve()).as_posix()
        article_id = article_ids.get(blob_key, blob_key)
        parser = parser_for_key(path.name)
        if parser is None:
            raise ValueError(f"no parser for {path.suffix}")
        parsed = parser.parse(path.read_bytes())
        labels = detector.detect_with_provenance(parsed.sections)
        sandwich_labels = detector.detect_with_provenance(parsed.sections, apply_sandwich=True)
        changed = {
            i
            for i, (a, b) in enumerate(zip(labels, sandwich_labels, strict=True))
            if b.source == "sandwich"
        }
        for index in tuple(changed):
            for child in range(index + 1, len(parsed.sections)):
                heading = parsed.sections[child].heading or ""
                if heading and not _SUB_NUMBER.match(heading):
                    break
                if _SUB_NUMBER.match(heading):
                    changed.add(child)
        previous_text: str | None = None
        previous_section: str | None = None
        for section_index, section in enumerate(parsed.sections):
            label = labels[section_index]
            alt_label = sandwich_labels[section_index]
            measured_sentence_count = len(split_sentences(section.text))
            total += measured_sentence_count
            if label.code is None:
                unknown_total += measured_sentence_count
            if section_index in changed:
                code = alt_label.code or "UNKNOWN"
                sandwich_section_sentences[code] += measured_sentence_count
                sandwich_sections[code] += 1
                sandwich_articles[code].add(article_id)
            features = _spacy_section_analyser(nlp, section.text)
            for sentence_text, start, _end, feature_json, _source in features:
                code = label.code
                item_code = code
                tokens = (
                    usable_tokens(SentenceAnalysis.from_json(feature_json))
                    if feature_json
                    else None
                )
                context = previous_text if code is not None and code == previous_section else None
                item = MiningItem(
                    text=sentence_text,
                    source_sentence_ids=[
                        uuid5(NAMESPACE_URL, f"{blob_key}:{section.order}:{start}")
                    ],
                    section_code=item_code,
                    char_start=section.char_start + start,
                    previous_text=context,
                    tokens=tokens,
                )
                accepted = sentence_filter.reject_reason(item) is None
                if accepted:
                    pass_total += 1
                    if code is None:
                        unknown_pass += 1
                        if section_index in changed:
                            sandwich_pass_sentences[alt_label.code or "UNKNOWN"] += 1
                    result = pipeline.process([item])
                    if result:
                        output = result[0]
                        frame = _frame_key(output)
                        raw_frame = output.text
                        frame_texts.setdefault(frame, output.text)
                        tier = (
                            "tier2"
                            if (output.construction_id or "").startswith("hybrid_")
                            else "tier1"
                        )
                        rows[frame] += 1
                        row_tiers[(frame, tier)] += 1
                        shares[frame].add(article_id)
                        default_frames[frame].add(article_id)
                        frame_sources[frame].append((article_id, code))
                        frame_sections[frame].add((article_id, section.order))
                        raw_rows[raw_frame] += 1
                        raw_shares[raw_frame].add(article_id)
                        raw_unknown_sources[raw_frame].append((article_id, code))
                        if section_index in changed:
                            code = alt_label.code or "UNKNOWN"
                            sandwich_frames[code].add(frame)
                            sandwich_frame_articles[code][frame].add(article_id)
                            sandwich_frame_rows[frame] += 1
                previous_text, previous_section = sentence_text, code

    threshold = policies.mining_filter.frame_section_dominant_share_threshold
    distributions = {
        frame: summarize_frame_sections(sources, dominant_share_threshold=threshold)
        for frame, sources in frame_sources.items()
    }
    raw_distributions = {
        frame: summarize_frame_sections(sources, dominant_share_threshold=threshold)
        for frame, sources in raw_unknown_sources.items()
    }
    unknown_frame_names = {frame for frame, dist in distributions.items() if dist.is_unknown}
    dropped = {
        frame for frame, dist in distributions.items() if dist.is_unknown and dist.paper_count == 1
    }
    dropped_rows = sum(rows[frame] for frame in dropped)
    all_shared = sum(len(papers) >= 2 for papers in shares.values())
    after_frames = len(shares) - len(dropped)
    raw_dropped = {
        frame
        for frame, dist in raw_distributions.items()
        if dist.is_unknown and dist.paper_count == 1
    }
    dominant_counts = Counter(dist.dominant_code for dist in distributions.values())
    distribution_counts = Counter(
        "UNKNOWN" if dist.is_unknown else dist.dominant_code for dist in distributions.values()
    )
    return {
        "sentences": total,
        "mining_pass": pass_total,
        "unknown_sentences": unknown_total,
        "unknown_pass": unknown_pass,
        "sandwich_sentences": dict(sandwich_section_sentences),
        "sandwich_sections": dict(sandwich_sections),
        "sandwich_articles_touched": len(
            {article for article_ids in sandwich_articles.values() for article in article_ids}
        ),
        "sandwich_pass_sentences": dict(sandwich_pass_sentences),
        "sandwich_articles": {code: len(ids) for code, ids in sandwich_articles.items()},
        "sandwich_frames": {code: len(frames) for code, frames in sandwich_frames.items()},
        "sandwich_shared_frames": {
            code: sum(len(sandwich_frame_articles[code][frame]) >= 2 for frame in frames)
            for code, frames in sandwich_frames.items()
        },
        "distinct_frames": len(shares),
        "extracted_rows": sum(rows.values()),
        "raw_distinct_frames": len(raw_shares),
        "raw_dropped_frames": len(raw_dropped),
        "raw_shared_frames": sum(len(papers) >= 2 for papers in raw_shares.values()),
        "unknown_frames": len(unknown_frame_names),
        "known_distribution_frames": sum(not dist.is_unknown for dist in distributions.values()),
        "mixed_frames": sum(dist.dominant_code == "MIXED" for dist in distributions.values()),
        "unknown_frames_by_distribution": sum(dist.is_unknown for dist in distributions.values()),
        "dominant_code_counts": dict(sorted(dominant_counts.items())),
        "distribution_counts": dict(sorted(distribution_counts.items())),
        "multi_section_frames": sum(len(sections) >= 2 for sections in frame_sections.values()),
        "tier_rows": {
            tier: sum(count for (frame, row_tier), count in row_tiers.items() if row_tier == tier)
            for tier in ("tier1", "tier2")
        },
        "dropped_frames": len(dropped),
        "dropped_rows": dropped_rows,
        "unknown_frame_drop_share": len(dropped) / len(unknown_frame_names)
        if unknown_frame_names
        else 0.0,
        "kept_frames": after_frames,
        "shared_before": all_shared,
        "shared_after": sum(
            len(papers) >= 2 for frame, papers in shares.items() if frame not in dropped
        ),
        "dropped_tier_rows": {
            tier: sum(row_tiers[(frame, tier)] for frame in dropped) for tier in ("tier1", "tier2")
        },
        "dropped_samples": [
            frame_texts[frame]
            for frame in sorted(dropped, key=lambda key: (-rows[key], frame_texts[key].casefold()))[
                :15
            ]
        ],
        "dropped_sample_rows": {
            frame_texts[frame]: rows[frame]
            for frame in sorted(dropped, key=lambda key: (-rows[key], frame_texts[key].casefold()))[
                :15
            ]
        },
        "sandwich_frame_samples": {
            code: sorted(frames)[:10] for code, frames in sandwich_frames.items()
        },
        "spacy_version": nlp.info.spacy_version,
        "model_version": nlp.info.model_version,
    }


def _write_report(path: Path, part1, validation, measure) -> None:
    lines = [
        "# Heading keywords, sandwich measurement, and single paper UNKNOWN frame filter",
        "",
        "Rights checked before corpus reads. The corpus was deduplicated from 51 blobs to 50 articles. "
        "No article sentences are included; the only text samples below are section headings and slot-abstracted frames.",
        "",
        "## UNKNOWN share",
        "",
        f"- After Part 1 heading labels: {measure['unknown_sentences']}/{measure['sentences']} all sentences "
        f"({measure['unknown_sentences'] / measure['sentences']:.2%}); mining-filter passes "
        f"{measure['unknown_pass']}/{measure['mining_pass']} ({measure['unknown_pass'] / measure['mining_pass']:.2%}).",
        f"- With the measured sandwich assignments applied hypothetically: "
        f"{measure['unknown_sentences'] - sum(measure['sandwich_sentences'].values())}/{measure['sentences']} "
        f"({(measure['unknown_sentences'] - sum(measure['sandwich_sentences'].values())) / measure['sentences']:.2%}) "
        f"all sentences; {measure['unknown_pass'] - sum(measure['sandwich_pass_sentences'].values())}/"
        f"{measure['mining_pass']} ({(measure['unknown_pass'] - sum(measure['sandwich_pass_sentences'].values())) / measure['mining_pass']:.2%}) "
        "mining-filter passes.",
        "- Phase 1b before this task (heading labels): 5,143/28,303 (18.17%) all sentences; "
        "4,223/11,509 (36.69%) mining-filter passes.",
        "",
        "## Part 1: new keywords",
        "",
        "Counts below are sentences in sections newly assigned the intended heading code. A section-heading match is not an independent gold label; no objective corpus mislabel can be established without reviewed expected codes.",
        "",
        "| Prefix | Intended code | Newly labeled sentences | Heading text observed |",
        "|---|---|---:|---|",
    ]
    counts, headings, _articles = part1
    for keyword, code in (
        ("numerical results", "RESULTS"),
        ("summary and outlook", "CONCLUSION"),
        ("artifact appendix", "APPENDIX"),
        ("reproducibility statement", "BACK_MATTER"),
        ("checklist", "APPENDIX"),
    ):
        observed = "; ".join(headings.get(keyword, [])) or "none"
        lines.append(f"| `{keyword}` | {code} | {counts.get(keyword, 0)} | {observed} |")
    lines += [
        "",
        "Potential mislabels found by the available evidence: none independently verifiable (no reviewed gold headings). "
        "The strict start-prefix rule avoids matches when a keyword occurs later in a heading.",
        "",
        "## Part 2: sandwich rule, measured only",
        "",
        "Validation hides each heading-sourced top-level label in turn, then predicts from its nearest remaining heading-sourced neighbours. "
        "Subheadings inherit a measured sandwich assignment. Formal blocks and non-rhetorical codes cannot be assigned.",
        "",
        "| Code | Correct / predicted | Precision |",
        "|---|---:|---:|",
    ]
    correct = validation["correct"]
    predicted = validation["predicted"]
    totals = sorted(
        set(correct)
        | set(predicted)
        | {"INTRO", "RELATED_WORK", "RESULTS", "DISCUSSION", "CONCLUSION"}
    )
    total_correct = total_predicted = 0
    for code in totals:
        c, p = correct.get(code, 0), predicted.get(code, 0)
        total_correct += c
        total_predicted += p
        precision = f"{c / p:.2%}" if p else "n/a (no predictions)"
        lines.append(f"| {code} | {c} / {p} | {precision} |")
    overall = total_correct / total_predicted if total_predicted else 0
    lines.append(f"| **Overall** | **{total_correct} / {total_predicted}** | **{overall:.2%}** |")
    lines += [
        "",
        f"Precision target >=95% reached: **{'yes' if overall >= 0.95 else 'no'}**.",
        "",
        "Wrong validation cases (heading text only):",
    ]
    if validation["wrong"]:
        for heading, expected, got in validation["wrong"]:
            lines.append(f"- `{heading}`: expected {expected}, predicted {got}.")
    else:
        lines.append("- None.")
    lines += [
        "",
        "Corpus measurement (hybrid on; default section labels): "
        f"{sum(measure['sandwich_sentences'].values())} UNKNOWN sentences relabeled across "
        f"{sum(measure['sandwich_sections'].values())} sections in "
        f"{measure['sandwich_articles_touched']} articles.",
        "",
        "Frames mined in relabeled sections (frame text only):",
    ]
    for code, frames in sorted(measure["sandwich_frame_samples"].items()):
        lines.append(
            f"- {code}: {measure['sandwich_frames'][code]} frames; "
            f"{measure['sandwich_sentences'].get(code, 0)} sentences; "
            f"{measure['sandwich_articles'].get(code, 0)} articles; "
            f"{measure['sandwich_sections'].get(code, 0)} sections; "
            f"{measure['sandwich_shared_frames'].get(code, 0)} frames in 2+ articles; samples: "
            + ("; ".join(f"`{frame}`" for frame in frames) or "none")
        )
    lines += [
        "",
        "Recommendation: keep the sandwich rule disabled unless the overall held-out precision reaches 95%. "
        f"Measured overall precision is {overall:.2%}.",
        "",
        "## Part 3: single-paper UNKNOWN frame read filter",
        "",
        "The existing `/extraction/phrases` read path is implemented in `modules/extraction/service.py:list_phrases`. "
        "It reads licensed source article IDs and section codes using `repository.candidate_section_sources`, "
        "exposes the distribution, and applies `unknown_single_paper_reason()` under "
        "`mining_filter.unknown_single_paper_filter`. The reason counts are returned in "
        "`PhrasePage.filtered_reason_counts`. No extraction, stored candidate, or database row is changed.",
        "",
        f"- Previous raw-output.text grouping: {measure['raw_distinct_frames']} distinct, "
        f"{measure['raw_dropped_frames']} UNKNOWN single-paper dropped, {measure['raw_shared_frames']} shared by 2+. "
        "Earlier report baseline: 1,573 / 474 / 145, respectively.",
        f"- Corrected `cluster_key` grouping: {measure['distinct_frames']} distinct frames; UNKNOWN frames: {measure['unknown_frames']}; dropped: {measure['dropped_frames']} "
        f"({measure['unknown_frame_drop_share']:.2%} of UNKNOWN frames); kept overall: {measure['kept_frames']}.",
        f"- Extracted rows: {measure['extracted_rows']}; rows dropped: {measure['dropped_rows']}; distinct frames after: {measure['kept_frames']} "
        f"(from {measure['distinct_frames']}); frames in 2+ articles: {measure['shared_before']} before, "
        f"{measure['shared_after']} after.",
        f"- Frames with known sources: {measure['known_distribution_frames']}; MIXED: {measure['mixed_frames']}; "
        f"UNKNOWN: {measure['unknown_frames_by_distribution']}; spanning 2+ source sections: {measure['multi_section_frames']}.",
        "- Dominant/distribution code counts: "
        + ", ".join(f"{code} {count}" for code, count in measure["distribution_counts"].items())
        + ".",
        f"- Total extracted rows: Tier 1 {measure['tier_rows']['tier1']}, Tier 2 {measure['tier_rows']['tier2']}; "
        f"after filtering: Tier 1 {measure['tier_rows']['tier1'] - measure['dropped_tier_rows']['tier1']}, "
        f"Tier 2 {measure['tier_rows']['tier2'] - measure['dropped_tier_rows']['tier2']}.",
        f"- Dropped rows by tier: Tier 1 {measure['dropped_tier_rows']['tier1']}; "
        f"Tier 2 {measure['dropped_tier_rows']['tier2']}.",
        "",
        "15 dropped frame samples (slot-abstracted text only; includes fewer if fewer than 15 qualify):",
    ]
    for frame in measure["dropped_samples"]:
        lines.append(f"- `{frame}` ({measure['dropped_sample_rows'][frame]} rows)")
    lines += [
        "",
        f"Run environment: spaCy {measure['spacy_version']}, model {measure['model_version']}; hybrid enabled.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--blob-root", type=Path, required=True)
    parser.add_argument("--rights-file", type=Path, required=True)
    parser.add_argument("--article-ids", type=Path, required=True)
    parser.add_argument("--model", default="en_core_web_sm")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    files = _files(args.directory)
    _rights(files, args.blob_root, args.rights_file)
    article_ids = _article_map(args.article_ids)
    files = _unique_articles(files, args.blob_root, article_ids)
    policy = load_policy_bundle().section_headings
    part1 = _part1_effects(files, policy)
    validation = _validation(files, policy)
    measure = _measure(files, args.blob_root, article_ids, policy, args.model)
    _write_report(args.report, part1, validation, measure)


if __name__ == "__main__":
    main()
