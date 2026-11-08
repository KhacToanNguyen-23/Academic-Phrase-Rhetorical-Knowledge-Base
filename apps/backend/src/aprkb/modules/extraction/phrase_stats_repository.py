"""Read candidate/article membership needed by the phrase-stats service."""

from sqlalchemy import any_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.corpus.models import Article, License, Sentence
from aprkb.modules.extraction.phrase_stats import CandidateArticle
from aprkb.modules.mining.models import Candidate


async def candidate_articles(session: AsyncSession) -> list[CandidateArticle]:
    """Return source membership for pending/accepted candidates; never select sentence text."""
    rows = await session.execute(
        select(
            Candidate.id,
            Candidate.canonical_frame,
            Candidate.status,
            Candidate.cluster_key,
            Sentence.id,
            Article.id,
            Article.import_batch_id,
            Article.journal_id,
        )
        .join(Sentence, Sentence.id == any_(Candidate.source_sentence_ids))
        .join(Article, Article.id == Sentence.article_id)
        .join(License, License.id == Article.license_id)
        .where(Candidate.status.in_(("pending", "accepted")))
        .where(License.allows_mining.is_(True))
        .order_by(Candidate.id, Article.id, Sentence.id)
    )
    return [
        CandidateArticle(
            candidate_id=candidate_id,
            frame=frame,
            status=status,
            cluster_key=cluster_key,
            sentence_id=sentence_id,
            article_id=article_id,
            batch_id=batch_id,
            journal_id=journal_id,
        )
        for (
            candidate_id,
            frame,
            status,
            cluster_key,
            sentence_id,
            article_id,
            batch_id,
            journal_id,
        ) in rows
    ]
