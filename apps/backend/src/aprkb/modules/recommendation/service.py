"""Database-backed recommendation request orchestration."""

import json
from hashlib import sha256
from uuid import UUID

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.audit.service import record_event
from aprkb.modules.discipline.null_source import NullDisciplineSource
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.journals import repository as journal_repository
from aprkb.modules.journals import service as journal_service
from aprkb.modules.journals.guideline_policy import GuidelinePolicy
from aprkb.modules.recommendation import repository
from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.fallback import FallbackTierLoader, choose_fallback_tier
from aprkb.modules.recommendation.gates import build_gates
from aprkb.modules.recommendation.models import RecommendationLog
from aprkb.modules.recommendation.pattern_view import PatternView
from aprkb.modules.recommendation.pipeline import RecommendationPipeline
from aprkb.modules.recommendation.schemas import RecommendationRequest
from aprkb.modules.recommendation.scorers import build_scorers
from aprkb.modules.taxonomy import repository as taxonomy_repository
from aprkb.modules.taxonomy import service as taxonomy_service
from aprkb.policies.evidence import EvidencePolicy
from aprkb.policies.loader import PolicyBundle

CRITERION_LABELS = {
    "discipline": "Discipline",
    "journal_genre": "Journal and genre",
    "evidence": "Evidence",
    "linguistic": "Keyword match",
    "provenance": "Provenance",
}


def score_explanations(
    breakdown: dict[str, float | None],
    *,
    claim_type: str | None,
    strength: str | None,
    evidence_level: str | None,
    evidence_policy: EvidencePolicy,
) -> list[str]:
    """Describe each measured score using its actual value and evidence ceiling."""
    explanations = [
        f"{CRITERION_LABELS[key]}: {value:.3f}"
        if value is not None
        else f"{CRITERION_LABELS[key]}: not available"
        for key, value in breakdown.items()
    ]
    if evidence_level is not None:
        try:
            maximum = evidence_policy.max_strength(claim_type or "", evidence_level)
        except ValueError:
            maximum = "not available"
        explanations.append(
            f"Evidence strength: {strength or 'Not labelled'}; maximum allowed: {maximum}"
        )
    return explanations


async def require_issued_candidate(
    session: AsyncSession,
    *,
    recommendation_id: UUID,
    pattern_version_id: UUID,
    client_id: UUID,
) -> None:
    """FR-07.5 / FR-07.7: bind render/feedback to a result issued to this client and version."""
    log = await session.get(RecommendationLog, recommendation_id)
    items = log.results.get("items", []) if log is not None else []
    if (
        log is None
        or log.created_by != client_id
        or not isinstance(items, list)
        or not any(
            isinstance(item, dict) and item.get("pattern_version_id") == str(pattern_version_id)
            for item in items
        )
    ):
        raise HTTPException(status_code=404, detail="Recommendation candidate not found")


