from __future__ import annotations

from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from aprkb.core.config import settings
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.mining.epistemic_labelers import (
    DualEpistemicAssessment,
    EpistemicAssessment,
    EpistemicKey,
    EpistemicPredicate,
)
from aprkb.modules.mining.epistemic_lexicon_service import (
    EPISTEMIC_ENRICHMENT_JOB_TYPE,
    assess_epistemic_entries,
    discover_epistemic_oov,
    enqueue_epistemic_oov_batch,
    load_active_epistemic_snapshot,
    review_epistemic_entry,
)
from aprkb.modules.mining.models import EpistemicLexiconAudit, Job


class _DualLabeler:
    provider = "test"
    model = "test-model"
    prompt_version = "test-dual-prompt-v1"

    async def assess_batch(self, predicates: list[EpistemicPredicate]):
        results: dict[EpistemicKey, DualEpistemicAssessment] = {}
        for predicate in predicates:
            if predicate.lemma == "dispute":
                run1 = EpistemicAssessment(
                    tier="high", confidence=0.99, rationale="Strong empirical assertion."
                )
                run2 = EpistemicAssessment(
                    tier="moderate", confidence=0.98, rationale="Evidence-based inference."
                )
            elif predicate.lemma == "contend":
                run1 = run2 = EpistemicAssessment(
                    tier="moderate", confidence=0.89, rationale="A reasoned academic claim."
                )
            elif predicate.lemma == "assert":
                run1 = run2 = EpistemicAssessment(
                    tier="moderate", confidence=0.90, rationale="A reasoned academic claim."
                )
            else:
                run1 = run2 = EpistemicAssessment(
                    tier="high", confidence=0.97, rationale="Direct empirical reporting force."
                )
            results[predicate.key] = DualEpistemicAssessment(run1=run1, run2=run2)
        return results


async def test_oov_discovery_batches_jobs_and_requires_provider_and_rights_gates(
    postgres_test_engine: AsyncEngine, monkeypatch
) -> None:
    factory = async_sessionmaker(postgres_test_engine, expire_on_commit=False)
    monkeypatch.setattr(settings, "epistemic_labeler", "null")
    monkeypatch.setattr(settings, "groq_allow_external_processing", False)
    async with factory() as session:
        first = await discover_epistemic_oov(
            session,
            lemma="postulate",
            pos="verb",
            construction_family="ccomp",
            enqueue_job=False,
        )
        second = await discover_epistemic_oov(
            session,
            lemma="posit",
            pos="verb",
            construction_family="ccomp",
            enqueue_job=False,
        )
        duplicate = await discover_epistemic_oov(
            session,
            lemma="POSTULATE",
            pos="VERB",
            construction_family="CCOMP",
            enqueue_job=False,
        )
        assert first.id == duplicate.id
        assert await session.scalar(select(func.count(Job.id))) == 0

        monkeypatch.setattr(settings, "epistemic_labeler", "groq")
        monkeypatch.setattr(settings, "groq_allow_external_processing", True)
        monkeypatch.setattr(settings, "groq_api_key", SecretStr("test-only"))
        await enqueue_epistemic_oov_batch(
            session, [first, second], rights_allow_external_processing=True
        )
        job = await session.scalar(select(Job).where(Job.type == EPISTEMIC_ENRICHMENT_JOB_TYPE))
        assert job is not None
        assert set(job.payload) == {"entry_ids"}
        assert set(job.payload["entry_ids"]) == {str(first.id), str(second.id)}
        await session.commit()


async def test_dual_consensus_activates_only_matching_tiers_above_point_nine(
    postgres_test_engine: AsyncEngine,
) -> None:
    factory = async_sessionmaker(postgres_test_engine, expire_on_commit=False)
    async with factory() as session:
        entries = [
            await discover_epistemic_oov(
                session, lemma=lemma, pos="verb", construction_family="ccomp", enqueue_job=False
            )
            for lemma in ("postulate", "dispute", "contend", "assert")
        ]
        results = await assess_epistemic_entries(
            session,
            entry_ids=[entry.id for entry in entries],
            labeler=_DualLabeler(),  # type: ignore[arg-type]
        )
        by_lemma = {entry.lemma: entry for entry in results}

        assert by_lemma["postulate"].status == "active"
        assert by_lemma["postulate"].score == 2.0
        assert by_lemma["postulate"].run1_tier == by_lemma["postulate"].run2_tier == "high"
        assert by_lemma["dispute"].status == "needs_review"
        assert by_lemma["dispute"].review_reason == "tier_disagreement"
        assert by_lemma["dispute"].score == 1.0
        assert by_lemma["contend"].status == "needs_review"
        assert by_lemma["contend"].review_reason == "low_confidence"
        assert by_lemma["assert"].status == "active"
        assert by_lemma["assert"].confidence == 0.90
        snapshot = await load_active_epistemic_snapshot(session)
        assert snapshot.entries[("postulate", "verb", "ccomp")] == 2.0
        assert ("dispute", "verb", "ccomp") not in snapshot.entries


async def test_locked_neutral_oov_is_held_without_provider_job(
    postgres_test_engine: AsyncEngine, monkeypatch
) -> None:
    factory = async_sessionmaker(postgres_test_engine, expire_on_commit=False)
    monkeypatch.setattr(settings, "epistemic_labeler", "groq")
    monkeypatch.setattr(settings, "groq_allow_external_processing", True)
    monkeypatch.setattr(settings, "groq_api_key", SecretStr("test-only"))
    async with factory() as session:
        entry = await discover_epistemic_oov(
            session,
            lemma="select",
            pos="verb",
            construction_family="ccomp",
            rights_allow_external_processing=True,
        )
        assert entry.status == "policy_conflict_hold"
        assert entry.provenance == "policy_conflict_hold"
        assert await session.scalar(select(func.count(Job.id))) == 0
        curator = ApiClient(
            name="test curator",
            key_hash="test-curator-key-hash",
            key_prefix="testcurator",
            role="curator",
        )
        session.add(curator)
        await session.flush()
        await review_epistemic_entry(
            session, entry_id=entry.id, actor_id=curator.id, action="reject"
        )
        audit = await session.scalar(
            select(EpistemicLexiconAudit).where(EpistemicLexiconAudit.entry_id == entry.id)
        )
        assert audit is not None
        assert audit.previous_status == "policy_conflict_hold"
        assert audit.new_status == "rejected"
        await session.commit()
