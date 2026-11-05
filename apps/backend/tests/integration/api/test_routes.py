"""Phase 04 API contract tests derived from SCAFFOLD_PRD sections 7 and 10."""

import asyncio
import hashlib
import re
from collections import Counter
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
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
from aprkb.modules.gold.labelers import GoldLabelingQuotaError, GoldLabelingRequestError
from aprkb.modules.gold.labels import GoldLabels
from aprkb.modules.gold.models import GoldItem
from aprkb.modules.gold.service import delete_sample_batch, label_sample_batch
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
from aprkb.modules.recommendation.models import Feedback, RecommendationLog
from aprkb.modules.taxonomy.models import Intent
from aprkb.policies.loader import load_policy_bundle
from aprkb.seeds.load import run_seed
from tests.seed_data import seed_legacy_pattern_fixtures


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
        ("/v1/auth/me", "get"),
        ("/v1/auth/demo-session", "post"),
        ("/v1/taxonomy", "get"),
        ("/v1/taxonomy/releases", "get"),
        ("/v1/taxonomy/reference-options", "get"),
        ("/v1/patterns", "get"),
        ("/v1/patterns/versions/{id}", "get"),
        ("/v1/patterns/{id}", "get"),
        ("/v1/patterns/{id}/versions", "get"),
        ("/v1/patterns", "post"),
        ("/v1/patterns/{id}/versions", "post"),
        ("/v1/patterns/{id}/retire", "post"),
        ("/v1/recommendations", "post"),
        ("/v1/render", "post"),
        ("/v1/validate", "post"),
        ("/v1/feedback", "post"),
        ("/v1/reference-library/categories", "get"),
        ("/v1/reference-library/categories/{id}", "get"),
        ("/v1/reference-library/search", "get"),
        ("/v1/journals", "get"),
        ("/v1/journals/{id}", "get"),
        ("/v1/journals/{id}/guidelines", "post"),
        ("/v1/admin/review-queue", "get"),
        ("/v1/admin/review-queue/{id}/intent", "put"),
        ("/v1/admin/review-queue/{id}/decisions", "post"),
        ("/v1/admin/gold/samples", "post"),
        ("/v1/admin/gold/samples/{id}/label", "post"),
        ("/v1/admin/gold/items", "get"),
        ("/v1/admin/gold/items/{id}", "get"),
        ("/v1/admin/gold/items/{id}/review", "post"),
        ("/v1/admin/gold/stats", "get"),
        ("/v1/admin/corpus/articles", "post"),
        ("/v1/admin/corpus/articles/{id}/mine", "post"),
        ("/v1/admin/corpus/imports", "post"),
        ("/v1/admin/corpus/import-profiles", "get"),
        ("/v1/admin/corpus/import-profiles", "post"),
        ("/v1/admin/corpus/import-profiles/{id}", "get"),
        ("/v1/admin/corpus/import-profiles/{id}", "patch"),
        ("/v1/admin/corpus/sources/slr/taxonomy", "get"),
        # ADR-0009 extraction page.
        ("/v1/admin/corpus/batches", "get"),
        ("/v1/admin/corpus/articles", "get"),
        ("/v1/admin/corpus/articles/{id}/text", "get"),
        ("/v1/admin/corpus/mine", "post"),
        ("/v1/admin/extraction/phrases", "get"),
        ("/v1/admin/extraction/phrases/decisions", "post"),
        ("/v1/admin/extraction/phrases/{id}/decision", "post"),
        ("/v1/admin/jobs/{id}", "get"),
        ("/v1/admin/api-keys", "post"),
        ("/v1/admin/api-keys", "get"),
        ("/v1/admin/api-keys", "delete"),
        ("/v1/admin/releases/{id}/publish", "post"),
        ("/v1/vocabulary/families", "get"),
        ("/v1/vocabulary/lemmas", "get"),
        ("/v1/vocabulary/letters", "get"),
        ("/v1/vocabulary/lemmas/{id}", "get"),
        ("/v1/admin/vocabulary/imports", "get"),
        ("/v1/admin/vocabulary/imports", "post"),
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
    sections = {item["code"]: item for item in tree.json()["sections"]}
    assert sections["INTRO"]["compatible_genres"] == [
        "RESEARCH_ARTICLE",
        "SYSTEMATIC_REVIEW",
    ]
    assert sections["DISCUSSION"]["compatible_genres"] == ["RESEARCH_ARTICLE"]


