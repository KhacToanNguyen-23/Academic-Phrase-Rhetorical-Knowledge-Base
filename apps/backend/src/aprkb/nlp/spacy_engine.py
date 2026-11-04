"""TODO(owner, FR-06.2): spike only; not wired into ingest or mining."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from typing import Any

from aprkb.nlp.features import (
    FEATURES_SCHEMA_VERSION,
    NlpEngineInfo,
    SentenceAnalysis,
    TokenFeature,
)
from aprkb.policies.loader import load_policy_bundle

_COMPONENT_NAME = "aprkb_sentence_rules"
_HEADING_LINE = re.compile(r"^\s*\d+(?:\.\d+)*\.\s+\S.*$")
_BLANK_LINE = re.compile(r"\n[ \t]*\n")
_SENTENCE_STARTERS = frozenset(
    {"a", "an", "the", "this", "that", "these", "those", "we", "they", "it", "our"}
)


class SpacyEngine:
    """Run one lazily-loaded spaCy pipeline while preserving source offsets."""

    def __init__(self, model_name: str = "en_core_web_sm", *, abbreviation_guard: bool = True):
        import spacy
        from spacy.language import Language

        abbreviations = (
            frozenset(
                value.casefold() for value in load_policy_bundle().abbreviations.abbreviations
            )
            if abbreviation_guard
            else frozenset()
        )
        _register_sentence_rules(Language)
        self._nlp = spacy.load(model_name, exclude=("ner",))
        config = {
            "abbreviations": sorted(abbreviations),
            "abbreviation_guard": abbreviation_guard,
        }
        if _COMPONENT_NAME not in self._nlp.pipe_names:
            if "parser" in self._nlp.pipe_names:
                self._nlp.add_pipe(_COMPONENT_NAME, before="parser", config=config)
            else:
                self._nlp.add_pipe(_COMPONENT_NAME, first=True, config=config)

        meta = self._nlp.meta
        self._info = NlpEngineInfo(
            engine="spacy",
            spacy_version=spacy.__version__,
            model_name=model_name,
            model_version=str(meta.get("version", "unknown")),
            components=tuple(self._nlp.pipe_names),
            schema_version=FEATURES_SCHEMA_VERSION,
            abbreviation_guard=abbreviation_guard,
        )

    @property
    def info(self) -> NlpEngineInfo:
        return self._info

    def analyze(self, text: str) -> list[SentenceAnalysis]:
        doc = self._nlp(text)
        return [
            self._analysis_from_sentence(doc, sentence)
            for sentence in doc.sents
            if sentence.text.strip()
        ]

    def analyze_many(self, texts: Iterable[str]) -> Iterator[list[SentenceAnalysis]]:
        for doc in self._nlp.pipe(texts):
            yield [
                self._analysis_from_sentence(doc, sentence)
                for sentence in doc.sents
                if sentence.text.strip()
            ]

    @staticmethod
    def _analysis_from_sentence(doc: Any, sentence: Any) -> SentenceAnalysis:
        char_start, char_end = _trim_offsets(doc.text, sentence.start_char, sentence.end_char)
        sentence_tokens = [
            token
            for token in sentence
            if char_start <= token.idx and token.idx + len(token.text) <= char_end
        ]
        token_indexes = {token.i: index for index, token in enumerate(sentence_tokens)}
        resolved: list[tuple[Any, int | None, str]] = []
        for token in sentence_tokens:
            head = token_indexes.get(token.head.i)
            if head is None and not token.head.is_space:
                raise AssertionError("spaCy token head escaped its sentence")
            resolved.append((token, head, token.dep_))
        repair_root = not any(head is not None and dep == "ROOT" for _, head, dep in resolved)
        features: list[TokenFeature] = []
        for index, (token, head, dep) in enumerate(resolved):
            if head is None:
                head = index
                dep = "ROOT" if repair_root else "dep"
                repair_root = False
            features.append(
                TokenFeature(
                    i=index,
                    start=token.idx - char_start,
                    end=token.idx + len(token.text) - char_start,
                    pos=token.pos_,
                    tag=token.tag_,
                    dep=dep,
                    head=head,
                    lemma=token.lemma_,
                    morph=str(token.morph),
                    is_space=token.is_space,
                )
            )
        if sum(feature.dep == "ROOT" for feature in features) != 1:
            raise AssertionError("spaCy sentence must contain exactly one ROOT")
        return SentenceAnalysis(char_start, char_end, tuple(features))


def get_engine(
    model_name: str = "en_core_web_sm", *, abbreviation_guard: bool = True
) -> SpacyEngine:
    """Create a lazily-importing spaCy engine for the requested model."""
    return SpacyEngine(model_name, abbreviation_guard=abbreviation_guard)


def _register_sentence_rules(language: Any) -> None:
    if _COMPONENT_NAME in language.factories:
        return

    @language.factory(  # type: ignore[untyped-decorator]
        _COMPONENT_NAME,
        default_config={"abbreviations": [], "abbreviation_guard": True},
    )
    def create_sentence_rules(
        nlp: Any, name: str, abbreviations: list[str], abbreviation_guard: bool
    ) -> Any:
        del nlp, name
        return _SentenceRules(abbreviations, abbreviation_guard)


class _SentenceRules:
    """spaCy component for policy abbreviations and deterministic hard boundaries."""

    def __init__(self, abbreviations: Iterable[str], abbreviation_guard: bool) -> None:
        self._abbreviations = frozenset(value.casefold().rstrip(".") for value in abbreviations)
        self._abbreviation_guard = abbreviation_guard

    def __call__(self, doc: Any) -> Any:
        for index, token in enumerate(doc):
            next_token = _next_content_token(doc, index)
            if next_token is None:
                continue
            blank_line = _is_blank_line_between(doc.text, token, next_token)
            if blank_line:
                next_token.is_sent_start = True
            if _is_numeric_heading_boundary(doc.text, token, next_token):
                next_token.is_sent_start = True
            if _is_unspaced_sentence_boundary(doc.text, token, next_token):
                next_token.is_sent_start = True
            if _is_protected_delimited_boundary(doc.text, token, next_token):
                next_token.is_sent_start = False
            if _is_terminal_punctuation_boundary(doc.text, token, next_token):
                next_token.is_sent_start = True
            if (
                self._abbreviation_guard
                and not blank_line
                and _is_guarded_abbreviation(token, self._abbreviations)
            ):
                next_token.is_sent_start = _is_sentence_starter(next_token)
        return doc


def _is_guarded_abbreviation(token: Any, abbreviations: frozenset[str]) -> bool:
    normalized = token.text.casefold().rstrip(".")
    if normalized not in abbreviations:
        return False
    # The policy contains `ms`, but only capitalised `Ms.` is a title. Lowercase
    # `ms.` is treated as the unit so that "measured in ms. Latency" can split.
    return not (normalized == "ms" and token.text == "ms")


def _is_sentence_starter(token: Any) -> bool:
    return token.text[:1].isupper() and token.text.casefold() in _SENTENCE_STARTERS


def _next_content_token(doc: Any, index: int) -> Any | None:
    next_index = index + 1
    while next_index < len(doc) and doc[next_index].is_space:
        next_index += 1
    return doc[next_index] if next_index < len(doc) else None


def _is_blank_line_between(text: str, token: Any, next_token: Any) -> bool:
    return bool(_BLANK_LINE.search(text[token.idx + len(token.text) : next_token.idx]))


def _is_numeric_heading_boundary(text: str, token: Any, next_token: Any) -> bool:
    if "\n" not in text[token.idx + len(token.text) : next_token.idx]:
        return False
    line_start = text.rfind("\n", 0, token.idx + len(token.text)) + 1
    line_end = text.find("\n", token.idx + len(token.text))
    if line_end == -1:
        return False
    return bool(_HEADING_LINE.fullmatch(text[line_start:line_end]))


def _is_unspaced_sentence_boundary(text: str, token: Any, next_token: Any) -> bool:
    gap = text[token.idx + len(token.text) : next_token.idx]
    return not gap and token.text in {".", "!", "?"} and next_token.text[:1].isupper()


def _is_terminal_punctuation_boundary(text: str, token: Any, next_token: Any) -> bool:
    gap = text[token.idx + len(token.text) : next_token.idx]
    return (
        bool(gap) and gap.isspace() and token.text in {"!", "?"} and next_token.text[:1].isupper()
    )


def _is_protected_delimited_boundary(text: str, token: Any, next_token: Any) -> bool:
    if token.text == ")":
        opening = text.rfind("(", 0, token.idx)
        closing = text.rfind(")", 0, token.idx)
        return opening > closing and any(mark in text[opening : token.idx] for mark in {"?", "!"})
    if token.text in {'"', "'"}:
        prefix = text[: token.idx]
        return prefix.count(token.text) % 2 == 1 and any(
            mark in prefix[prefix.rfind(token.text) :] for mark in {"?", "!"}
        )
    return False


def _trim_offsets(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end
