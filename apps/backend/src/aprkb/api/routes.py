"""Gom router của các module dưới prefix /v1 (PRD-12)."""

from fastapi import APIRouter

from aprkb.modules.analytics.router import override_router as overrides
from aprkb.modules.analytics.router import router as analytics
from aprkb.modules.corpus.router import admin_router as corpus_admin
from aprkb.modules.gold.router import router as gold
from aprkb.modules.identity.router import admin_router as identity_admin
from aprkb.modules.identity.router import router as identity
from aprkb.modules.journals.router import router as journals
from aprkb.modules.patterns.router import router as patterns
from aprkb.modules.recommendation.router import router as recommendation
from aprkb.modules.review.router import router as review
from aprkb.modules.taxonomy.router import admin_router as taxonomy_admin
from aprkb.modules.taxonomy.router import router as taxonomy
from aprkb.modules.validation.router import router as validation

api_router = APIRouter(prefix="/v1")
api_router.include_router(identity, prefix="/auth")
api_router.include_router(identity_admin, prefix="/admin")
api_router.include_router(taxonomy, prefix="/taxonomy")
api_router.include_router(taxonomy_admin, prefix="/admin")
api_router.include_router(patterns, prefix="/patterns")
api_router.include_router(journals, prefix="/journals")
api_router.include_router(recommendation, prefix="/recommendations")
api_router.include_router(validation, prefix="/validate")
api_router.include_router(review, prefix="/admin")
api_router.include_router(corpus_admin, prefix="/admin")
api_router.include_router(gold)
api_router.include_router(analytics, prefix="/feedback")
api_router.include_router(overrides, prefix="/overrides")