async def recommend(
    session: AsyncSession,
    *,
    payload: RecommendationRequest,
    actor: ApiClient,
    request_id: str,
    policy_bundle: PolicyBundle,
) -> dict[str, object]:
    """FR-07.1–.4: retrieve, gate, rank and log suggestions with explanation/fallback (BR-08)."""
    # Blank optional context has the same meaning in SQL, gates and warnings.
    payload = payload.model_copy(
        update={
            field: None
            for field in ("intent", "move", "section")
            if (value := getattr(payload, field)) is not None and not value.strip()
        }
    )
    if (
        payload.genre is not None
        and payload.section is not None
        and not await taxonomy_service.is_genre_section_compatible(
            session, genre_code=payload.genre, section_code=payload.section
        )
    ):
        raise HTTPException(status_code=422, detail="Genre and section are not compatible")
    try:
        evidence_policy = EvidencePolicy.from_reference_enums(
            policy_bundle.evidence_matrix, await repository.reference_strengths(session)
        )
    except ValueError as error:
        raise HTTPException(
            status_code=503, detail="Evidence reference data is unavailable"
        ) from error
    if payload.journal_id is not None:
        await journal_service.get_journal(session, payload.journal_id)
    guideline_policy = GuidelinePolicy()
    if payload.journal_id is not None:
        guidelines = await journal_repository.list_active_mandatory_guidelines(
            session, payload.journal_id
        )
        guideline_policy.set(
            payload.journal_id,
            tuple(
                {"rule_type": row.rule_type, "payload": row.payload, "is_mandatory": True}
                for row in guidelines
            ),
        )
    query = payload.query.strip() if payload.query else None
    rows = await repository.load_pattern_rows(
        session,
        intent_code=payload.intent,
        query=query or None,
        move_code=payload.move,
        claim_type=payload.claim_type,
        genre_code=payload.genre,
        internal_use_codes=frozenset(policy_bundle.license.internal_use_codes),
    )
    by_tier: dict[str, list[PatternView]] = {
        tier: [] for tier in policy_bundle.fallback_tiers.tiers
    }
    for row in rows:
        allowed_genres = tuple(row.allowed_genres)
        tier = choose_fallback_tier(policy_bundle.fallback_tiers.tiers)
        if tier is None:
            continue
        by_tier[tier].append(
            PatternView(
                pattern_version_id=row.current_version_id,
                status=row.status,
                intent_code=row.intent_code,
                canonical_frame=row.canonical_frame,
                claim_type=row.claim_type,
                epistemic_strength=row.epistemic_strength,
                allowed_sections=tuple(row.allowed_sections),
                allowed_genres=allowed_genres,
                source_type=row.source_type,
                license_allows_display=(
                    row.source_type == "authored"
                    or (
                        row.source_type == "mined"
                        and (row.license_allows_display or row.license_flag)
                    )
                ),
                license_flag=row.license_flag,
                version_no=row.version_no,
                license_code=row.license_code,
                license_name=row.license_name,
                source_reference=row.source_reference,
                article_id=row.article_id,
                evidence_min=row.evidence_min,
                forbidden_contexts=tuple(row.forbidden_contexts),
            )
        )
    context = RecommendationContext(
        intent_code=payload.intent,
        section_code=payload.section,
        genre_code=payload.genre,
        journal_id=payload.journal_id,
        claim_type=payload.claim_type,
        evidence_level=payload.evidence_level,
        discipline_code=payload.discipline,
        client_id=actor.id,
        limit=payload.limit,
        query=query,
    )
    pipeline = RecommendationPipeline(
        gates=build_gates(evidence_policy=evidence_policy, guideline_policy=guideline_policy),
        scorers=build_scorers(
            discipline_source=NullDisciplineSource(),
            evidence_policy=evidence_policy,
            ranking_policy=policy_bundle.ranking_weights,
        ),
        weights=policy_bundle.ranking_weights.weights,
        tier_loader=FallbackTierLoader(tiers=policy_bundle.fallback_tiers.tiers, by_tier=by_tier),
    )
    result = pipeline.recommend(context)
    fallback_reason = (
        "No verified journal-specific recommendation data; using generic patterns"
        if payload.journal_id is not None
        else None
    )
    versions = {
        "ranking_weights": policy_bundle.ranking_weights.version,
        "license_policy": policy_bundle.license.version,
        "fallback_tiers": policy_bundle.fallback_tiers.version,
        "evidence_matrix": policy_bundle.evidence_matrix.version,
        "validation_rules": policy_bundle.validation_rules.version,
        "epistemic_markers": policy_bundle.epistemic_markers.version,
    }
    taxonomy_release = await taxonomy_repository.published_release(session)
    versions["taxonomy_release"] = taxonomy_release.version if taxonomy_release else "unpublished"
    warnings = []
    if not payload.intent and not payload.move and not query:
        warnings.append("Không có intent/move/query; kết quả là toàn bộ pattern được duyệt")
    if not payload.section:
        warnings.append("Section không được lọc")
    if payload.evidence_level is None:
        warnings.append("Evidence level not selected; candidate strength was not filtered")
    if payload.discipline:
        warnings.append("Discipline affinity is unavailable and was not used for ranking")
    if payload.journal_id is not None and guideline_policy.has_mandatory_rules(payload.journal_id):
        warnings.append(
            "This journal has mandatory guidelines that the demo cannot evaluate; "
            "affected patterns were excluded"
        )
    if len({item.score for item in result.items}) < 2 and len(result.items) > 1:
        warnings.append(
            "Available signals do not separate these patterns; tied results use "
            "deterministic text order"
        )
    items = [
        {
            "pattern_version_id": item.pattern.pattern_version_id,
            "canonical_frame": item.pattern.canonical_frame,
            "score": item.score,
            "breakdown": item.breakdown,
            "fallback_tier": item.fallback_tier,
            "source_type": item.pattern.source_type,
            "version_no": item.pattern.version_no,
            "license_code": item.pattern.license_code,
            "license_name": item.pattern.license_name,
            "license_flag": item.pattern.license_flag,
            "source_reference": item.pattern.source_reference,
            "article_id": item.pattern.article_id,
            "explanations": score_explanations(
                item.breakdown,
                claim_type=payload.claim_type or item.pattern.claim_type,
                strength=item.pattern.epistemic_strength,
                evidence_level=payload.evidence_level,
                evidence_policy=evidence_policy,
            ),
        }
        for item in result.items
    ]
    log_items = [{**item, "pattern_version_id": str(item["pattern_version_id"])} for item in items]
    results: dict[str, object] = {
        "items": log_items,
        "excluded": result.excluded,
        "fallback_reason": fallback_reason,
        "warnings": warnings,
    }
    try:
        # BR-08 / FR-09.6: keep explanation, fallback and policy versions;
        # hash the query and omit manuscript text.
        logged_request = payload.model_dump(mode="json", exclude={"query"})
        if query:
            logged_request["query_hash"] = sha256(query.encode("utf-8")).hexdigest()
        context_hash = sha256(
            json.dumps(logged_request, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        logged_request["context_hash"] = context_hash
        log = await repository.add_recommendation_log(
            session,
            request=logged_request,
            results=jsonable_encoder(results),
            policy_versions=versions,
            created_by=actor.id,
        )
        await record_event(
            session,
            actor_id=actor.id,
            action="recommendation.create",
            entity_type="recommendation_log",
            entity_id=log.id,
            after={"item_count": len(items), "policy_versions": versions},
            request_id=request_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return {
        "items": items,
        "excluded": result.excluded,
        "policy_versions": versions,
        "recommendation_id": log.id,
        "context_hash": context_hash,
        "fallback_reason": fallback_reason,
        "warnings": warnings,
    }
