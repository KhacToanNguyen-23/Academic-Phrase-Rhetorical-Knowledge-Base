"""Phase 04 API contract tests derived from SCAFFOLD_PRD sections 7 and 10."""

import asyncio
import re
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from aprkb.api.main import create_app
from aprkb.core.deps import get_db_session
from aprkb.modules.audit.models import AuditEvent
from aprkb.modules.corpus.models import Article, ArticleSection, License, Sentence
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.identity.service import create_api_key
from aprkb.modules.journals.models import GuidelineRule, JournalProfile
from aprkb.modules.mining.models import Candidate
from aprkb.modules.patterns.models import (
    EvidenceProvenance,
    PatternVersion,
    PhrasePattern,
    ReviewDecision,
    UsageConstraint,
)
from aprkb.modules.recommendation.models import Feedback, Override, RecommendationLog
from aprkb.modules.taxonomy.models import Intent
from aprkb.seeds.load import run_seed


@pytest_asyncio.fixture
async def session_factory(postgres_test_engine: AsyncEngine) -> AsyncIterator[async_sessionmaker]:
    yield async_sessionmaker(postgres_test_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def api_client(session_factory: async_sessionmaker) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def override_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client,
    ):
        yield client


async def create_key(
    session_factory: async_sessionmaker, role: str, name: str | None = None
) -> tuple[ApiClient, str]:
    async with session_factory() as session:
        client, key = await create_api_key(session, name=name or f"phase04-{role}", role=role)
        await session.commit()
        return client, key


def _normalized_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{id}", path)


def test_openapi_matches_prd_routes_and_pattern_versions_are_append_only():
    app = create_app()
    paths = app.openapi()["paths"]
    actual = {
        (_normalized_path(path), method.lower())
        for path, operations in paths.items()
        for method in operations
    }
    expected = {
        ("/v1/health", "get"),
        ("/v1/taxonomy", "get"),
        ("/v1/taxonomy/releases", "get"),
        ("/v1/patterns", "get"),
        ("/v1/patterns/{id}", "get"),
        ("/v1/patterns/{id}/versions", "get"),
        ("/v1/patterns", "post"),
        ("/v1/patterns/{id}/versions", "post"),
        ("/v1/patterns/{id}/retire", "post"),
        ("/v1/recommendations", "post"),
        ("/v1/validate", "post"),
        ("/v1/feedback", "post"),
        ("/v1/overrides", "post"),
        ("/v1/journals", "get"),
        ("/v1/journals/{id}", "get"),
        ("/v1/journals/{id}/guidelines", "post"),
        ("/v1/admin/review-queue", "get"),
        ("/v1/admin/review-queue/{id}/decisions", "post"),
        ("/v1/admin/corpus/articles", "post"),
        ("/v1/admin/corpus/articles/{id}/mine", "post"),
        ("/v1/admin/corpus/imports", "post"),
        ("/v1/admin/jobs/{id}", "get"),
        ("/v1/admin/api-keys", "post"),
        ("/v1/admin/api-keys", "get"),
        ("/v1/admin/api-keys", "delete"),
        ("/v1/admin/releases/{id}/publish", "post"),
    }

    assert actual == expected
    for path, operations in paths.items():
        if "/versions" in path:
            assert set(operations) <= {"get", "post"}
            assert path.rstrip("/").count("/") == 4


@pytest.mark.asyncio
async def test_published_taxonomy_tree_and_release_list(api_client, session_factory):
    await run_seed_in_session(session_factory)
    _, key = await create_key(session_factory, "client", "taxonomy reader")
    headers = {"X-API-Key": key}

    releases = await api_client.get("/v1/taxonomy/releases", headers=headers)
    tree = await api_client.get("/v1/taxonomy", headers=headers)

    assert releases.status_code == 200
    assert "0.1.0" in releases.text
    assert "published" in releases.text
    assert tree.status_code == 200
    assert "INTRO" in tree.text
    assert "INTRO_GAP_INDICATE" in tree.text


