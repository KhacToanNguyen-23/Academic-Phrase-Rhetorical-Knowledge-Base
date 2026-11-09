"""Client validation endpoint using the shared evidence policy and V02."""

import json
import re
from hashlib import sha256
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
UNFILLED_SLOT = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*)\}")


@router.post("", response_model=ValidationResponse)
async def validate_text(
    payload: ValidationRequest,
    request: Request,
    _actor: Client,
    session: DatabaseSession,
) -> ValidationResponse:
    """FR-08.1/.6 / BR-03: return rule-level outcomes and explicitly expose unavailable checks."""
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
        source_values=tuple(value for value in (payload.context, *payload.slots.values()) if value),
    )
    result = pipeline.run(payload.text, context)
    unavailable = [rule.code for rule in result.rules if rule.severity.value == "unavailable"]
    warnings = []
    if unavailable:
        warnings.append(
            "Validation is incomplete because checks are unavailable: " + ", ".join(unavailable)
        )
    unfilled_slots = sorted(set(UNFILLED_SLOT.findall(payload.text)))
    if unfilled_slots:
        warnings.append(
            "Unfilled template placeholders remain: "
            + ", ".join(f"{{{slot}}}" for slot in unfilled_slots)
        )
    return ValidationResponse(
        validation_id=uuid4(),
        text_hash=sha256(payload.text.encode("utf-8")).hexdigest(),
        context_hash=sha256(
            json.dumps(context.__dict__, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        policy_versions={
            "evidence_matrix": bundle.evidence_matrix.version,
            "epistemic_markers": bundle.epistemic_markers.version,
            "validation_rules": bundle.validation_rules.version,
        },
        severity=result.severity.value,
        complete=result.complete,
        checks_unavailable=unavailable,
        checks_not_applicable=[
            rule.code for rule in result.rules if rule.severity.value == "not_applicable"
        ],
        warnings=warnings,
        rules=[
            ValidationRuleResponse(
                code=rule.code,
                severity=rule.severity.value,
                message=rule.message,
                span=rule.span,
                applied=rule.applied,
                recommended_action=rule.recommended_action,
            )
            for rule in result.rules
        ],
    )
