"""TODO(owner, FR-06.2): spike only; not wired into ingest or mining.

Compare the existing splitter with spaCy on self-authored spike fixtures.
Run from ``apps/backend`` with the backend environment active.
"""

from __future__ import annotations

import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from aprkb.modules.corpus.sentence_splitter import split_sentences
from aprkb.modules.mining.stages.slot_abstractor import SlotAbstractor
from aprkb.nlp import SpacyEngine
from aprkb.policies.loader import load_policy_bundle

FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "nlp_spike" / "sentences.yaml"


@dataclass
class Config:
    name: str
    engine: SpacyEngine | None = None
    load_ms: float | None = None
    error: str | None = None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    with FIXTURE.open(encoding="utf-8") as fixture:
        payload = yaml.safe_load(fixture)
    cases: list[dict[str, Any]] = payload["cases"]
    slot_cases: list[str] = payload["slot_cases"]
    configs = [
        Config("regex splitter"),
        _load_config("en_core_web_sm (shared rules, no guard)", "en_core_web_sm", False),
        _load_config("en_core_web_sm (shared rules, guard)", "en_core_web_sm", True),
    ]
    print("# spaCy NLP spike comparison")
    print()
    print("Self-authored fixtures only; no article corpus text is used.")
    print()
    print("## Versions and model load")
    print()
    print("| Config | Model | spaCy | Model version | Components | Load ms | Status |")
    print("|---|---|---|---|---|---:|---|")
    for config in configs:
        if config.name == "regex splitter":
            print(f"| {config.name} | - | - | - | - | - | baseline |")
            continue
        if config.engine is None:
            print(f"| {config.name} | - | - | - | - | - | {config.error} |")
            continue
        info = config.engine.info
        print(
            f"| {config.name} | {info.model_name} | {info.spacy_version} | "
            f"{info.model_version} | {', '.join(info.components)} | {config.load_ms:.2f} | loaded |"
        )
    print()
    print("## Sentence splitting")
    print()
    print("| Config | Exact cases | Total cases |")
    print("|---|---:|---:|")
    for config in configs:
        matches, _ = _split_results(config, cases)
        print(f"| {config.name} | {matches} | {len(cases)} |")
    print()
    for config in configs:
        _, failures = _split_results(config, cases)
        print(f"### {config.name} failures")
        print()
        if not failures:
            print("None.")
        else:
            print("| Case | Expected | Actual |")
            print("|---:|---|---|")
            for index, expected, actual in failures:
                print(f"| {index} | {_md(expected)} | {_md(actual)} |")
        print()
    print("## Syntax probe: slot cases")
    print()
    abstractor = SlotAbstractor(
        load_policy_bundle().reporting_verbs, load_policy_bundle().slot_abstraction
    )
    for index, text in enumerate(slot_cases, start=1):
        regex_match = abstractor._reporting_match(text)
        regex_surface = regex_match[4] if regex_match else "—"
        regex_reason = abstractor.extractability_reason(text) or "extractable"
        print(f"### Case {index}: {text}")
        print()
        print(f"Current regex: reason=`{regex_reason}`, matched verb=`{regex_surface}`")
        print()
        print("| Config | ROOT verb + tense | nsubj subtree | ccomp with mark=that |")
        print("|---|---|---|---|")
        for config in configs:
            if config.engine is None:
                print(f"| {config.name} | unavailable | unavailable | unavailable |")
                continue
            root, subject, complement = _syntax_probe(config.engine, text)
            print(f"| {config.name} | {root} | {subject} | {complement} |")
        print()
    print("## Performance")
    print()
    for config in configs:
        if config.name == "regex splitter":
            print(f"- {config.name}: {_regex_performance(cases)}")
            continue
        if config.engine is None:
            print(f"- {config.name}: unavailable ({config.error}).")
            continue
        print(f"- {config.name}: {_performance(config.engine, cases)}")
    print()


def _load_config(name: str, model_name: str, abbreviation_guard: bool) -> Config:
    started = time.perf_counter()
    try:
        del abbreviation_guard
        engine = SpacyEngine(model_name)
    except Exception as error:  # pragma: no cover - depends on optional installed models
        return Config(name, error=f"not available: {type(error).__name__}: {error}")
    return Config(name, engine=engine, load_ms=(time.perf_counter() - started) * 1000)