@pytest.mark.asyncio
async def test_patterns_list_detail_history_create_and_append_version(api_client, session_factory):
    await run_seed_in_session(session_factory)
    _, key = await create_key(session_factory, "curator", "pattern curator")
    headers = {"X-API-Key": key}
    created = await api_client.post(
        "/v1/patterns",
        headers=headers,
        json={
            "intent_code": "INTRO_GAP_INDICATE",
            "canonical_frame": "The project introduces {topic}.",
            "slots": {"topic": "noun_phrase"},
            "epistemic_strength": "low",
            "claim_type": "descriptive",
            "change_note": "Initial draft",
            "allowed_sections": ["INTRO"],
            "allowed_genres": ["RESEARCH_ARTICLE"],
            "source_type": "authored",
        },
    )
    assert created.status_code in {200, 201}
    pattern_id = UUID(created.json()["id"])

    listed = await api_client.get(
        "/v1/patterns",
        params={"intent": "INTRO_GAP_INDICATE", "section": "INTRO", "status": "draft"},
        headers=headers,
    )
    detail = await api_client.get(f"/v1/patterns/{pattern_id}", headers=headers)
    history_before = await api_client.get(f"/v1/patterns/{pattern_id}/versions", headers=headers)

    assert listed.status_code == 200
    assert "The project introduces {topic}." in listed.text
    assert detail.status_code == 200
    assert "The project introduces {topic}." in detail.text
    assert history_before.status_code == 200
    assert "The project introduces {topic}." in history_before.text
    async with session_factory() as session:
        first_version = await session.scalar(
            select(PatternVersion).where(PatternVersion.pattern_id == pattern_id)
        )
        assert first_version is not None and first_version.version_no == 1
        first_version_id = first_version.id
        audit_before_append = (
            await session.scalar(select(func.count()).select_from(AuditEvent)) or 0
        )

    appended = await api_client.post(
        f"/v1/patterns/{pattern_id}/versions",
        headers=headers,
        json={
            "canonical_frame": "This project presents {topic}.",
            "slots": {"topic": "noun_phrase"},
            "epistemic_strength": "low",
            "claim_type": "descriptive",
            "change_note": "Clarify the frame",
        },
    )

    assert appended.status_code in {200, 201}
    history_after = await api_client.get(f"/v1/patterns/{pattern_id}/versions", headers=headers)
    assert history_after.status_code == 200
    assert "The project introduces {topic}." in history_after.text
    assert "This project presents {topic}." in history_after.text
    async with session_factory() as session:
        versions = list(
            await session.scalars(
                select(PatternVersion)
                .where(PatternVersion.pattern_id == pattern_id)
                .order_by(PatternVersion.version_no)
            )
        )
        assert [version.version_no for version in versions] == [1, 2]
        assert versions[0].id == first_version_id
        assert versions[0].canonical_frame == "The project introduces {topic}."
        assert versions[1].canonical_frame == "This project presents {topic}."
        audit_count = await session.scalar(select(func.count()).select_from(AuditEvent)) or 0
        assert audit_count >= audit_before_append + 1


@pytest.mark.asyncio
async def test_admin_retire_changes_pattern_status_and_audits_write(api_client, session_factory):
    await run_seed_in_session(session_factory)
    async with session_factory() as session:
        pattern_row = await session.scalar(
            select(PhrasePattern).where(PhrasePattern.status == "approved")
        )
        assert pattern_row is not None
        pattern_id = pattern_row.id
    _, admin_key = await create_key(session_factory, "admin", "pattern admin")

    response = await api_client.post(
        f"/v1/patterns/{pattern_id}/retire",
        headers={"X-API-Key": admin_key},
    )

    assert response.status_code in {200, 204}
    async with session_factory() as session:
        pattern_row = await session.get(PhrasePattern, pattern_id)
        audit_count = await session.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.entity_id == pattern_id)
        )
        assert pattern_row is not None and pattern_row.status == "retired"
        assert audit_count and audit_count >= 1


@pytest.mark.asyncio
async def test_journal_list_detail_and_guideline_write_are_persisted_and_audited(
    api_client, session_factory
):
    async with session_factory() as session:
        journal = JournalProfile(name="Phase 04 Test Journal", issn="2049-3630")
        session.add(journal)
        await session.commit()
        journal_id = journal.id
    _, client_key = await create_key(session_factory, "client", "journal reader")
    _, curator_key = await create_key(session_factory, "curator", "journal curator")

    listed = await api_client.get("/v1/journals", headers={"X-API-Key": client_key})
    detail = await api_client.get(f"/v1/journals/{journal_id}", headers={"X-API-Key": client_key})
    guideline = await api_client.post(
        f"/v1/journals/{journal_id}/guidelines",
        headers={"X-API-Key": curator_key},
        json={
            "rule_type": "submission_guideline",
            "payload": {"source": "test fixture"},
            "is_mandatory": False,
        },
    )

    assert listed.status_code == 200 and "Phase 04 Test Journal" in listed.text
    assert detail.status_code == 200 and "2049-3630" in detail.text
    assert guideline.status_code in {200, 201}
    async with session_factory() as session:
        rule = await session.scalar(
            select(GuidelineRule).where(GuidelineRule.journal_id == journal_id)
        )
        assert rule is not None and rule.rule_type == "submission_guideline"
        audit_count = await session.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.entity_id == rule.id)
        )
        assert audit_count and audit_count >= 1