@pytest.mark.asyncio
async def test_genre_section_relationship_rejects_mismatch_and_keeps_empty_results_empty(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await run_seed_in_session(session_factory)
    _, key = await create_key(session_factory, "client", "genre-section client")
    headers = {"X-API-Key": key}
    payload = {
        "intent": "INTRO_GAP_INDICATE",
        "section": "DISCUSSION",
        "genre": "SYSTEMATIC_REVIEW",
        "claim_type": "descriptive",
        "evidence_level": "multiple_consistent",
    }

    incompatible = await api_client.post("/v1/recommendations", headers=headers, json=payload)
    assert incompatible.status_code == 422

    valid_empty = await api_client.post(
        "/v1/recommendations",
        headers=headers,
        json={**payload, "section": "INTRO"},
    )
    assert valid_empty.status_code == 200
    assert valid_empty.json()["items"] == []


@pytest.mark.asyncio
async def test_recommendations_default_to_approved_patterns_and_count_evidence_hidden(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await run_seed_in_session(session_factory)
    _, key = await create_key(session_factory, "client", "writer table client")
    headers = {"X-API-Key": key}

    initial = await api_client.post("/v1/recommendations", headers=headers, json={})
    assert initial.status_code == 200
    assert initial.json()["items"]
    assert all(item["source_type"] in {"authored", "mined"} for item in initial.json()["items"])
    assert all(
        "There is limited evidence about" not in item["canonical_frame"]
        for item in initial.json()["items"]
    )
    assert initial.json()["excluded"].get("GATE_APPROVAL", 0) > 0
    assert all(
        "The findings may relate to" not in item["canonical_frame"]
        for item in initial.json()["items"]
    )
    assert any("Evidence level not selected" in warning for warning in initial.json()["warnings"])

    filtered = await api_client.post(
        "/v1/recommendations",
        headers=headers,
        json={"evidence_level": "single_study"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["excluded"].get("GATE_EVIDENCE", 0) > 0


@pytest.mark.asyncio
async def test_lab_phrasebank_basic_is_listed_and_recommended_from_seeded_db(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await run_seed_in_session(session_factory)
    _, key = await create_key(session_factory, "client", "phrasebank basic client")
    headers = {"X-API-Key": key}
    intent = "METHODS_DESCRIBING_PREVIOUSLY_USED_METHODS"
    expected_frame = "Many researchers have utilised {x} to measure {details}"

    listed = await api_client.get(
        "/v1/patterns",
        params={"section": "METHODS", "intent": intent, "status": "approved", "limit": 200},
        headers=headers,
    )
    assert listed.status_code == 200
    match = next(item for item in listed.json() if item["canonical_frame"] == expected_frame)
    assert set(match["slots"]) == {"x", "details"}
    assert match["intent_name"] == "Describing previously used methods"
    assert match["source_type"] == "authored"

    recommended = await api_client.post(
        "/v1/recommendations",
        headers=headers,
        json={"section": "METHODS", "intent": intent, "genre": "RESEARCH_ARTICLE", "limit": 10},
    )
    assert recommended.status_code == 200
    assert expected_frame in {item["canonical_frame"] for item in recommended.json()["items"]}


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
        usage = await session.scalar(
            select(UsageConstraint).where(UsageConstraint.pattern_version_id == first_version_id)
        )
        provenance = await session.scalar(
            select(EvidenceProvenance).where(
                EvidenceProvenance.pattern_version_id == first_version_id
            )
        )
        assert usage is not None and provenance is not None
        usage.evidence_min = "multiple_consistent"
        usage.forbidden_contexts = ["DISCUSSION"]
        provenance.source_sentence_count = 12
        provenance.occurrence_hash = "invented-hash"
        provenance.source_section_code = "INTRO"
        await session.commit()
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
        for version in versions:
            usage = await session.scalar(
                select(UsageConstraint).where(UsageConstraint.pattern_version_id == version.id)
            )
            provenance = await session.scalar(
                select(EvidenceProvenance).where(
                    EvidenceProvenance.pattern_version_id == version.id
                )
            )
            assert usage is not None and provenance is not None
            assert usage.evidence_min == "multiple_consistent"
            assert usage.forbidden_contexts == ["DISCUSSION"]
            assert provenance.source_sentence_count == 12
            assert provenance.occurrence_hash == "invented-hash"
            assert provenance.source_section_code == "INTRO"
        audit_count = await session.scalar(select(func.count()).select_from(AuditEvent)) or 0
        assert audit_count >= audit_before_append + 1


@pytest.mark.asyncio
async def test_client_pattern_reads_hide_drafts_and_restricted_provenance(
    api_client, session_factory
):
    await run_seed_in_session(session_factory)
    async with session_factory() as session:
        draft = await session.scalar(select(PhrasePattern).where(PhrasePattern.status == "draft"))
        restricted = await session.scalar(
            select(PhrasePattern)
            .join(PatternVersion, PatternVersion.id == PhrasePattern.current_version_id)
            .join(
                EvidenceProvenance,
                EvidenceProvenance.pattern_version_id == PatternVersion.id,
            )
            .join(License, License.id == EvidenceProvenance.license_id)
            .where(License.code == "PROPRIETARY")
        )
        assert draft is not None and restricted is not None
        draft_id = draft.id
        restricted_id = restricted.id
        denied_license = await session.scalar(select(License).where(License.code == "CC-BY-NC"))
        source = await session.scalar(
            select(EvidenceProvenance).where(
                EvidenceProvenance.pattern_version_id == restricted.current_version_id
            )
        )
        assert denied_license is not None and source is not None
        source.license_id = denied_license.id
        await session.commit()

    _, client_key = await create_key(session_factory, "client", "pattern API client")
    _, curator_key = await create_key(session_factory, "curator", "pattern curator")
    client_headers = {"X-API-Key": client_key}
    curator_headers = {"X-API-Key": curator_key}

    client_list = await api_client.get("/v1/patterns", headers=client_headers)
    hidden_draft = await api_client.get(f"/v1/patterns/{draft_id}", headers=client_headers)
    hidden_draft_history = await api_client.get(
        f"/v1/patterns/{draft_id}/versions", headers=client_headers
    )
    hidden_restricted = await api_client.get(
        f"/v1/patterns/{restricted_id}", headers=client_headers
    )
    curator_list = await api_client.get(
        "/v1/patterns", params={"status": "draft"}, headers=curator_headers
    )
    curator_draft = await api_client.get(f"/v1/patterns/{draft_id}", headers=curator_headers)
    curator_history = await api_client.get(
        f"/v1/patterns/{draft_id}/versions", headers=curator_headers
    )

    assert client_list.status_code == 200
    assert all(item["status"] == "approved" for item in client_list.json())
    assert str(restricted_id) not in {item["id"] for item in client_list.json()}
    assert hidden_draft.status_code == 404
    assert hidden_draft_history.status_code == 404
    assert hidden_restricted.status_code == 404
    assert curator_draft.status_code == 200
    assert curator_draft.json()["status"] == "draft"
    assert curator_list.status_code == 200
    assert str(draft_id) in {item["id"] for item in curator_list.json()}
    assert curator_history.status_code == 200
    assert len(curator_history.json()) == 1


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
async def test_feedback_is_persisted_and_override_is_unavailable_in_mvp(
    api_client, session_factory
):
    await run_seed_in_session(session_factory)
    client, key = await create_key(session_factory, "client", "feedback client")
    headers = {"X-API-Key": key}
    recommendation = await api_client.post(
        "/v1/recommendations",
        headers=headers,
        json={
            "intent": "INTRO_GAP_INDICATE",
            "section": "INTRO",
            "genre": "RESEARCH_ARTICLE",
            "claim_type": "descriptive",
            "evidence_level": "multiple_consistent",
        },
    )
    assert recommendation.status_code == 200
    recommendation_id = UUID(recommendation.json()["recommendation_id"])
    version_id = UUID(recommendation.json()["items"][0]["pattern_version_id"])
    feedback = await api_client.post(
        "/v1/feedback",
        headers=headers,
        json={
            "recommendation_id": str(recommendation_id),
            "pattern_version_id": str(version_id),
            "signal": "accepted",
            "payload": {"context_hash": "b" * 64},
        },
    )
    assert feedback.status_code in {200, 201}
    override = await api_client.post(
        "/v1/overrides",
        headers=headers,
        json={"validation_id": str(uuid4()), "rule_code": "V02", "rationale": "test"},
    )
    assert override.status_code == 404
    unrelated = await api_client.post(
        "/v1/feedback",
        headers=headers,
        json={
            "recommendation_id": str(recommendation_id),
            "pattern_version_id": str(uuid4()),
            "signal": "accepted",
            "payload": {"context_hash": "b" * 64},
        },
    )
    assert unrelated.status_code == 404
    async with session_factory() as session:
        feedback_row = await session.scalar(
            select(Feedback).where(Feedback.recommendation_id == recommendation_id)
        )
        assert feedback_row is not None
        assert feedback_row.client_id == client.id
        audited_entity_ids = set(
            await session.scalars(
                select(AuditEvent.entity_id).where(AuditEvent.entity_id == feedback_row.id)
            )
        )
        assert audited_entity_ids == {feedback_row.id}


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

    options = await api_client.get(
        "/v1/taxonomy/reference-options", headers={"X-API-Key": keys["client"]}
    )
    assert options.status_code == 200
    assert {item["group"] for item in options.json()} == {
        "claim_type",
        "evidence_level",
        "epistemic_strength",
    }

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
async def test_review_queue_fails_closed_for_legacy_unmasked_candidate(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await run_seed_in_session(session_factory)
    _, key = await create_key(session_factory, "reviewer", "legacy candidate reviewer")
    candidate_id = await _create_candidate(session_factory, unsafe=True)

    response = await api_client.get("/v1/admin/review-queue", headers={"X-API-Key": key})

    assert response.status_code == 409
    assert "The study reports a result" not in response.text
    assert "Candidate slot schema is invalid" in response.text
    decision = await _decision_payload(api_client, key, candidate_id, "approve")
    assert decision.status_code == 409
    assert "The study reports a result" not in decision.text


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
        await seed_legacy_pattern_fixtures(session)
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
    assert all(
        any(explanation.startswith("Evidence: ") for explanation in item["explanations"])
        and any("maximum allowed:" in explanation for explanation in item["explanations"])
        for item in body["items"]
    )
    frames = {item["canonical_frame"] for item in body["items"]}
    assert "There is limited evidence about {topic}." not in frames
    assert "The findings may relate to {context}." not in frames
    assert "Prior work has rarely examined {topic}." in frames
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
            "source_type",
            "version_no",
            "license_code",
            "license_name",
            "license_flag",
            "source_reference",
        }
        assert item["breakdown"]["discipline"] is None
        assert item["breakdown"]["journal_genre"] is None
        assert item["license_flag"] is (item["license_code"] == "PROPRIETARY")
    assert body["policy_versions"] == {
        "ranking_weights": "0.2.0",
        "license_policy": "0.1.0",
        "fallback_tiers": "0.1.0",
        "evidence_matrix": "0.1.0",
        "validation_rules": "0.2.0",
        "epistemic_markers": "0.1.0",
        "taxonomy_release": "0.2.0",
    }

    async with session_factory() as session:
        log = await session.get(RecommendationLog, UUID(body["recommendation_id"]))
        assert log is not None
        assert log.request["intent"] == "INTRO_GAP_INDICATE"
        assert log.results["items"]


@pytest.mark.asyncio
async def test_proprietary_recommendation_is_flagged_for_internal_use(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    async with session_factory() as session:
        await run_seed(session)
        await seed_legacy_pattern_fixtures(session)
        intent = await session.scalar(select(Intent).where(Intent.code == "INTRO_GAP_INDICATE"))
        license_row = await session.scalar(select(License).where(License.code == "PROPRIETARY"))
        assert intent is not None and license_row is not None
        pattern = PhrasePattern(intent_id=intent.id, status="approved")
        session.add(pattern)
        await session.flush()
        version = PatternVersion(
            pattern_id=pattern.id,
            version_no=1,
            canonical_frame="The proprietary fixture suggests {topic}.",
            slots={"topic": "noun_phrase"},
            epistemic_strength="low",
            claim_type="descriptive",
        )
        session.add(version)
        await session.flush()
        pattern.current_version_id = version.id
        session.add_all(
            [
                UsageConstraint(
                    pattern_version_id=version.id,
                    allowed_sections=["INTRO"],
                    allowed_genres=["RESEARCH_ARTICLE"],
                ),
                EvidenceProvenance(
                    pattern_version_id=version.id,
                    source_type="mined",
                    sentence_ids=[],
                    license_id=license_row.id,
                ),
            ]
        )
        _, key = await create_api_key(session, name="internal writer", role="client")
        await session.commit()

    response = await api_client.post(
        "/v1/recommendations",
        headers={"X-API-Key": key},
        json={
            "intent": "INTRO_GAP_INDICATE",
            "section": "INTRO",
            "genre": "RESEARCH_ARTICLE",
            "claim_type": "descriptive",
            "evidence_level": "multiple_consistent",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    item = next(
        item
        for item in response.json()["items"]
        if item["canonical_frame"] == "The proprietary fixture suggests {topic}."
    )
    assert item["license_code"] == "PROPRIETARY"
    assert item["license_flag"] is True

    headers = {"X-API-Key": key}
    for path in (
        f"/v1/patterns/{pattern.id}",
        f"/v1/patterns/versions/{version.id}",
        f"/v1/patterns/{pattern.id}/versions",
    ):
        detail = await api_client.get(path, headers=headers)
        assert detail.status_code == 200, detail.text
    listed = await api_client.get("/v1/patterns", headers=headers)
    assert listed.status_code == 200
    metadata = next(row for row in listed.json() if row["id"] == str(pattern.id))
    assert metadata["license_allows_display"] is False
    assert metadata["license_flag"] is True
    render_payload = {
        "recommendation_id": response.json()["recommendation_id"],
        "pattern_version_id": str(version.id),
        "slots": {"topic": "an invented topic"},
    }
    rendered = await api_client.post("/v1/render", headers=headers, json=render_payload)
    assert rendered.status_code == 200, rendered.text
    assert rendered.json()["text"] == "The proprietary fixture suggests an invented topic."

    # An issued recommendation must not keep access after its source loses permission.
    async with session_factory() as session:
        denied_license = await session.scalar(select(License).where(License.code == "CC-BY-NC"))
        source = await session.scalar(
            select(EvidenceProvenance).where(EvidenceProvenance.pattern_version_id == version.id)
        )
        assert denied_license is not None and source is not None
        source.license_id = denied_license.id
        await session.commit()
    denied = await api_client.post("/v1/render", headers=headers, json=render_payload)
    assert denied.status_code == 404
    denied_detail = await api_client.get(f"/v1/patterns/versions/{version.id}", headers=headers)
    assert denied_detail.status_code == 404
    recommended_again = await api_client.post(
        "/v1/recommendations", headers=headers, json={"limit": 100}
    )
    assert recommended_again.status_code == 200
    assert str(version.id) not in {
        row["pattern_version_id"] for row in recommended_again.json()["items"]
    }


@pytest.mark.asyncio
async def test_pattern_browsing_filters_keyword_and_taxonomy_before_old_200_cap(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await run_seed_in_session(session_factory)
    _, key = await create_key(session_factory, "client", "late pattern reader")
    async with session_factory() as session:
        intent = await session.scalar(select(Intent).where(Intent.code == "INTRO_GAP_INDICATE"))
        assert intent is not None
        final_pattern_id = None
        for index in range(201):
            pattern = PhrasePattern(
                intent_id=intent.id,
                status="approved",
                created_at=datetime(2030, 1, 1, tzinfo=UTC) + timedelta(seconds=index),
            )
            session.add(pattern)
            await session.flush()
            version = PatternVersion(
                pattern_id=pattern.id,
                version_no=1,
                canonical_frame="Late needle phrase" if index == 200 else "Ordinary phrase",
                slots={},
                epistemic_strength="low",
                claim_type="descriptive",
            )
            session.add(version)
            await session.flush()
            pattern.current_version_id = version.id
            session.add_all(
                [
                    UsageConstraint(
                        pattern_version_id=version.id, allowed_sections=["INTRO"], allowed_genres=[]
                    ),
                    EvidenceProvenance(
                        pattern_version_id=version.id, source_type="authored", sentence_ids=[]
                    ),
                ]
            )
            final_pattern_id = pattern.id
        await session.commit()
    response = await api_client.get(
        "/v1/patterns",
        headers={"X-API-Key": key},
        params={"q": "NEEDLE", "section": "INTRO", "intent": "INTRO_GAP_INDICATE", "limit": 1},
    )
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()] == [str(final_pattern_id)]


@pytest.mark.asyncio
async def test_recommendation_search_keeps_query_private_and_uses_honest_journal_fallback(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    async with session_factory() as session:
        await run_seed(session)
        await seed_legacy_pattern_fixtures(session)
        journal = JournalProfile(name="Search fallback journal", issn="2049-3631")
        session.add(journal)
        _, key = await create_api_key(session, name="search client", role="client")
        await session.commit()

    payload = {
        "intent": "INTRO_GAP_INDICATE",
        "section": "INTRO",
        "genre": "RESEARCH_ARTICLE",
        "journal_id": str(journal.id),
        "claim_type": "descriptive",
        "evidence_level": "multiple_consistent",
        "query": "underexplored",
    }
    response = await api_client.post(
        "/v1/recommendations", headers={"X-API-Key": key}, json=payload
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert all(item["fallback_tier"] == "generic_genre" for item in body["items"])
    assert all("underexplored" in item["canonical_frame"] for item in body["items"])
    assert body["fallback_reason"]
    async with session_factory() as session:
        log = await session.get(RecommendationLog, UUID(body["recommendation_id"]))
        assert log is not None
        assert "query" not in log.request
        assert log.request["query_hash"]
        assert "underexplored" not in str(log.request)

    wildcard_response = await api_client.post(
        "/v1/recommendations",
        headers={"X-API-Key": key},
        json={**payload, "query": "%"},
    )
    assert wildcard_response.status_code == 200
    assert wildcard_response.json()["items"] == []


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
    assert body["complete"] is False
    assert "V01" in body["checks_unavailable"]
    v02 = next(rule for rule in body["rules"] if rule["code"] == "V02")
    assert v02["applied"] is True
    assert v02["recommended_action"]


@pytest.mark.asyncio
async def test_render_uses_approved_version_and_validates_slots(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await run_seed_in_session(session_factory)
    _, key = await create_key(session_factory, "client", "render client")
    async with session_factory() as session:
        approved = await session.scalar(
            select(PatternVersion).where(PatternVersion.canonical_frame.like("The role of %"))
        )
        restricted = await session.scalar(
            select(PatternVersion).where(
                PatternVersion.canonical_frame.like("Prior work has rarely %")
            )
        )
        assert approved is not None and restricted is not None
        denied_license = await session.scalar(select(License).where(License.code == "CC-BY-NC"))
        source = await session.scalar(
            select(EvidenceProvenance).where(EvidenceProvenance.pattern_version_id == restricted.id)
        )
        assert denied_license is not None and source is not None
        source.license_id = denied_license.id
        await session.commit()

    endpoint = "/v1/render"
    headers = {"X-API-Key": key}
    recommendation = await api_client.post(
        "/v1/recommendations",
        headers=headers,
        json={
            "intent": "INTRO_GAP_INDICATE",
            "section": "INTRO",
            "genre": "RESEARCH_ARTICLE",
            "claim_type": "descriptive",
            "evidence_level": "multiple_consistent",
        },
    )
    assert recommendation.status_code == 200
    assert str(approved.id) in {
        item["pattern_version_id"] for item in recommendation.json()["items"]
    }
    detail = await api_client.get(f"/v1/patterns/versions/{approved.id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["slots"]["topic"]["type"] == "noun_phrase"
    payload = {
        "recommendation_id": recommendation.json()["recommendation_id"],
        "pattern_version_id": str(approved.id),
        "slots": {"topic": "language models", "context": "education"},
    }
    response = await api_client.post(endpoint, headers=headers, json=payload)
    assert response.status_code == 200
    assert response.json()["text"] == (
        "The role of language models in education remains underexplored."
    )
    assert response.json()["unfilled_slots"] == []

    invalid = await api_client.post(
        endpoint, headers=headers, json={**payload, "slots": {"topic": "AI"}}
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["details"]["field_errors"] == {
        "topic": "Enter at least 3 characters.",
        "context": "This field is required.",
    }

    extra = await api_client.post(
        endpoint, headers=headers, json={**payload, "slots": {"unexpected": "x"}}
    )
    assert extra.status_code == 422
    forbidden = await api_client.post(
        endpoint,
        headers=headers,
        json={**payload, "pattern_version_id": str(restricted.id), "slots": {}},
    )
    assert forbidden.status_code == 404
    hidden_detail = await api_client.get(f"/v1/patterns/versions/{restricted.id}", headers=headers)
    assert hidden_detail.status_code == 404


@pytest.mark.asyncio
async def test_feedback_rejects_raw_writer_text(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await run_seed_in_session(session_factory)
    _, key = await create_key(session_factory, "client", "privacy client")
    response = await api_client.post(
        "/v1/feedback",
        headers={"X-API-Key": key},
        json={
            "recommendation_id": str(uuid4()),
            "pattern_version_id": str(uuid4()),
            "signal": "edited",
            "payload": {"raw_text": "My unpublished sentence"},
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validation_checks_writer_provided_grounding_and_keeps_v05_unavailable(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await run_seed_in_session(session_factory)
    _, key = await create_key(session_factory, "client", "validation grounding client")
    response = await api_client.post(
        "/v1/validate",
        headers={"X-API-Key": key},
        json={
            "text": "The result was significant (p < 0.05) with a rate of 45%.",
            "claim_type": "descriptive",
            "evidence_level": "multiple_consistent",
            "context": "study context",
            "slots": {"topic": "language models"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    v03 = next(rule for rule in body["rules"] if rule["code"] == "V03")
    assert v03["severity"] == "block"
    assert v03["applied"] is True
    assert v03["span"] is not None
    assert "V05" in body["checks_unavailable"]


async def _create_candidate(session_factory: async_sessionmaker, *, unsafe: bool = False) -> UUID:
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
            canonical_frame=(
                "[X] The study reports a result that [Y]." if unsafe else "[X] report that [Y]."
            ),
            slots=(
                {"finding": "source wording"}
                if unsafe
                else {
                    "X": {"type": "noun_phrase", "signals": []},
                    "Y": {"type": "clause", "signals": []},
                }
            ),
            intent_id=intent.id if intent is not None else None,
            confidence=0.8,
            epistemic_strength="moderate",
            source_sentence_ids=[sentence.id],
            status="pending",
        )
        session.add(candidate)
        await session.commit()
        return candidate.id


@pytest.mark.asyncio
async def test_original_reviewer_can_complete_legacy_missing_intent(api_client, session_factory):
    await run_seed_in_session(session_factory)
    first_reviewer, first_key = await create_key(
        session_factory, "reviewer", "legacy first reviewer"
    )
    _, other_key = await create_key(session_factory, "reviewer", "legacy second reviewer")
    candidate_id = await _create_candidate(session_factory)
    async with session_factory() as session:
        candidate = await session.get(Candidate, candidate_id)
        assert candidate is not None
        intent_id = candidate.intent_id
        candidate.intent_id = None
        # Older code allowed approving the phrase before an intent had been assigned.
        session.add(
            ReviewDecision(
                candidate_id=candidate_id,
                round=1,
                decision="approve",
                reviewer_id=first_reviewer.id,
            )
        )
        await session.commit()
    path = f"/v1/admin/review-queue/{candidate_id}/intent"
    payload = {"intent_id": str(intent_id)}
    denied = await api_client.put(path, headers={"X-API-Key": other_key}, json=payload)
    assert denied.status_code == 409
    confirmed = await api_client.put(path, headers={"X-API-Key": first_key}, json=payload)
    assert confirmed.status_code == 200, confirmed.text
    frozen = await api_client.put(path, headers={"X-API-Key": first_key}, json=payload)
    assert frozen.status_code == 409
    async with session_factory() as session:
        event = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "candidate.intent.update",
                AuditEvent.entity_id == candidate_id,
            )
        )
        assert event is not None and event.after["first_reviewer_confirmed_intent"] is True
    second = await _decision_payload(api_client, other_key, candidate_id, "approve")
    assert second.status_code == 200, second.text
    assert second.json()["candidate_status"] == "accepted"


async def _version_count(session_factory: async_sessionmaker) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(PatternVersion)) or 0


@pytest.mark.asyncio
async def test_gold_sampling_stores_only_sentence_reference_hash_and_audits_counts(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await run_seed_in_session(session_factory)
    _, key = await create_key(session_factory, "curator", "gold sampler")
    source_text = "The sample method improves a fictional result."
    async with session_factory() as session:
        license_row = await session.scalar(select(License).where(License.code == "CC-BY"))
        assert license_row is not None and license_row.allows_mining
        article = Article(
            source="slr",
            license_id=license_row.id,
            blob_key="phase02/mock-article.md",
            title="Mock Article",
            ingest_status="ready",
        )
        session.add(article)
        await session.flush()
        section = ArticleSection(
            article_id=article.id,
            section_code="RESULTS",
            heading="Results",
            order=1,
        )
        session.add(section)
        await session.flush()
        sentence = Sentence(
            article_id=article.id,
            article_section_id=section.id,
            text=source_text,
            char_start=0,
            char_end=len(source_text),
        )
        session.add(sentence)
        upload_article = Article(
            source="upload",
            license_id=license_row.id,
            blob_key="phase02/mock-upload.md",
            title="Mock Upload",
            ingest_status="ready",
        )
        session.add(upload_article)
        await session.flush()
        upload_sentence = Sentence(
            article_id=upload_article.id,
            text="An allowed upload sentence is outside the SLR sample.",
            char_start=0,
            char_end=len("An allowed upload sentence is outside the SLR sample."),
        )
        session.add(upload_sentence)
        blocked_license = License(
            code="TEST-NO-MINING", name="Test license", allows_mining=False, allows_display=False
        )
        session.add(blocked_license)
        await session.flush()
        blocked_article = Article(
            license_id=blocked_license.id,
            blob_key="phase02/mock-restricted.md",
            title="Restricted Mock Article",
            ingest_status="ready",
        )
        session.add(blocked_article)
        await session.flush()
        blocked_sentence = Sentence(
            article_id=blocked_article.id,
            text="A restricted mock sentence remains excluded.",
            char_start=0,
            char_end=len("A restricted mock sentence remains excluded."),
        )
        session.add(blocked_sentence)
        await session.commit()

    response = await api_client.post(
        "/v1/admin/gold/samples",
        headers={"X-API-Key": key},
        json={"size": 1, "seed": 741, "max_per_article": 1},
    )

    assert response.status_code == 202
    assert source_text not in response.text
    async with session_factory() as session:
        item = await session.scalar(
            select(GoldItem).where(GoldItem.sample_batch == response.json()["sample_batch"])
        )
        assert item is not None
        assert item.sentence_id == sentence.id
        assert item.sentence_id != blocked_sentence.id
        assert item.sentence_id != upload_sentence.id
        assert item.text_sha256
        audit = await session.scalar(
            select(AuditEvent).where(AuditEvent.action == "gold.sample.create")
        )
        assert audit is not None
        assert source_text not in str(audit.after)
        assert audit.after["filtered_count"] == 0
        assert audit.after["sampling_policy_version"] == load_policy_bundle().gold_sampling.version
        batch = response.json()["sample_batch"]
        # The only eligible sentence is already sampled, so it must not be drawn again.
        again = await api_client.post(
            "/v1/admin/gold/samples",
            headers={"X-API-Key": key},
            json={"size": 1, "seed": 742, "max_per_article": 1},
        )
        assert again.status_code == 422
        item.ai_labels = {"keep": True}
        await session.commit()
        with pytest.raises(ValueError, match="contains labels"):
            await delete_sample_batch(
                session, sample_batch=batch, request_id="test-gold-delete-blocked"
            )

    async with session_factory() as session:
        item = await session.scalar(select(GoldItem).where(GoldItem.sample_batch == batch))
        assert item is not None
        item.ai_labels = None
        await session.commit()
        deleted_count = await delete_sample_batch(
            session, sample_batch=batch, request_id="test-gold-delete"
        )
        assert deleted_count == 1

        remaining = await session.scalar(select(GoldItem).where(GoldItem.sample_batch == batch))
        assert remaining is None
        delete_audit = await session.scalar(
            select(AuditEvent).where(AuditEvent.action == "gold.sample.delete")
        )
        assert delete_audit is not None
        assert delete_audit.after == {"deleted_count": 1}
        assert source_text not in str(delete_audit.before)
        assert source_text not in str(delete_audit.after)


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
        await seed_legacy_pattern_fixtures(session)
        await session.commit()


@pytest.mark.asyncio
async def test_gold_review_displays_only_allowed_source_and_audits_label_fields(
    api_client: AsyncClient, session_factory: async_sessionmaker
) -> None:
    await run_seed_in_session(session_factory)
    reviewer, key = await create_key(session_factory, "reviewer", "gold final reviewer")
    source = "Our small fixture shows that the example system works reliably."
    async with session_factory() as session:
        license_row = await session.scalar(select(License).where(License.code == "CC-BY"))
        assert license_row is not None and license_row.allows_display
        article = Article(
            source="slr",
            license_id=license_row.id,
            blob_key="gold/mock-review.md",
            title="Self-authored review fixture",
            ingest_status="ready",
        )
        session.add(article)
        await session.flush()
        section = ArticleSection(
            article_id=article.id, section_code="RESULTS", heading="Results", order=0
        )
        session.add(section)
        await session.flush()
        sentence = Sentence(
            article_id=article.id,
            article_section_id=section.id,
            text=source,
            char_start=0,
            char_end=len(source),
        )
        session.add(sentence)
        await session.flush()
        item = GoldItem(
            article_id=article.id,
            sentence_id=sentence.id,
            char_start=0,
            char_end=len(source),
            text_sha256=hashlib.sha256(source.encode()).hexdigest(),
            section_at_sampling="RESULTS",
            split="dev",
            sample_batch="mock-review-batch",
            guideline_version="v0",
            ai_labels={"keep": True, "section": "RESULTS", "slots": []},
            status="draft",
        )
        session.add(item)
        await session.commit()
        item_id = item.id

    headers = {"X-API-Key": key}
    listed = await api_client.get("/v1/admin/gold/items?status=draft", headers=headers)
    assert listed.status_code == 200
    assert source not in listed.text
    detail = await api_client.get(f"/v1/admin/gold/items/{item_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["text"] == source
    decision = await api_client.post(
        f"/v1/admin/gold/items/{item_id}/review",
        headers=headers,
        json={
            "decision": "approve",
            "final_labels": {"keep": True, "section": "RESULTS", "slots": []},
        },
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"
    async with session_factory() as session:
        item = await session.get(GoldItem, item_id)
        event = await session.scalar(
            select(AuditEvent).where(AuditEvent.action == "gold.item.review")
        )
        assert item is not None and item.reviewed_by == reviewer.id
        assert event is not None and source not in str(event.after)


class _QuotaAfterTwoLabeler:
    """Fake labeler: labels two sentences, then reports an exhausted daily quota."""

    model = "fake-model"
    prompt_version = "fake-v0"
    total_tokens = 321

    def __init__(self, *, error: Exception) -> None:
        self.calls = 0
        self._error = error

    async def label(self, **kwargs: object) -> GoldLabels:
        self.calls += 1
        if self.calls > 2:
            raise self._error
        return GoldLabels(keep=True, section="RESULTS", frame=str(kwargs["sentence"]))


async def _seed_unlabeled_gold_batch(session_factory: async_sessionmaker, count: int) -> str:
    async with session_factory() as session:
        license_row = await session.scalar(select(License).where(License.code == "CC-BY"))
        assert license_row is not None
        article = Article(
            source="slr",
            license_id=license_row.id,
            blob_key="gold/mock-quota.md",
            title="Self-authored quota fixture",
            ingest_status="ready",
        )
        session.add(article)
        await session.flush()
        section = ArticleSection(
            article_id=article.id, section_code="RESULTS", heading="Results", order=0
        )
        session.add(section)
        await session.flush()
        offset = 0
        for index in range(count):
            text = f"Fixture sentence number {index} describes a mock result."
            sentence = Sentence(
                article_id=article.id,
                article_section_id=section.id,
                text=text,
                char_start=offset,
                char_end=offset + len(text),
            )
            session.add(sentence)
            await session.flush()
            session.add(
                GoldItem(
                    article_id=article.id,
                    sentence_id=sentence.id,
                    char_start=offset,
                    char_end=offset + len(text),
                    text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                    section_at_sampling="RESULTS",
                    split="dev",
                    sample_batch="mock-quota-batch",
                    guideline_version="v0",
                    status="pending_ai",
                )
            )
            offset += len(text) + 1
        await session.commit()
    return "mock-quota-batch"


@pytest.mark.asyncio
async def test_gold_labeling_keeps_finished_labels_when_daily_quota_runs_out(
    session_factory: async_sessionmaker,
) -> None:
    await run_seed_in_session(session_factory)
    batch = await _seed_unlabeled_gold_batch(session_factory, 5)
    labeler = _QuotaAfterTwoLabeler(error=GoldLabelingQuotaError(7200))

    async with session_factory() as session:
        result = await label_sample_batch(
            session, sample_batch=batch, request_id="test", labeler=labeler
        )

    assert result == {
        "labeled_count": 2,
        "stale_count": 0,
        "tokens_used": 321,
        "stopped": "quota",
        "remaining_count": 3,
        "retry_after_seconds": 7200,
    }
    async with session_factory() as session:
        statuses = Counter(await session.scalars(select(GoldItem.status)))
    assert statuses == {"draft": 2, "pending_ai": 3}


@pytest.mark.asyncio
async def test_gold_labeling_keeps_finished_labels_before_raising_other_request_errors(
    session_factory: async_sessionmaker,
) -> None:
    await run_seed_in_session(session_factory)
    batch = await _seed_unlabeled_gold_batch(session_factory, 4)
    labeler = _QuotaAfterTwoLabeler(error=GoldLabelingRequestError("Groq credentials rejected"))

    async with session_factory() as session:
        with pytest.raises(GoldLabelingRequestError):
            await label_sample_batch(
                session, sample_batch=batch, request_id="test", labeler=labeler
            )

    async with session_factory() as session:
        statuses = Counter(await session.scalars(select(GoldItem.status)))
    assert statuses == {"draft": 2, "pending_ai": 2}
