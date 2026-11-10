"""Export proposed frame labels to the ignored local curation workbook."""

import argparse
import asyncio
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import any_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from aprkb.core.config import settings
from aprkb.modules.corpus.models import Article, ArticleSection, License, Sentence
from aprkb.modules.mining.frame_labels import FrameSourceLabelData, build_frame_labels
from aprkb.modules.mining.frame_sections import summarize_frame_sections
from aprkb.modules.mining.models import Candidate, CandidateLabel
from aprkb.modules.mining.review_workbook import write_review_workbook
from aprkb.modules.taxonomy.models import ArticleGenre
from aprkb.policies.loader import load_policy_bundle

OUTPUT = Path(__file__).resolve().parents[3] / "tmp" / "shared-frames-curation.xlsx"


async def export(*, with_examples: bool, output: Path = OUTPUT) -> int:
    policies = load_policy_bundle()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            rows, candidates = await _proposal_rows(session, policies)
            if with_examples:
                examples = await _rights_checked_examples(session, candidates)
                for row in rows:
                    row["examples"] = examples.get(UUID(row["candidate_id"]), [])
            write_review_workbook(
                rows,
                output,
                vocabulary=policies.frame_label_vocabulary,
                with_examples=with_examples,
                existing_path=output,
            )
            return len(rows)
    finally:
        await engine.dispose()


async def _proposal_rows(
    session: AsyncSession,
    policies: Any,
) -> tuple[list[dict[str, Any]], list[Candidate]]:
    candidates = list(
        await session.scalars(
            select(Candidate)
            .join(CandidateLabel, CandidateLabel.candidate_id == Candidate.id)
            .where(CandidateLabel.status == "proposed", Candidate.status == "pending")
            .distinct()
            .order_by(Candidate.id)
        )
    )
    if not candidates:
        return [], []
    candidate_ids = [candidate.id for candidate in candidates]
    label_rows = list(
        await session.scalars(
            select(CandidateLabel)
            .where(
                CandidateLabel.candidate_id.in_(candidate_ids),
                CandidateLabel.status == "proposed",
            )
            .order_by(CandidateLabel.candidate_id, CandidateLabel.label_code)
        )
    )
    labels_by_candidate: dict[UUID, dict[str, dict[str, Any]]] = defaultdict(dict)
    for label in label_rows:
        labels_by_candidate[label.candidate_id][label.label_code] = {
            "value": label.value,
            "confidence": label.confidence,
            "agreement": label.agreement,
            "options": label.options,
            "needs_attention": label.needs_attention,
        }
    metadata_rows = await session.execute(
        select(
            Candidate.id,
            Sentence.id,
            Article.id,
            ArticleSection.section_code,
            ArticleGenre.code,
            License.code,
            License.allows_mining,
            License.allows_display,
        )
        .join(Sentence, Sentence.id == any_(Candidate.source_sentence_ids))
        .join(Article, Article.id == Sentence.article_id)
        .join(License, License.id == Article.license_id)
        .outerjoin(ArticleSection, ArticleSection.id == Sentence.article_section_id)
        .outerjoin(ArticleGenre, ArticleGenre.id == Article.genre_id)
        .where(Candidate.id.in_(candidate_ids))
        .order_by(Candidate.id, Article.id, Sentence.id)
    )
    sources_by_candidate: dict[UUID, list[tuple[Any, ...]]] = defaultdict(list)
    for source in metadata_rows:
        sources_by_candidate[source[0]].append(tuple(source[1:]))
    output_rows: list[dict[str, Any]] = []
    eligible_candidates: list[Candidate] = []
    for candidate in candidates:
        sources = sources_by_candidate.get(candidate.id, [])
        if not sources or any(not source[5] or not source[6] for source in sources):
            continue
        distribution = summarize_frame_sections(
            [(source[1], source[2]) for source in sources],
            dominant_share_threshold=policies.mining_filter.frame_section_dominant_share_threshold,
        )
        section_distribution = _format_sections(distribution.counts)
        labels = labels_by_candidate.get(candidate.id, {})
        frame_sources = [
            FrameSourceLabelData(
                article_id=str(source[1]),
                genre_code=source[3],
                license_code=source[4],
                allows_mining=bool(source[5]),
                allows_display=bool(source[6]),
            )
            for source in sources
        ]
        base_labels = build_frame_labels(
            canonical_frame=candidate.canonical_frame,
            slot_types={},
            epistemic_strength=candidate.epistemic_strength,
            source_sentence_count=len(candidate.source_sentence_ids),
            cluster_key=candidate.cluster_key,
            sources=frame_sources,
            section_distribution=distribution,
            dominant_share_threshold=policies.mining_filter.frame_section_dominant_share_threshold,
            anchor_policy=policies.frame_function_anchors,
        )
        anchor_suggestion = (
            "; ".join(
                f"{field}={getattr(base_labels, field).value}"
                for field in ("function_group", "intent", "general_function")
                if getattr(base_labels, field).status == "proposed"
            )
            or None
        )
        for field in ("function_group", "intent", "general_function"):
            rule_label = getattr(base_labels, field)
            if rule_label.status == "proposed":
                labels.setdefault(
                    field,
                    {
                        "value": rule_label.value,
                        "confidence": rule_label.confidence,
                        "agreement": "anchor",
                        "needs_attention": False,
                    },
                )
        output_rows.append(
            {
                "candidate_id": str(candidate.id),
                "canonical_frame": candidate.canonical_frame,
                "family": _family(candidate.cluster_key),
                "paper_count": distribution.paper_count,
                "sentence_count": len(candidate.source_sentence_ids),
                "section_distribution": section_distribution,
                "epistemic_strength": candidate.epistemic_strength,
                "examples": [],
                "labels": labels,
                "anchor_suggestion": anchor_suggestion,
                "paper_ids": [
                    hashlib.sha256(str(article_id).encode("utf-8")).hexdigest()[:16]
                    for article_id in sorted({source[1] for source in sources})
                ],
            }
        )
        eligible_candidates.append(candidate)
    return output_rows, eligible_candidates


