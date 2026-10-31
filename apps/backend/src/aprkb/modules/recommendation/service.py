"""Database-backed recommendation request orchestration."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.audit.service import record_event
from aprkb.modules.discipline.null_source import NullDisciplineSource
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.recommendation import repository
from aprkb.modules.recommendation.context import RecommendationContext
from aprkb.modules.recommendation.fallback import FallbackTierLoader
from aprkb.modules.recommendation.gates import build_gates
from aprkb.modules.recommendation.pattern_view import PatternView
from aprkb.modules.recommendation.pipeline import RecommendationPipeline
from aprkb.modules.recommendation.schemas import RecommendationRequest
from aprkb.modules.recommendation.scorers import build_scorers
from aprkb.policies.evidence import EvidencePolicy
from aprkb.policies.loader import PolicyBundle


async def recommend(
    session: AsyncSession,
    *,
    payload: RecommendationRequest,
    actor: ApiClient,
    request_id: str,
    policy_bundle: PolicyBundle,
) -> dict[str, object]:
    try:
        evidence_policy = EvidencePolicy.from_reference_enums(
            policy_bundle.evidence_matrix, await repository.reference_strengths(session)
        )
    except ValueError as error:
        raise HTTPException(
            status_code=503, detail="Evidence reference data is unavailable"
        ) from error
    rows = await repository.load_pattern_rows(session, intent_code=payload.intent)
    rows_by_version: dict[UUID, list[repository.PatternRow]] = {}
    for row in rows:
        rows_by_version.setdefault(row[2].id, []).append(row)
    by_tier: dict[str, list[PatternView]] = {
        tier: [] for tier in policy_bundle.fallback_tiers.tiers
    }
    for version_rows in rows_by_version.values():
        pattern, _intent, version, usage, provenance, license_row = version_rows[0]
        if len(version_rows) != 1:
            provenance = None
            license_row = None
        source_type = provenance.source_type if provenance else "unknown"
        allowed_genres = tuple(usage.allowed_genres) if usage else ()
        if allowed_genres:
            if payload.genre in allowed_genres:
                tier = "journal_genre"
            else:
                # Similar-journal and discipline fallback require data not in this scaffold.
                continue
        else:
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
                        and license_row.allows_display
                    )
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
    )
    pipeline = RecommendationPipeline(
        gates=build_gates(evidence_policy=evidence_policy),
        scorers=build_scorers(
            discipline_source=NullDisciplineSource(), evidence_policy=evidence_policy
        ),
        weights=policy_bundle.ranking_weights.weights,
        tier_loader=FallbackTierLoader(tiers=policy_bundle.fallback_tiers.tiers, by_tier=by_tier),
    )
    result = pipeline.recommend(context)
    versions = {
        "ranking_weights": policy_bundle.ranking_weights.version,
        "evidence_matrix": policy_bundle.evidence_matrix.version,
    }
    items = [
        {
            "pattern_version_id": item.pattern.pattern_version_id,
            "canonical_frame": item.pattern.canonical_frame,
            "score": item.score,
            "breakdown": item.breakdown,
            "fallback_tier": item.fallback_tier,
            "explanations": list(item.explanations),
        }
        for item in result.items
    ]
    log_items = [{**item, "pattern_version_id": str(item["pattern_version_id"])} for item in items]
    results: dict[str, object] = {"items": log_items, "excluded": result.excluded}
    try:
        log = await repository.add_recommendation_log(
            session,
            request=payload.model_dump(mode="json"),
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
    }