def _split_results(
    config: Config, cases: list[dict[str, Any]]
) -> tuple[int, list[tuple[int, list[str], list[str]]]]:
    failures: list[tuple[int, list[str], list[str]]] = []
    matches = 0
    for index, case in enumerate(cases, start=1):
        expected = case["expected"]
        if config.name == "regex splitter":
            actual = [span.text for span in split_sentences(case["text"])]
        elif config.engine is None:
            actual = [config.error or "unavailable"]
        else:
            actual = [
                analysis.to_sentence_span(case["text"]).text
                for analysis in config.engine.analyze(case["text"])
            ]
        if actual == expected:
            matches += 1
        else:
            failures.append((index, expected, actual))
    return matches, failures


def _syntax_probe(engine: SpacyEngine, text: str) -> tuple[str, str, str]:
    doc = engine._nlp(text)
    root = next((token for token in doc if token.dep_ == "ROOT"), None)
    root_value = "—" if root is None else f"{root.text} ({root.morph})"
    subject_kind, subject_value, complement_value, has_that_mark = _syntax_spans(doc, doc.text)
    if subject_kind:
        subject_value = f"{subject_kind}: {subject_value}"
    if has_that_mark:
        complement_value += " [mark=that]"
    return root_value, subject_value, complement_value


def _syntax_spans(doc: Any, source: str) -> tuple[str, str, str, bool]:
    """Return direct-ROOT subject and ccomp spans for the syntax probe."""
    root = next((token for token in doc if token.dep_ == "ROOT"), None)
    if root is None:
        return "", "-", "-", False
    subject = next(
        (token for token in root.children if token.dep_ in {"nsubjpass", "nsubj", "expl"}),
        None,
    )
    subject_kind = subject.dep_ if subject is not None else ""
    subject_value = _single_subtree_text(subject, source) if subject is not None else "-"
    complement = next((token for token in root.children if token.dep_ == "ccomp"), None)
    complement_value = _single_subtree_text(complement, source) if complement else "-"
    has_that_mark = bool(
        complement
        and any(
            child.dep_ == "mark" and child.text.casefold() == "that"
            for child in complement.children
        )
    )
    return subject_kind, subject_value, complement_value, has_that_mark


def _single_subtree_text(token: Any, source: str) -> str:
    start = token.left_edge.idx
    end = token.right_edge.idx + len(token.right_edge.text)
    return source[start:end].rstrip(".,!?;:").replace("|", "\\|")


def _performance(engine: SpacyEngine, cases: list[dict[str, Any]]) -> str:
    texts = [case["text"] for case in cases]
    repeats = math.ceil(5000 / len(cases))
    repeated = texts * repeats
    timings: list[float] = []
    parsed_sentences = 0
    for _ in range(3):
        started = time.perf_counter()
        parsed_sentences = sum(len(batch) for batch in engine.analyze_many(repeated))
        timings.append(time.perf_counter() - started)
    average_ms = sum(timings) / len(timings) * 1000
    return (
        f"{parsed_sentences} sentences across {len(repeated)} inputs; "
        f"average {average_ms / parsed_sentences * 1000:.2f} ms per 1,000 sentences "
        f"(three runs)"
    )


def _regex_performance(cases: list[dict[str, Any]]) -> str:
    texts = [case["text"] for case in cases]
    repeats = math.ceil(5000 / len(cases))
    repeated = texts * repeats
    timings: list[float] = []
    parsed_sentences = 0
    for _ in range(3):
        started = time.perf_counter()
        parsed_sentences = sum(len(split_sentences(text)) for text in repeated)
        timings.append(time.perf_counter() - started)
    average_ms = sum(timings) / len(timings) * 1000
    return (
        f"{parsed_sentences} sentences across {len(repeated)} inputs; "
        f"average {average_ms / parsed_sentences * 1000:.2f} ms per 1,000 sentences "
        f"(three runs)"
    )


def _md(values: list[str]) -> str:
    return "<br>".join(value.replace("|", "\\|").replace("\n", "<br>") for value in values)


if __name__ == "__main__":
    main()
