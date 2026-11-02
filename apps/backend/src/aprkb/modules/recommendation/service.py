"""Database-backed recommendation request orchestration."""

import json
from hashlib import sha256
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.audit.service import record_event
from aprkb.modules.discipline.null_source import NullDisciplineSource
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.journals import repository as journal_repository
from aprkb.modules.journals import service as journal_service
from aprkb.modules.journals.guideline_policy import GuidelinePolicy
from aprkb.modules.recommendation import repository
from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.fallback import FallbackTierLoader
from aprkb.modules.recommendation.gates import build_gates
from aprkb.modules.recommendation.models import RecommendationLog
from aprkb.modules.recommendation.pattern_view import PatternView
from aprkb.modules.recommendation.pipeline import RecommendationPipeline
from aprkb.modules.recommendation.schemas import RecommendationRequest
from aprkb.modules.recommendation.scorers import build_scorers
from aprkb.modules.taxonomy import repository as taxonomy_repository
from aprkb.policies.evidence import EvidencePolicy
from aprkb.policies.loader import PolicyBundle


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
    )
    rows_by_version: dict[UUID, list[repository.PatternRow]] = {}
    for row in rows:
        rows_by_version.setdefault(row[2].id, []).append(row)
    by_tier: dict[str, list[PatternView]] = {
        tier: [] for tier in policy_bundle.fallback_tiers.tiers
    }
    for version_rows in rows_by_version.values():
        pattern, _intent, version, usage, provenance, license_row, article = version_rows[0]
        if len(version_rows) != 1:
            provenance = None
            license_row = None
            article = None
        source_type = provenance.source_type if provenance else "unknown"
        allowed_genres = tuple(usage.allowed_genres) if usage else ()
        if allowed_genres and payload.genre not in allowed_genres:
            continue
        # A genre match alone is not evidence of journal-specific suitability.
        tier = "generic_genre"
        if tier not in by_tier:
            continue
        by_tier[tier].append(
            PatternView(
                pattern_version_id=version.id,
                status=pattern.status,
                intent_code=payload.intent,
                canonical_frame=version.canonical_frame,
                claim_type=version.claim_type,
                epistemic_strength=version.epistemic_strength,
                allowed_sections=tuple(usage.allowed_sections) if usage else (),
                allowed_genres=allowed_genres,
                source_type=source_type,
                license_allows_display=(
                    source_type == "authored"
                    or (
                        source_type == "mined"
                        and license_row is not None
                        and (
                            license_row.allows_display
                            or license_row.code in policy_bundle.license.internal_use_codes
                        )
                    )
                ),
                license_flag=(
                    license_row is not None
                    and license_row.code in policy_bundle.license.internal_use_codes
                ),
                version_no=version.version_no,
                license_code=license_row.code if license_row else None,
                license_name=license_row.name if license_row else None,
                source_reference=(
                    (article.doi or f"Article {article.id}") if article is not None else None
                ),
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
            discipline_source=NullDisciplineSource(), evidence_policy=evidence_policy
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
            "explanations": [
                *item.explanations,
                *([fallback_reason] if fallback_reason is not None else []),
            ],
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
            results=results,
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
