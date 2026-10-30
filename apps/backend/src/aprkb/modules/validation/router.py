"""Client validation endpoint using the shared evidence policy and V02."""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.deps import get_db_session
from aprkb.core.security import require_role
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.recommendation.repository import reference_strengths
from aprkb.modules.validation.context import ValidationContext
from aprkb.modules.validation.pipeline import ValidationPipeline
from aprkb.modules.validation.rules import build_rules
from aprkb.modules.validation.schemas import (
    ValidationRequest,
    ValidationResponse,
    ValidationRuleResponse,
)
from aprkb.policies.evidence import EvidencePolicy

router = APIRouter(tags=["validation"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
Client = Annotated[ApiClient, Depends(require_role("client"))]


@router.post("", response_model=ValidationResponse)
async def validate_text(
    payload: ValidationRequest,
    request: Request,
    _actor: Client,
    session: DatabaseSession,
) -> ValidationResponse:
    bundle = request.app.state.policy_bundle
    try:
        evidence_policy = EvidencePolicy.from_reference_enums(
            bundle.evidence_matrix, await reference_strengths(session)
        )
    except ValueError as error:
        raise HTTPException(
            status_code=503, detail="Evidence reference data is unavailable"
        ) from error
    pipeline = ValidationPipeline(
        rules=build_rules(
            evidence_policy=evidence_policy,
            lexicon=bundle.epistemic_markers,
            policy=bundle.validation_rules,
        )
    )
    context = ValidationContext(
        claim_type=payload.claim_type,
        evidence_level=payload.evidence_level,
        epistemic_strength=payload.epistemic_strength,
    )
    result = pipeline.run(payload.text, context)
    return ValidationResponse(
        validation_id=uuid4(),
        severity=result.severity.value,
        rules=[
            ValidationRuleResponse(
                code=rule.code,
                severity=rule.severity.value,
                message=rule.message,
                span=rule.span,
            )
            for rule in result.rules
        ],
    )