@pytest.mark.asyncio
async def test_feedback_and_override_are_persisted_and_audited_rationale_is_required(
    api_client, session_factory
):
    await run_seed_in_session(session_factory)
    async with session_factory() as session:
        version = await session.scalar(select(PatternVersion).limit(1))
        assert version is not None
        version_id = version.id
    client, key = await create_key(session_factory, "client", "feedback client")
    headers = {"X-API-Key": key}
    recommendation_id = uuid4()
    feedback = await api_client.post(
        "/v1/feedback",
        headers=headers,
        json={
            "recommendation_id": str(recommendation_id),
            "pattern_version_id": str(version_id),
            "signal": "accepted",
            "payload": {"source": "test"},
        },
    )
    validation_id = uuid4()
    missing_rationale = await api_client.post(
        "/v1/overrides",
        headers=headers,
        json={"validation_id": str(validation_id), "rule_code": "V02"},
    )
    override = await api_client.post(
        "/v1/overrides",
        headers=headers,
        json={
            "validation_id": str(validation_id),
            "rule_code": "V02",
            "rationale": "The cited evidence was independently reviewed.",
        },
    )

    assert feedback.status_code in {200, 201}
    assert missing_rationale.status_code == 422
    assert override.status_code in {200, 201}
    async with session_factory() as session:
        feedback_row = await session.scalar(
            select(Feedback).where(Feedback.recommendation_id == recommendation_id)
        )
        override_row = await session.scalar(
            select(Override).where(Override.validation_id == validation_id)
        )
        assert feedback_row is not None
        assert feedback_row.client_id == client.id
        assert override_row is not None
        assert override_row.rationale == "The cited evidence was independently reviewed."
        audited_entity_ids = set(
            await session.scalars(
                select(AuditEvent.entity_id).where(
                    AuditEvent.entity_id.in_([feedback_row.id, override_row.id])
                )
            )
        )
        assert audited_entity_ids == {feedback_row.id, override_row.id}


@pytest.mark.asyncio
async def test_release_publish_is_explicitly_not_implemented(api_client, session_factory):
    _, admin_key = await create_key(session_factory, "admin", "release publisher")

    response = await api_client.post(
        f"/v1/admin/releases/{uuid4()}/publish",
        headers={"X-API-Key": admin_key},
    )

    assert response.status_code == 501


