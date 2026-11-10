"""Read-side frame labels; proposed judgment labels never imply confirmation."""

import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from aprkb.modules.mining.frame_sections import FrameSectionDistribution
from aprkb.policies.schemas import FrameFunctionAnchorsPolicy

LabelStatus = Literal["derived", "proposed", "unassigned", "confirmed", "rejected"]
FunctionGroup = Literal[
    "INTRODUCING_WORK",
    "REFERRING_TO_SOURCES",
    "DESCRIBING_METHODS",
    "REPORTING_RESULTS",
    "DISCUSSING_FINDINGS",
    "WRITING_CONCLUSIONS",
    "GENERAL_FUNCTIONS",
]


class FrameLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Any | None
    status: LabelStatus
    source: str
    confidence: str | float | None = None
    evidence: dict[str, Any] | None = None
    options: list[dict[str, Any]] | None = None
    agreement: str | None = None
    needs_attention: bool = False


class FrameLabels(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    section_scope: FrameLabel
    observed_sections: FrameLabel
    article_genres: FrameLabel
    provenance: FrameLabel
    license_status: FrameLabel
    source_class: FrameLabel
    slots: FrameLabel
    epistemic_strength: FrameLabel
    function_group: FrameLabel
    intent: FrameLabel
    move: FrameLabel
    step: FrameLabel
    claim_type: FrameLabel
    register_label: FrameLabel = Field(alias="register")
    general_function: FrameLabel
    sequence_hint: FrameLabel
    constraints: FrameLabel
    review_status: FrameLabel


class FrameSourceLabelData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    article_id: str
    genre_code: str | None = None
    license_code: str | None = None
    allows_mining: bool | None = None
    allows_display: bool | None = None


def recommendation_value(label: FrameLabel) -> Any | None:
    """Only deterministic or human-confirmed labels may flow into recommendation."""
    return label.value if label.status in {"derived", "confirmed"} else None


def build_frame_labels(
    *,
    canonical_frame: str,
    slot_types: dict[str, str],
    epistemic_strength: str | None,
    source_sentence_count: int,
    cluster_key: str | None,
    sources: Sequence[FrameSourceLabelData],
    section_distribution: FrameSectionDistribution,
    dominant_share_threshold: float,
    anchor_policy: FrameFunctionAnchorsPolicy,
) -> FrameLabels:
    """Build read-only evidence and label proposals for one mined frame."""
    scoped = [
        {"code": code, "share": share}
        for code, share in section_distribution.shares.items()
        if share >= dominant_share_threshold
    ]
    genres = sorted({source.genre_code for source in sources if source.genre_code})
    license_value = _license_status(sources)
    tier, construction_id = _extraction_method(cluster_key)
    proposal = _anchor_proposal(canonical_frame, anchor_policy)

    function_group = _label(None, "unassigned", "none")
    intent = _label(None, "unassigned", "none")
    general_function = _label(None, "unassigned", "none")
    if proposal is not None:
        anchor, matched_lemma, matched_form = proposal
        evidence = {
            "anchor_id": anchor.id,
            "matched_lemma": matched_lemma,
            "matched_form": matched_form,
        }
        function_group = _label(
            anchor.function_group,
            "proposed",
            f"anchor:{anchor.id}",
            confidence=anchor.confidence,
            evidence=evidence,
        )
        intent = _label(
            anchor.intent_hint,
            "proposed",
            f"anchor:{anchor.id}",
            confidence=anchor.confidence,
            evidence=evidence,
        )
        if anchor.function_group == "GENERAL_FUNCTIONS":
            general_function = _label(
                anchor.intent_hint,
                "proposed",
                f"anchor:{anchor.id}",
                confidence=anchor.confidence,
                evidence=evidence,
            )

    return FrameLabels(
        section_scope=_label(None, "unassigned", "none"),
        observed_sections=_label(
            {
                "codes": scoped,
                "counts": section_distribution.counts,
                "dominant": section_distribution.dominant_code,
                "unknown_count": section_distribution.unknown_count,
            },
            "derived",
            "frame_sections",
            evidence={"dominant_share": section_distribution.dominant_share},
        ),
        article_genres=_label(
            genres,
            "derived" if genres else "unassigned",
            "source_article_metadata",
        ),
        provenance=_label(
            {
                "source_sentence_count": source_sentence_count,
                "paper_count": len(
                    {source.article_id for source in sources if source.article_id != "unknown"}
                ),
                "tier": tier,
                "construction_id": construction_id,
            },
            "derived",
            "candidate_provenance",
        ),
        license_status=_label(
            license_value,
            "derived",
            "source_article_licenses",
            evidence={"license_codes": sorted({s.license_code or "unknown" for s in sources})},
        ),
        source_class=_label("corpus-inferred", "derived", "mining_pipeline"),
        slots=_label(slot_types, "derived", "candidate_slots"),
        epistemic_strength=_label(
            epistemic_strength,
            "derived" if epistemic_strength is not None else "unassigned",
            "epistemic_tagger",
        ),
        function_group=function_group,
        intent=intent,
        move=_label(None, "unassigned", "none"),
        step=_label(None, "unassigned", "none"),
        claim_type=_label(None, "unassigned", "none"),
        register=_label(None, "unassigned", "none"),
        general_function=general_function,
        sequence_hint=_label(None, "unassigned", "TODO(owner, FR-01)"),
        constraints=_label(None, "unassigned", "TODO(owner, FR-01)"),
        review_status=_label(None, "unassigned", "TODO(owner, FR-01)"),
    )


def overlay_candidate_labels(
    labels: FrameLabels,
    rows: Sequence[Mapping[str, Any]],
) -> FrameLabels:
    """Overlay stored proposal/approval values; rejected rows suppress rule hints."""
    field_by_code = {
        "function_group": "function_group",
        "intent": "intent",
        "move": "move",
        "step": "step",
        "claim_type": "claim_type",
        "register": "register_label",
        "general_function": "general_function",
        "section_scope": "section_scope",
    }
    updates: dict[str, FrameLabel] = {}
    for row in rows:
        label_code = row.get("label_code")
        if not isinstance(label_code, str):
            continue
        field = field_by_code.get(label_code)
        status = row.get("status")
        if field is None or status not in {"proposed", "confirmed", "rejected"}:
            continue
        if status == "rejected":
            updates[field] = _label(None, "rejected", "human")
            continue
        value = row.get("value")
        if value is not None and not isinstance(value, str):
            continue
        if status == "confirmed" and not isinstance(value, str):
            continue
        updates[field] = FrameLabel(
            value=value,
            status="confirmed" if status == "confirmed" else "proposed",
            source="human" if status == "confirmed" else str(row.get("source", "ai:2pass")),
            confidence=row.get("confidence"),
            options=row.get("options"),
            evidence={"passes": row["evidence"]} if row.get("evidence") else None,
            agreement=row.get("agreement"),
            needs_attention=bool(row.get("needs_attention", False)),
        )
    return labels.model_copy(update=updates)


def _label(
    value: Any | None,
    status: LabelStatus,
    source: str,
    *,
    confidence: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> FrameLabel:
    return FrameLabel(
        value=value, status=status, source=source, confidence=confidence, evidence=evidence
    )


def _license_status(sources: Sequence[FrameSourceLabelData]) -> str:
    if not sources or any(
        source.license_code in {None, "DEV-UNVERIFIED"}
        or source.allows_mining is None
        or source.allows_display is None
        for source in sources
    ):
        return "unknown"
    if any(not source.allows_mining or not source.allows_display for source in sources):
        return "restricted"
    return "allowed"


def _extraction_method(cluster_key: str | None) -> tuple[str, str | None]:
    if not cluster_key or not cluster_key.startswith("construction="):
        return "Tier 1", None
    parts = cluster_key.removeprefix("construction=").split(":", 2)
    return "Tier 2", parts[0] if parts else None


def _anchor_proposal(frame: str, policy: FrameFunctionAnchorsPolicy) -> tuple[Any, str, str] | None:
    matched: dict[str, tuple[Any, str, str]] = {}
    for anchor in policy.anchors:
        for lemma in anchor.lemmas:
            for form in anchor.forms[lemma]:
                form_pattern = r"\s+".join(re.escape(part) for part in form.split())
                pattern = re.compile(rf"(?<!\w){form_pattern}(?!\w)", re.I)
                match = pattern.search(frame)
                if match is None:
                    continue
                prefix = frame[: match.start()]
                if re.search(r"\b(?:not|never|no|without)\b(?:\W+\w+){0,2}\W*$", prefix, re.I):
                    return None
                matched.setdefault(anchor.id, (anchor, lemma, match.group(0)))
                break
            if anchor.id in matched:
                break
    return next(iter(matched.values())) if len(matched) == 1 else None
