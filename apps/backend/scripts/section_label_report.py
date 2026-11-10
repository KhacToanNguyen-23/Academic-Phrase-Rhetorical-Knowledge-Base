"""Rights-checked aggregate section-label report. Never prints article body text."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml
from mining_trial_report import _spacy_section_analyser

from aprkb.modules.corpus.ingest import parse_and_analyze
from aprkb.modules.corpus.parsers import parser_for_key
from aprkb.modules.corpus.section_detector import _SUB_NUMBER, _TOP_NUMBER, SectionDetector
from aprkb.modules.corpus.sentence_splitter import split_sentences
from aprkb.modules.mining.pipeline import MiningPipeline
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.modules.mining.stages.sentence_filter import SentenceFilter
from aprkb.nlp import SentenceAnalysis, SpacyEngine
from aprkb.nlp.syntax import usable_tokens
from aprkb.policies.loader import load_policy_bundle
from aprkb.policies.schemas import SectionHeadingsPolicy


def _rights_check(files: list[Path], blob_root: Path, rights_file: Path) -> dict[str, str]:
    root = blob_root.resolve()
    keys: set[str] = set()
    for path in files:
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("corpus files must be inside the blob root")
        keys.add(resolved.relative_to(root).as_posix())
    authorized = dict(
        line.split("\t", 1)
        for line in rights_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    missing = keys - authorized.keys()
    if missing:
        raise ValueError(f"{len(missing)} corpus files lack a mining-allowed record")
    return {key: authorized[key] for key in keys}


def _article_ids(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    return {
        key: hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
        for key, value in (
            line.split("\t", 1) for line in path.read_text(encoding="utf-8").splitlines() if line
        )
    }


def _policy(path: Path | None) -> SectionHeadingsPolicy:
    if path is None:
        return load_policy_bundle().section_headings
    return SectionHeadingsPolicy.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _sentence_count(text: str) -> int:
    return len(split_sentences(text))


def _normal_heading(text: str | None) -> str:
    return " ".join((text or "").casefold().split()).rstrip(".: ")


def _unique_files(files: list[Path], blob_root: Path, id_map: dict[str, str]) -> list[Path]:
    representatives: dict[str, Path] = {}
    for path in files:
        key = path.resolve().relative_to(blob_root.resolve()).as_posix()
        article_id = id_map.get(key, key)
        representatives.setdefault(article_id, path)
    return sorted(representatives.values())


def _analyze(
    files: list[Path],
    blob_root: Path,
    rights_file: Path,
    id_map: dict[str, str],
    policy: SectionHeadingsPolicy,
    survey: dict[tuple[str, int], str] | None = None,
) -> dict[str, object]:
    # Rights are established for every selected blob before any blob is opened.
    _rights_check(files, blob_root, rights_file)
    files = _unique_files(files, blob_root, id_map)
    detector = SectionDetector(policy)
    inherit_policy = policy.model_copy(update={"formal_block_policy": "inherit"})
    inherit_detector = SectionDetector(inherit_policy)
    policy_bundle = load_policy_bundle()
    nlp = SpacyEngine("en_core_web_sm")
    stages = build_stages(policy_bundle=policy_bundle, hybrid_enabled=True)
    sentence_filter = next(stage for stage in stages if isinstance(stage, SentenceFilter))
    pipeline = MiningPipeline(stages=stages)
    article_codes: defaultdict[str, set[str]] = defaultdict(set)
    article_codes_inferred: defaultdict[str, set[str]] = defaultdict(set)
    source_counts: Counter[str] = Counter()
    total_sentences = unknown_sentences = inferred_sentences = 0
    pass_sentences = pass_unknown_heading = pass_unknown_inferred = 0
    formal_sentences: Counter[str] = Counter()
    formal_by_article: defaultdict[str, Counter[str]] = defaultdict(Counter)
    definition_sentences = definition_pass = definition_frames = 0
    inferred_sections = inferred_agree_sections = inferred_survey_sections = 0
    inferred_survey_sentences = inferred_agree_sentences = 0
    processed_inferred_sections: set[tuple[str, int]] = set()
    intro_bleed: set[str] = set()
    for path in files:
        blob_key = path.resolve().relative_to(blob_root.resolve()).as_posix()
        article_id = id_map.get(blob_key, blob_key)
        parser = parser_for_key(path.name)
        if parser is None:
            raise ValueError(f"no parser for corpus file extension {path.suffix}")
        prepared = parse_and_analyze(
            parser,
            path.read_bytes(),
            section_headings=policy,
            analyse_section=lambda text: _spacy_section_analyser(nlp, text),
        )
        parsed = prepared.parsed
        labels = detector.detect_with_provenance(parsed.sections)
        inherit_labels = inherit_detector.detect_with_provenance(parsed.sections)
        sections_by_order = {section.order: section for section in parsed.sections}
        by_order = {
            section.order: label for section, label in zip(parsed.sections, labels, strict=True)
        }
        inherit_by_order = {
            section.order: label
            for section, label in zip(parsed.sections, inherit_labels, strict=True)
        }
        explicit_appendix = any(
            _is_explicit_appendix_heading(section.heading, policy) for section in parsed.sections
        )
        formal_region = False
        existing_appendix_region = False
        for section, label, inherit_label in zip(
            parsed.sections, labels, inherit_labels, strict=True
        ):
            if section.heading:
                source_counts[label.source] += 1
            count = _sentence_count(section.text)
            total_sentences += count
            if label.code is None:
                unknown_sentences += count
                article_codes[article_id].add("UNKNOWN")
            else:
                article_codes[article_id].add(label.code)
            effective_code = label.inferred_code or label.code
            if effective_code is None:
                article_codes_inferred[article_id].add("UNKNOWN")
            else:
                article_codes_inferred[article_id].add(effective_code)
            if label.inferred_code is not None:
                inferred_sentences += count
            formal_heading = _formal_kind(section.heading, policy) is not None
            explicit_appendix_heading = _is_explicit_appendix_heading(section.heading, policy)
            lettered_appendix = bool(section.heading) and any(
                re.search(pattern, section.heading) for pattern in policy.appendix_patterns
            )
            if explicit_appendix_heading:
                existing_appendix_region = True
                formal_region = False
            elif label.code != "APPENDIX":
                formal_region = False
            elif not existing_appendix_region and (
                formal_heading or (lettered_appendix and not explicit_appendix)
            ):
                formal_region = True
            if label.code == "APPENDIX" and formal_region:
                formal_sentences[article_id] += count
                formal_by_article[article_id][section.heading or ""] += count
            if (
                _formal_kind(section.heading, policy) == "DEFINITION_ASSUMPTION"
                and inherit_label.code == "METHODS"
            ):
                definition_sentences += count
        seen_intro_heading = False
        seen_later_top_heading = False
        previous_text: str | None = None
        previous_section: str | None = None
        for sentence in prepared.sentences:
            section = sections_by_order[sentence.section_order]
            label = by_order[sentence.section_order]
            inherit_label = inherit_by_order[sentence.section_order]
            effective_code = label.inferred_code or label.code
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
                source_sentence_ids=[],
                section_code=sentence.section_code,
                char_start=sentence.char_start,
                previous_text=context,
                tokens=tokens,
            )
            passes = sentence_filter.reject_reason(item) is None
            if passes:
                pass_sentences += 1
                if label.code is None:
                    pass_unknown_heading += 1
                if effective_code is None:
                    pass_unknown_inferred += 1
            candidate_definition = (
                _formal_kind(section.heading, policy) == "DEFINITION_ASSUMPTION"
                and inherit_label.code == "METHODS"
            )
            candidate_item = MiningItem(
                text=sentence.text,
                source_sentence_ids=[],
                section_code="METHODS",
                char_start=sentence.char_start,
                previous_text=context,
                tokens=tokens,
            )
            if candidate_definition and sentence_filter.reject_reason(candidate_item) is None:
                definition_pass += 1
                if pipeline.process([candidate_item]):
                    definition_frames += 1
            section_key = (article_id, section.order)
            if (
                section_key not in processed_inferred_sections
                and label.source == "inferred"
                and label.inferred_code == "METHODS"
            ):
                processed_inferred_sections.add(section_key)
                section_sentence_count = _sentence_count(section.text)
                inferred_sections += 1
                survey_code = (survey or {}).get((Path(blob_key).stem, section.order))
                if survey_code is not None:
                    inferred_survey_sections += 1
                    inferred_survey_sentences += section_sentence_count
                    if survey_code == "METHODS":
                        inferred_agree_sections += 1
                        inferred_agree_sentences += section_sentence_count
            is_top = (
                bool(
                    section.heading
                    and _TOP_NUMBER.match(section.heading)
                    and not _SUB_NUMBER.match(section.heading)
                )
                or label.source == "heading"
            )
            if label.code == "INTRO" and label.source == "heading":
                seen_intro_heading = True
                seen_later_top_heading = False
            elif seen_intro_heading and is_top:
                seen_later_top_heading = True
            if seen_later_top_heading and label.code == "INTRO" and label.source == "inherited":
                intro_bleed.add(article_id)
    codes = [
        "ABSTRACT",
        "INTRO",
        "RELATED_WORK",
        "METHODS",
        "RESULTS",
        "DISCUSSION",
        "CONCLUSION",
        "UNKNOWN",
    ]
    return {
        "articles_per_code_heading_only": {
            code: sum(code in values for values in article_codes.values()) for code in codes
        },
        "articles_per_code_with_inferred": {
            code: sum(code in values for values in article_codes_inferred.values())
            for code in codes
        },
        "unknown_sentences_heading_only": unknown_sentences,
        "unknown_share_all_heading_only": unknown_sentences / total_sentences
        if total_sentences
        else 0.0,
        "unknown_share_all_with_inferred": (unknown_sentences - inferred_sentences)
        / total_sentences
        if total_sentences
        else 0.0,
        "unknown_share_mining_pass_heading_only": pass_unknown_heading / pass_sentences
        if pass_sentences
        else 0.0,
        "unknown_share_mining_pass_with_inferred": pass_unknown_inferred / pass_sentences
        if pass_sentences
        else 0.0,
        "all_sentences": total_sentences,
        "mining_filter_pass_sentences": pass_sentences,
        "inferred_sections": inferred_sections,
        "inferred_sentences": inferred_sentences,
        "inferred_methods_survey_agreement": (
            f"{inferred_agree_sections}/{inferred_survey_sections} sections; "
            f"{inferred_agree_sentences}/{inferred_survey_sentences} sentences"
        ),
        "definition_assumption_sentences": definition_sentences,
        "definition_assumption_mining_pass_sentences": definition_pass,
        "definition_assumption_mined_frames_lost_if_excluded": definition_frames,
        "formal_block_sentences_per_article": {
            key: dict(value) for key, value in sorted(formal_by_article.items())
        },
        "formal_block_sentences": dict(sorted(formal_sentences.items())),
        "intro_bleed_articles": len(intro_bleed),
        "heading_sources": dict(sorted(source_counts.items())),
        "articles": len(files),
    }


def _formal_kind(heading: str | None, policy: SectionHeadingsPolicy) -> str | None:
    if not heading:
        return None
    normalized = re.sub(r"^(?:[A-Z](?:\.\d+)*|\d+(?:\.\d+)*|[IVXLC]+)\.?\s+", "", heading)
    normalized = _normal_heading(normalized)
    for code, patterns in policy.formal_blocks.items():
        if any(re.search(pattern, normalized) for pattern in patterns):
            return code
    return None


def _is_explicit_appendix_heading(heading: str | None, policy: SectionHeadingsPolicy) -> bool:
    if not heading:
        return False
    normalized = re.sub(r"^(?:[A-Z]|\d+(?:\.\d+)*|[IVXLC]+)\.?\s+", "", heading)
    return any(
        re.search(pattern, _normal_heading(normalized))
        for pattern in policy.non_rhetorical.get("APPENDIX", [])
    )


def _survey(path: Path | None) -> dict[tuple[str, int], str]:
    if path is None:
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assignments: dict[tuple[str, int], str] = {}
    for article_id, rows in payload["articles"].items():
        for row in rows:
            code = row.get("true_code")
            if code:
                assignments[(article_id, int(row["section_order"]))] = str(code)
    return assignments


def _evaluate_gold(
    gold_path: Path,
    files: list[Path],
    blob_root: Path,
    rights_file: Path,
    id_map: dict[str, str],
    policy: SectionHeadingsPolicy,
) -> dict[str, object]:
    gold_doc = yaml.safe_load(gold_path.read_text(encoding="utf-8"))
    gold_by_id = {str(item["article_id"]): item["headings"] for item in gold_doc["articles"]}
    _rights_check(files, blob_root, rights_file)
    files = _unique_files(files, blob_root, id_map)
    matched = heading_correct = sentence_total = sentence_correct = 0
    matrix: Counter[tuple[str, str]] = Counter()
    detector = SectionDetector(policy)
    for path in files:
        key = path.resolve().relative_to(blob_root.resolve()).as_posix()
        article_id = id_map.get(key, key)
        if article_id not in gold_by_id:
            continue
        parser = parser_for_key(path.name)
        if parser is None:
            continue
        parsed = parser.parse(path.read_bytes())
        predicted = detector.detect_with_provenance(parsed.sections)
        expected = {_normal_heading(row["heading"]): row["code"] for row in gold_by_id[article_id]}
        for section, label in zip(parsed.sections, predicted, strict=True):
            heading_key = _normal_heading(section.heading)
            if heading_key not in expected:
                continue
            gold_code = expected[heading_key]
            matched += 1
            predicted_code = label.code or "UNKNOWN"
            heading_correct += predicted_code == gold_code
            weight = _sentence_count(section.text)
            sentence_total += weight
            sentence_correct += weight * (predicted_code == gold_code)
            matrix[(gold_code, predicted_code)] += 1
    return {
        "matched_gold_headings": matched,
        "heading_accuracy": heading_correct / matched if matched else 0.0,
        "sentence_weighted_accuracy": sentence_correct / sentence_total if sentence_total else 0.0,
        "confusion_matrix": {
            gold: dict(
                sorted((pred, count) for (truth, pred), count in matrix.items() if truth == gold)
            )
            for gold in sorted({truth for truth, _ in matrix})
        },
    }


def _print_reports(reports: list[tuple[str, dict[str, object], dict[str, object] | None]]) -> None:
    columns = [label for label, _, _ in reports]
    print("measure\t" + "\t".join(columns))
    names = list(reports[0][1])
    if reports[0][2] is not None:
        names.extend(reports[0][2])
    for name in names:
        values = []
        for _, result, evaluation in reports:
            value = result.get(name) if name in result else (evaluation or {}).get(name)
            values.append(str(value))
        print(name + "\t" + "\t".join(values))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--blob-root", type=Path, required=True)
    parser.add_argument("--rights-file", type=Path, required=True)
    parser.add_argument("--article-ids", type=Path)
    parser.add_argument("--gold", type=Path)
    parser.add_argument("--survey-assignments", type=Path)
    parser.add_argument(
        "--policy", type=Path, help="candidate policy; compare against the current policy"
    )
    args = parser.parse_args()
    if not args.directory.is_dir():
        parser.error("directory does not exist")
    try:
        files = sorted(
            path
            for path in args.directory.rglob("*")
            if path.is_file() and path.suffix.casefold() in {".md", ".txt"}
        )
        ids = _article_ids(args.article_ids)
        survey = _survey(args.survey_assignments)
        current = load_policy_bundle().section_headings
        policies = [("current", current)]
        if args.policy is not None:
            policies.append(("candidate", _policy(args.policy)))
        reports = []
        for label, policy in policies:
            result = _analyze(files, args.blob_root, args.rights_file, ids, policy, survey)
            evaluation = (
                _evaluate_gold(args.gold, files, args.blob_root, args.rights_file, ids, policy)
                if args.gold
                else None
            )
            reports.append((label, result, evaluation))
        _print_reports(reports)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
