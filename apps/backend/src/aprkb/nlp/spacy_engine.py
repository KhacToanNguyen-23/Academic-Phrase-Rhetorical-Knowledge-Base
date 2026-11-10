"""spaCy parser with shared character-level sentence-boundary rules."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Any

from aprkb.modules.corpus.sentence_splitter import (
    BoundaryDecision,
    boundary_candidates,
)
from aprkb.nlp.features import (
    FEATURES_SCHEMA_VERSION,
    NlpEngineInfo,
    SentenceAnalysis,
    TokenFeature,
)
from aprkb.policies.loader import load_policy_bundle
from aprkb.policies.schemas import SentenceRulesPolicy

if TYPE_CHECKING:
    from spacy.tokens import Doc

_COMPONENT_NAME = "aprkb_sentence_rules"


class SpacyEngine:
    """Run one lazily-loaded spaCy pipeline while preserving source offsets."""

    def __init__(self, model_name: str = "en_core_web_sm"):
        import spacy
        from spacy.language import Language

        self._sentence_rules = load_policy_bundle().sentence_rules
        self._repaired_sentences = 0
        _register_sentence_rules(Language)
        self._nlp = spacy.load(model_name, exclude=("ner",))
        if _COMPONENT_NAME not in self._nlp.pipe_names:
            config = {"rules": self._sentence_rules.model_dump(mode="json")}
            if "parser" in self._nlp.pipe_names:
                self._nlp.add_pipe(_COMPONENT_NAME, before="parser", config=config)
            else:
                self._nlp.add_pipe(_COMPONENT_NAME, first=True, config=config)
        self._rules_component = self._nlp.get_pipe(_COMPONENT_NAME)
        meta = self._nlp.meta
        self._info = NlpEngineInfo(
            engine="spacy",
            spacy_version=_distribution_version("spacy"),
            model_name=model_name,
            model_version=str(meta.get("version", "unknown")),
            components=tuple(self._nlp.pipe_names),
            schema_version=FEATURES_SCHEMA_VERSION,
            abbreviation_guard=False,
            boundary_policy_version=self._sentence_rules.version,
        )

    @property
    def info(self) -> NlpEngineInfo:
        return self._info

    @property
    def alignment_misses(self) -> int:
        """Count candidate offsets that did not align to a spaCy token start."""
        return int(getattr(self._rules_component, "alignment_misses", 0))

    @property
    def repaired_sentences(self) -> int:
        """Count analyses whose token tree needed a recorded repair."""
        return self._repaired_sentences

    def analyze(self, text: str) -> list[SentenceAnalysis]:
        doc = self._nlp(text)
        return self._analyses(doc)

    def parse(self, text: str) -> Doc:
        """Return an ephemeral parsed Doc for consumers that need dependency tokens."""
        return self._nlp(text)

    def analyze_many(self, texts: Iterable[str]) -> Iterator[list[SentenceAnalysis]]:
        for doc in self._nlp.pipe(texts):
            yield self._analyses(doc)

    def _analyses(self, doc: Any) -> list[SentenceAnalysis]:
        candidates = {
            item.offset: item for item in boundary_candidates(doc.text, self._sentence_rules)
        }
        analyses: list[SentenceAnalysis] = []
        first = True
        for sentence in doc.sents:
            if not sentence.text.strip():
                continue
            analyses.append(
                self._analysis_from_sentence(
                    doc,
                    sentence,
                    candidates,
                    is_first=first,
                )
            )
            first = False
        self._repaired_sentences += sum(analysis.repaired for analysis in analyses)
        return analyses

    @staticmethod
    def _analysis_from_sentence(
        doc: Any, sentence: Any, candidates: dict[int, Any], *, is_first: bool = False
    ) -> SentenceAnalysis:
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
        repaired = not any(head is not None and dep == "ROOT" for _, head, dep in resolved)
        repair_root = repaired
        features: list[TokenFeature] = []
        for index, (token, head, dep) in enumerate(resolved):
            if head is None:
                head = index
                dep = "ROOT" if repair_root else "dep"
                repair_root = False
                repaired = True
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
        candidate = candidates.get(sentence.start_char)
        boundary_source = (
            "rule:start"
            if is_first
            else (
                f"rule:{candidate.rule}"
                if candidate is not None and candidate.decision is not BoundaryDecision.UNSURE
                else "parser"
            )
        )
        return SentenceAnalysis(char_start, char_end, tuple(features), boundary_source, repaired)


def get_engine(model_name: str = "en_core_web_sm") -> SpacyEngine:
    """Create a lazily-importing spaCy engine for the requested model."""
    return SpacyEngine(model_name)


def _register_sentence_rules(language: Any) -> None:
    if _COMPONENT_NAME in language.factories:
        return

    @language.factory(  # type: ignore[untyped-decorator]
        _COMPONENT_NAME,
        default_config={"rules": {}},
    )
    def create_sentence_rules(nlp: Any, name: str, rules: dict[str, Any]) -> Any:
        del nlp, name
        return _SentenceRules(SentenceRulesPolicy.model_validate(rules))


class _SentenceRules:
    """Apply tri-state character rules before the spaCy dependency parser."""

    def __init__(self, rules: SentenceRulesPolicy) -> None:
        self._rules = rules
        self.alignment_misses = 0

    def __call__(self, doc: Any) -> Any:
        candidates = boundary_candidates(doc.text, self._rules)
        by_offset = {token.idx: token for token in doc if not token.is_space}
        for token in doc:
            token.is_sent_start = False
        first = next((token for token in doc if not token.is_space), None)
        if first is not None:
            first.is_sent_start = True
        for candidate in candidates:
            token = by_offset.get(candidate.offset)
            if token is None:
                self.alignment_misses += 1
                continue
            if candidate.decision is BoundaryDecision.SPLIT:
                token.is_sent_start = True
            elif candidate.decision is BoundaryDecision.NO_SPLIT:
                token.is_sent_start = False
            else:
                token.is_sent_start = None
        return doc


def _trim_offsets(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end