async def _rights_checked_examples(
    session: AsyncSession,
    candidates: list[Candidate],
) -> dict[UUID, list[str]]:
    """Read example text only after all sources for each candidate pass both rights checks."""
    if not candidates:
        return {}
    ids = [candidate.id for candidate in candidates]
    metadata = await session.execute(
        select(Candidate.id, Sentence.id, Article.id, License.allows_mining, License.allows_display)
        .join(Sentence, Sentence.id == any_(Candidate.source_sentence_ids))
        .join(Article, Article.id == Sentence.article_id)
        .join(License, License.id == Article.license_id)
        .where(Candidate.id.in_(ids))
        .with_for_update(of=License)
    )
    allowed: dict[UUID, list[tuple[UUID, UUID]]] = defaultdict(list)
    denied: set[UUID] = set()
    expected = {candidate.id: set(candidate.source_sentence_ids) for candidate in candidates}
    seen: dict[UUID, set[UUID]] = defaultdict(set)
    for candidate_id, sentence_id, article_id, allows_mining, allows_display in metadata:
        seen[candidate_id].add(sentence_id)
        if not allows_mining or not allows_display:
            denied.add(candidate_id)
        else:
            allowed[candidate_id].append((sentence_id, article_id))
    approved_ids = {
        candidate_id
        for candidate_id in expected
        if candidate_id not in denied and seen[candidate_id] == expected[candidate_id]
    }
    sentence_to_candidates: dict[UUID, list[UUID]] = defaultdict(list)
    for candidate_id in approved_ids:
        for sentence_id, _ in allowed[candidate_id]:
            sentence_to_candidates[sentence_id].append(candidate_id)
    if not sentence_to_candidates:
        return {}
    text_rows = await session.execute(
        select(Sentence.id, Sentence.article_id, Sentence.text)
        .where(Sentence.id.in_(sentence_to_candidates))
        .order_by(Sentence.article_id, Sentence.char_start, Sentence.id)
    )
    examples: dict[UUID, list[str]] = defaultdict(list)
    articles: dict[UUID, set[UUID]] = defaultdict(set)
    for sentence_id, article_id, text in text_rows:
        for candidate_id in sentence_to_candidates[sentence_id]:
            if article_id in articles[candidate_id]:
                continue
            articles[candidate_id].add(article_id)
            examples[candidate_id].append(text[:300])
    return dict(examples)


def _format_sections(counts: dict[str, int]) -> str:
    total = sum(counts.values())
    if total == 0:
        return "UNKNOWN"
    return ", ".join(
        f"{code} {round(count * 100 / total)}%" for code, count in counts.items() if count
    )


def _family(cluster_key: str | None) -> str:
    if cluster_key and cluster_key.startswith("construction="):
        return "Tier 2:" + cluster_key.removeprefix("construction=").split(":", 1)[0]
    return "Tier 1"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-examples",
        action="store_true",
        help="Include rights-checked examples in the local workbook",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    count = asyncio.run(export(with_examples=args.with_examples, output=args.output))
    print(f"Exported {count} frame proposal rows to the local workbook.")


if __name__ == "__main__":
    main()