@pytest.mark.asyncio
async def test_role_hierarchy_on_client_reviewer_curator_and_admin_routes(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await run_seed_in_session(session_factory)
    keys = {
        role: (await create_key(session_factory, role))[1]
        for role in ("client", "reviewer", "curator", "admin")
    }
    missing_key = await api_client.get("/v1/taxonomy")
    assert missing_key.status_code == 401

    for role, key in keys.items():
        taxonomy = await api_client.get("/v1/taxonomy", headers={"X-API-Key": key})
        assert taxonomy.status_code == 200, role

    review_queue = "/v1/admin/review-queue"
    for role, key in keys.items():
        response = await api_client.get(review_queue, headers={"X-API-Key": key})
        if role == "client":
            assert response.status_code == 403
        else:
            assert response.status_code == 200, role

    job_path = f"/v1/admin/jobs/{uuid4()}"
    for role, key in keys.items():
        response = await api_client.get(job_path, headers={"X-API-Key": key})
        if role in {"client", "reviewer"}:
            assert response.status_code == 403
        else:
            assert response.status_code != 403, role

    for role, key in keys.items():
        response = await api_client.get("/v1/admin/api-keys", headers={"X-API-Key": key})
        if role == "admin":
            assert response.status_code == 200
        else:
            assert response.status_code == 403


@pytest.mark.asyncio
async def test_health_checks_database_and_all_responses_have_request_id(
    api_client: AsyncClient,
) -> None:
    response = await api_client.get("/v1/health")

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


@pytest.mark.asyncio
async def test_database_health_failure_uses_standard_error_envelope() -> None:
    app = create_app()

    async def failing_db_session():
        raise RuntimeError("database unavailable")
        yield  # pragma: no cover

    app.dependency_overrides[get_db_session] = failing_db_session
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client,
    ):
        response = await client.get("/v1/health")

    assert response.status_code >= 400
    body = response.json()
    assert set(body) == {"error", "request_id"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["request_id"] == response.headers.get("X-Request-ID")


@pytest.mark.asyncio
async def test_unknown_route_error_includes_matching_request_id(
    api_client: AsyncClient,
) -> None:
    response = await api_client.get("/v1/not-a-prd-route")

    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error", "request_id"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["request_id"] == response.headers.get("X-Request-ID")


@pytest.mark.asyncio
async def test_recommendation_pipeline_filters_seed_and_persists_explainable_log(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    async with session_factory() as session:
        await run_seed(session)
        intent = await session.scalar(select(Intent).where(Intent.code == "INTRO_GAP_INDICATE"))
        assert intent is not None
        unprovenanced = PhrasePattern(intent_id=intent.id, status="approved")
        session.add(unprovenanced)
        await session.flush()
        unprovenanced_version = PatternVersion(
            pattern_id=unprovenanced.id,
            version_no=1,
            canonical_frame="Unprovenanced phrase {topic}.",
            slots={"topic": "noun_phrase"},
            epistemic_strength="low",
            claim_type="descriptive",
        )
        session.add(unprovenanced_version)
        await session.flush()
        unprovenanced.current_version_id = unprovenanced_version.id
        session.add(
            UsageConstraint(
                pattern_version_id=unprovenanced_version.id,
                allowed_sections=["INTRO"],
                allowed_genres=["RESEARCH_ARTICLE"],
            )
        )
        conflicting = PhrasePattern(intent_id=intent.id, status="approved")
        session.add(conflicting)
        await session.flush()
        conflicting_version = PatternVersion(
            pattern_id=conflicting.id,
            version_no=1,
            canonical_frame="Conflicting provenance phrase {topic}.",
            slots={"topic": "noun_phrase"},
            epistemic_strength="low",
            claim_type="descriptive",
        )
        session.add(conflicting_version)
        await session.flush()
        conflicting.current_version_id = conflicting_version.id
        session.add(
            UsageConstraint(
                pattern_version_id=conflicting_version.id,
                allowed_sections=["INTRO"],
                allowed_genres=["RESEARCH_ARTICLE"],
            )
        )
        proprietary = await session.scalar(select(License).where(License.code == "PROPRIETARY"))
        assert proprietary is not None
        session.add_all(
            [
                EvidenceProvenance(
                    pattern_version_id=conflicting_version.id,
                    source_type="authored",
                    sentence_ids=[],
                ),
                EvidenceProvenance(
                    pattern_version_id=conflicting_version.id,
                    source_type="mined",
                    sentence_ids=[],
                    license_id=proprietary.id,
                ),
            ]
        )
        client, key = await create_api_key(session, name="recommendation client", role="client")
        await session.commit()

    response = await api_client.post(
        "/v1/recommendations",
        headers={"X-API-Key": key},
        json={
            "intent": "INTRO_GAP_INDICATE",
            "section": "INTRO",
            "genre": "RESEARCH_ARTICLE",
            "journal_id": None,
            "claim_type": "descriptive",
            "evidence_level": "multiple_consistent",
            "discipline": None,
            "limit": 10,
        },
    )

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    body = response.json()
    assert body["items"]
    frames = {item["canonical_frame"] for item in body["items"]}
    assert "There is limited evidence about {topic}." not in frames
    assert "The findings may relate to {context}." not in frames
    assert "Prior work has rarely examined {topic}." not in frames
    assert "Unprovenanced phrase {topic}." not in frames
    assert "Conflicting provenance phrase {topic}." not in frames
    for item in body["items"]:
        assert set(item) >= {
            "pattern_version_id",
            "canonical_frame",
            "score",
            "breakdown",
            "fallback_tier",
            "explanations",
        }
        assert item["breakdown"]["discipline"] is None
        assert item["breakdown"]["journal_genre"] is None
    assert body["policy_versions"] == {
        "ranking_weights": "0.1.0",
        "evidence_matrix": "0.1.0",
    }

    async with session_factory() as session:
        log = await session.get(RecommendationLog, UUID(body["recommendation_id"]))
        assert log is not None
        assert log.request["intent"] == "INTRO_GAP_INDICATE"
        assert log.results["items"]


@pytest.mark.asyncio
async def test_validation_http_runs_v02_and_blocks_prove_with_single_study(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await run_seed_in_session(session_factory)
    _, key = await create_key(session_factory, "client", "validation client")
    response = await api_client.post(
        "/v1/validate",
        headers={"X-API-Key": key},
        json={
            "text": "This proves the intervention caused the outcome.",
            "claim_type": "causal",
            "evidence_level": "single_study",
            "epistemic_strength": "absolute",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    body = response.json()
    serialized = str(body).casefold()
    assert "v02" in serialized
    assert "block" in serialized


async def _create_candidate(session_factory: async_sessionmaker) -> UUID:
    async with session_factory() as session:
        intent = await session.scalar(select(Intent).limit(1))
        license_row = await session.scalar(select(License).where(License.code == "CC-BY"))
        assert license_row is not None
        article = Article(license_id=license_row.id, blob_key="phase04/test.txt", title="Test")
        session.add(article)
        await session.flush()
        section = ArticleSection(
            article_id=article.id,
            section_code="INTRO",
            heading="Introduction",
            order=1,
        )
        session.add(section)
        await session.flush()
        sentence = Sentence(
            article_id=article.id,
            article_section_id=section.id,
            text="The study reports a result.",
            char_start=0,
            char_end=28,
        )
        session.add(sentence)
        await session.flush()
        candidate = Candidate(
            canonical_frame="The results {verb} that {finding}.",
            slots={"finding": "clause"},
            intent_id=intent.id if intent is not None else None,
            confidence=0.8,
            epistemic_strength="moderate",
            source_sentence_ids=[sentence.id],
            status="pending",
        )
        session.add(candidate)
        await session.commit()
        return candidate.id


async def _version_count(session_factory: async_sessionmaker) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(PatternVersion)) or 0


async def _decision_payload(api_client: AsyncClient, key: str, candidate_id: UUID, decision: str):
    return await api_client.post(
        f"/v1/admin/review-queue/{candidate_id}/decisions",
        headers={"X-API-Key": key},
        json={"decision": decision, "comment": "phase 04 review contract"},
    )


@pytest.mark.asyncio
async def test_candidate_requires_two_approvals_before_version_promotion(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await run_seed_in_session(session_factory)
    _, key = await create_key(session_factory, "reviewer", "two-round reviewer")
    candidate_id = await _create_candidate(session_factory)
    before = await _version_count(session_factory)

    first = await _decision_payload(api_client, key, candidate_id, "approve")
    assert first.status_code in {200, 201}
    assert await _version_count(session_factory) == before

    second = await _decision_payload(api_client, key, candidate_id, "approve")
    assert second.status_code in {200, 201}
    assert await _version_count(session_factory) == before + 1
    async with session_factory() as session:
        decisions = list(
            await session.scalars(
                select(ReviewDecision)
                .where(ReviewDecision.candidate_id == candidate_id)
                .order_by(ReviewDecision.round)
            )
        )
        candidate = await session.get(Candidate, candidate_id)
        assert [decision.round for decision in decisions] == [1, 2]
        assert [decision.decision for decision in decisions] == ["approve", "approve"]
        assert candidate is not None and candidate.status == "accepted"


@pytest.mark.asyncio
async def test_candidate_rejection_never_creates_pattern_version(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await run_seed_in_session(session_factory)
    _, key = await create_key(session_factory, "reviewer", "reject reviewer")
    candidate_id = await _create_candidate(session_factory)
    before = await _version_count(session_factory)

    response = await _decision_payload(api_client, key, candidate_id, "reject")

    assert response.status_code in {200, 201}
    assert await _version_count(session_factory) == before
    async with session_factory() as session:
        candidate = await session.get(Candidate, candidate_id)
        decision = await session.scalar(
            select(ReviewDecision).where(ReviewDecision.candidate_id == candidate_id)
        )
        assert candidate is not None and candidate.status == "rejected"
        assert decision is not None and decision.decision == "reject"


@pytest.mark.asyncio
async def test_concurrent_approvals_create_at_most_one_promotion_after_two_rounds(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await run_seed_in_session(session_factory)
    _, key = await create_key(session_factory, "reviewer", "concurrent reviewer")
    candidate_id = await _create_candidate(session_factory)
    before = await _version_count(session_factory)

    responses = await asyncio.gather(
        _decision_payload(api_client, key, candidate_id, "approve"),
        _decision_payload(api_client, key, candidate_id, "approve"),
    )

    assert all(response.status_code in {200, 201, 409} for response in responses)
    async with session_factory() as session:
        decisions = list(
            await session.scalars(
                select(ReviewDecision)
                .where(ReviewDecision.candidate_id == candidate_id)
                .order_by(ReviewDecision.round)
            )
        )
        after = await session.scalar(select(func.count()).select_from(PatternVersion)) or 0
        candidate = await session.get(Candidate, candidate_id)
        assert after in {before, before + 1}
        if after == before + 1:
            assert [decision.round for decision in decisions] == [1, 2]
            assert all(decision.decision == "approve" for decision in decisions)
            assert candidate is not None and candidate.status == "accepted"
        else:
            assert len(decisions) < 2


async def run_seed_in_session(session_factory: async_sessionmaker) -> None:
    async with session_factory() as session:
        await run_seed(session)
        await session.commit()
