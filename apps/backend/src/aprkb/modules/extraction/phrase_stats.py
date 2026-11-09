"""Read-only document-frequency contrast for safely masked candidate frames."""

from dataclasses import dataclass
from math import log
from uuid import UUID

from aprkb.modules.mining.frame_key import frame_key
from aprkb.policies.schemas import PhraseStatsPolicy


@dataclass(frozen=True)
class CandidateArticle:
    candidate_id: UUID
    frame: str
    status: str
    sentence_id: UUID
    article_id: UUID
    batch_id: UUID | None
    journal_id: UUID | None
    cluster_key: str | None = None


@dataclass(frozen=True)
class PhraseStatsRequest:
    focal_batch_id: UUID | None = None
    focal_journal_id: UUID | None = None
    background_batch_ids: tuple[UUID, ...] = ()
    background_journal_ids: tuple[UUID, ...] = ()
    all_other: bool = False
    top_n: int | None = None


@dataclass(frozen=True)
class FrameStats:
    frame: str
    df_focal: int
    n_focal: int
    df_bg: int
    n_bg: int
    occurrences: int
    score: float
    sample_sentence_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class PhraseStatsResult:
    status_included: tuple[str, ...]
    n_focal: int
    n_bg: int
    score_ranking: tuple[FrameStats, ...]
    recurrence_ranking: tuple[FrameStats, ...]
    notices: tuple[str, ...]


@dataclass
class _FrameGroup:
    frames: set[str]
    focal_docs: set[UUID]
    background_docs: set[UUID]
    candidate_articles: set[tuple[UUID, UUID]]
    samples: dict[UUID, UUID]


def compute_phrase_stats(
    rows: list[CandidateArticle], request: PhraseStatsRequest, policy: PhraseStatsPolicy
) -> PhraseStatsResult:
    """Aggregate candidate rows by distinct article and score descriptive frame contrast."""
    _validate_request(request)
    eligible = [row for row in rows if row.status in {"pending", "accepted"}]
    focal = [
        row for row in eligible if _matches(row, request.focal_batch_id, request.focal_journal_id)
    ]
    if request.all_other:
        focal_article_ids = {row.article_id for row in focal}
        background = [row for row in eligible if row.article_id not in focal_article_ids]
    else:
        background = [
            row
            for row in eligible
            if _matches_many(row, request.background_batch_ids, request.background_journal_ids)
        ]

    focal_articles = {row.article_id for row in focal}
    background_articles = {row.article_id for row in background}
    if focal_articles & background_articles:
        raise ValueError("focal and background article sets overlap")

    n_focal, n_bg = len(focal_articles), len(background_articles)
    grouped: dict[str, _FrameGroup] = {}
    for is_focal, source_rows in ((True, focal), (False, background)):
        for row in source_rows:
            construction = _construction_prefix(row.cluster_key)
            key = frame_key(row.frame, construction)
            group = grouped.setdefault(key, _FrameGroup(set(), set(), set(), set(), {}))
            group.frames.add(row.frame)
            if is_focal:
                group.focal_docs.add(row.article_id)
                group.candidate_articles.add((row.candidate_id, row.article_id))
                group.samples.setdefault(row.article_id, row.sentence_id)
            else:
                group.background_docs.add(row.article_id)

    alpha = policy.smoothing_alpha
    results = [
        FrameStats(
            frame=min(group.frames, key=lambda value: (value.casefold(), value)),
            df_focal=len(group.focal_docs),
            n_focal=n_focal,
            df_bg=len(group.background_docs),
            n_bg=n_bg,
            occurrences=len(group.candidate_articles),
            score=log(
                ((len(group.focal_docs) + alpha) / (n_focal + 2 * alpha))
                / ((len(group.background_docs) + alpha) / (n_bg + 2 * alpha))
            ),
            sample_sentence_ids=tuple(
                sentence_id
                for _, sentence_id in sorted(group.samples.items(), key=lambda pair: str(pair[0]))[
                    :3
                ]
            ),
        )
        for group in grouped.values()
    ]
    recurrence = sorted(
        results, key=lambda item: (-item.df_focal, -item.occurrences, frame_key(item.frame))
    )
    score_results = sorted(
        (item for item in results if item.df_focal >= policy.min_focal_docs),
        key=lambda item: (-item.score, -item.df_focal, -item.occurrences, frame_key(item.frame)),
    )
    limit = request.top_n if request.top_n is not None else policy.top_n
    notices: list[str] = []
    if n_focal < policy.warn_below_focal_articles:
        notices.append("focal article count is below the warning threshold; ranking is unstable")
    if n_bg == 0:
        notices.append("background is empty; no contrast is possible")
    unstable = n_focal < policy.warn_below_focal_articles or n_bg == 0
    return PhraseStatsResult(
        status_included=("pending", "accepted"),
        n_focal=n_focal,
        n_bg=n_bg,
        score_ranking=() if unstable else tuple(score_results[:limit]),
        recurrence_ranking=tuple(recurrence[:limit]),
        notices=tuple(notices),
    )


def _validate_request(request: PhraseStatsRequest) -> None:
    if (request.focal_batch_id is None) == (request.focal_journal_id is None):
        raise ValueError("select exactly one focal batch or journal")
    if request.all_other and (request.background_batch_ids or request.background_journal_ids):
        raise ValueError("all_other cannot be combined with explicit background selectors")
    if not request.all_other and not (
        request.background_batch_ids or request.background_journal_ids
    ):
        raise ValueError("select explicit background batches/journals or all_other")
    if request.top_n is not None and request.top_n < 1:
        raise ValueError("top_n must be positive")


def _matches(row: CandidateArticle, batch_id: UUID | None, journal_id: UUID | None) -> bool:
    return row.batch_id == batch_id if batch_id is not None else row.journal_id == journal_id


def _matches_many(
    row: CandidateArticle, batch_ids: tuple[UUID, ...], journal_ids: tuple[UUID, ...]
) -> bool:
    return row.batch_id in batch_ids or row.journal_id in journal_ids


def _construction_prefix(cluster_key: str | None) -> str | None:
    if cluster_key is None or not cluster_key.startswith("construction="):
        return None
    parts = cluster_key.split(":", 2)
    return f"{parts[0].removeprefix('construction=')}:{parts[1]}" if len(parts) == 3 else None
