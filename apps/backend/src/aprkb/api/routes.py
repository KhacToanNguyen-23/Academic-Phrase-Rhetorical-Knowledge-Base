"""Gom router của các module dưới prefix /v1 (PRD-12)."""

from fastapi import APIRouter

from aprkb.modules.analytics.router import router as analytics
from aprkb.modules.audit.router import router as audit
from aprkb.modules.corpus.router import router as corpus
from aprkb.modules.identity.router import router as identity
from aprkb.modules.journals.router import router as journals
from aprkb.modules.openalex.router import router as openalex
from aprkb.modules.patterns.router import router as patterns
from aprkb.modules.recommendation.router import router as recommendation
from aprkb.modules.review.router import router as review
from aprkb.modules.taxonomy.router import router as taxonomy
from aprkb.modules.validation.router import router as validation

api_router = APIRouter(prefix="/v1")
api_router.include_router(identity, prefix="/auth")
api_router.include_router(taxonomy, prefix="/taxonomy")
api_router.include_router(patterns, prefix="/patterns")
api_router.include_router(journals, prefix="/journals")
api_router.include_router(recommendation, prefix="/recommendations")
api_router.include_router(validation, prefix="/validate")
api_router.include_router(review, prefix="/reviews")
api_router.include_router(corpus, prefix="/corpus")
api_router.include_router(openalex, prefix="/openalex")
api_router.include_router(analytics, prefix="/feedback")
api_router.include_router(audit, prefix="/audit")
