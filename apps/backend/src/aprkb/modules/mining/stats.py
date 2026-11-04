"""Corpus-level mining statistics without labels or persistent source text."""

from collections import Counter
from dataclasses import dataclass
from random import Random
from uuid import UUID

from aprkb.modules.mining.pipeline import MiningPipeline
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.modules.mining.stages.sentence_filter import SentenceFilter
from aprkb.modules.mining.stages.slot_abstractor import SlotAbstractor
from aprkb.nlp.features import TokenFeature
from aprkb.policies.loader import PolicyBundle

EXTRACTED = "EXTRACTED"
EXTRACTION_REASONS = (
    EXTRACTED,
    "no_reporting_verb",
    "no_that",
    "no_subject",
    "subject_too_long",
    "clause_too_short",
    "empty_noun_phrase",
    "coordinated_reporting_verbs",
    "subject_not_nominal",
    "syntax_invalid_tokens",
)


@dataclass(frozen=True)
class StatsSentence:
    """The minimum sentence data needed by the pure statistics function."""

    text: str
    section_code: str | None = None
    sentence_id: UUID | None = None
    char_start: int = 0
    tokens: tuple[TokenFeature, ...] | None = None
    locator: str | None = None


@dataclass(frozen=True)
class StatsSample:
    """A terminal-only sample; callers must not persist this value."""

    text: str
    frame: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class MiningStats:
    total_sentences: int
    filter_kept: int
    filter_rejected: dict[str, int]
    extraction_reasons: dict[str, int]
    distinct_frames: int
    top_frames: list[tuple[str, int]]
    extracted_samples: list[StatsSample]
    missed_samples: list[StatsSample]


def compute_mining_stats(
    sentences: list[StatsSentence],
    policy_bundle: PolicyBundle,
    *,
    sample: int = 0,
    seed: int = 0,
) -> MiningStats:
    """Compute deterministic extraction coverage statistics from in-memory sentences.

    The function keeps source text only in memory for optional terminal samples. It does not
    write or log source text, and the returned counts and frames are safe to persist.
    """
    if sample < 0:
        raise ValueError("sample must be non-negative")

    stages = build_stages(policy_bundle=policy_bundle)
    sentence_filter = next(stage for stage in stages if isinstance(stage, SentenceFilter))
    abstractor = next(stage for stage in stages if isinstance(stage, SlotAbstractor))
    pipeline = MiningPipeline(stages=stages)
    filter_rejected: Counter[str] = Counter()
    extraction_reasons: Counter[str] = Counter({reason: 0 for reason in EXTRACTION_REASONS})
    frames: Counter[str] = Counter()
    extracted: list[StatsSample] = []
    missed: list[StatsSample] = []
    filter_kept = 0

    for index, sentence in enumerate(sentences):
        item = MiningItem(
            text=sentence.text,
            source_sentence_ids=[sentence.sentence_id or UUID(int=index + 1)],
            section_code=sentence.section_code,
            char_start=sentence.char_start,
            tokens=sentence.tokens,
            locator=sentence.locator,
        )
        filter_reason = sentence_filter.reject_reason(item)
        if filter_reason is not None:
            filter_rejected[filter_reason] += 1
            continue

        filter_kept += 1
        prediction = pipeline.process([item])
        if prediction:
            frame = prediction[0].text
            extraction_reasons[EXTRACTED] += 1
            frames[frame] += 1
            extracted.append(StatsSample(text=sentence.text[:140], frame=frame))
            continue

        reason = abstractor.extractability_reason(sentence.text, sentence.tokens) or "other"
        extraction_reasons[reason] += 1
        missed.append(StatsSample(text=sentence.text[:140], reason=reason))

    rng = Random(seed)
    return MiningStats(
        total_sentences=len(sentences),
        filter_kept=filter_kept,
        filter_rejected=dict(sorted(filter_rejected.items())),
        extraction_reasons=dict(extraction_reasons),
        distinct_frames=len(frames),
        top_frames=frames.most_common(15),
        extracted_samples=_sample_records(extracted, sample, rng),
        missed_samples=_sample_records(missed, sample, rng),
    )


def _sample_records(records: list[StatsSample], size: int, rng: Random) -> list[StatsSample]:
    if size == 0 or not records:
        return []
    count = min(size, len(records))
    return [records[index] for index in rng.sample(range(len(records)), count)]
