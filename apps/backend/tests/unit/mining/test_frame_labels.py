from aprkb.modules.mining.frame_labels import (
    FrameLabel,
    FrameSourceLabelData,
    build_frame_labels,
    overlay_candidate_labels,
    recommendation_value,
)
from aprkb.modules.mining.frame_sections import summarize_frame_sections
from aprkb.policies.loader import load_policy_bundle


def _labels(frame: str, *, license_code: str = "CC-BY"):
    policies = load_policy_bundle()
    sources = [
        FrameSourceLabelData(
            article_id="paper-a",
            genre_code="research_article",
            license_code=license_code,
            allows_mining=True,
            allows_display=True,
        ),
        FrameSourceLabelData(
            article_id="paper-b",
            genre_code="research_article",
            license_code="CC-BY",
            allows_mining=True,
            allows_display=True,
        ),
    ]
    distribution = summarize_frame_sections(
        [("paper-a", "RESULTS"), ("paper-b", "RESULTS"), ("paper-c", "INTRO")],
        dominant_share_threshold=0.6,
    )
    return build_frame_labels(
        canonical_frame=frame,
        slot_types={"X": "noun_phrase", "Y": "clause"},
        epistemic_strength="moderate",
        source_sentence_count=3,
        cluster_key="construction=causal_explanation:0.1.0:abc",
        sources=sources,
        section_distribution=distribution,
        dominant_share_threshold=0.6,
        anchor_policy=policies.frame_function_anchors,
    )


def test_frame_labels_populate_derived_proposals_and_unassigned_fields() -> None:
    labels = _labels("[X] suggests [Y] and outperforms [Z].")

    assert labels.section_scope.status == "unassigned"
    assert labels.observed_sections.status == "derived"
    assert labels.observed_sections.value == {
        "codes": [{"code": "RESULTS", "share": 2 / 3}],
        "counts": {
            "ABSTRACT": 0,
            "INTRO": 1,
            "RELATED_WORK": 0,
            "METHODS": 0,
            "RESULTS": 2,
            "DISCUSSION": 0,
            "CONCLUSION": 0,
        },
        "dominant": "RESULTS",
        "unknown_count": 0,
    }
    assert labels.article_genres.value == ["research_article"]
    assert labels.source_class.value == "corpus-inferred"
    assert labels.sequence_hint.status == "unassigned"
    assert labels.provenance.value == {
        "source_sentence_count": 3,
        "paper_count": 2,
        "tier": "Tier 2",
        "construction_id": "causal_explanation",
    }
    assert labels.license_status.value == "allowed"
    assert labels.slots.value == {"X": "noun_phrase", "Y": "clause"}
    assert labels.epistemic_strength.status == "derived"
    assert labels.epistemic_strength.evidence is None
    assert labels.function_group.value == "REPORTING_RESULTS"
    assert labels.function_group.status == "proposed"
    assert labels.function_group.confidence == "high"
    assert labels.function_group.source == "anchor:comparison_superiority"
    assert labels.intent.value == "compare_performance"
    assert labels.intent.status == "proposed"
    assert labels.move.status == labels.step.status == "unassigned"
    assert labels.claim_type.status == labels.register_label.status == "unassigned"
    assert labels.general_function.status == "unassigned"
    assert labels.constraints.status == labels.review_status.status == "unassigned"
    assert recommendation_value(labels.function_group) is None
    assert recommendation_value(labels.section_scope) is None
    assert "register" in labels.model_dump(by_alias=True)
    confirmed = FrameLabel(value="confirmed-by-human", status="confirmed", source="curation")
    assert recommendation_value(confirmed) == "confirmed-by-human"


def test_unknown_sections_and_unverified_licenses_fail_closed() -> None:
    policies = load_policy_bundle()
    distribution = summarize_frame_sections([("paper-a", None)], dominant_share_threshold=0.6)
    label = build_frame_labels(
        canonical_frame="[X] has no anchor [Y]",
        slot_types={},
        epistemic_strength=None,
        source_sentence_count=1,
        cluster_key=None,
        sources=[
            FrameSourceLabelData(
                article_id="paper-a",
                license_code="DEV-UNVERIFIED",
                allows_mining=True,
                allows_display=True,
            )
        ],
        section_distribution=distribution,
        dominant_share_threshold=0.6,
        anchor_policy=policies.frame_function_anchors,
    )

    assert label.section_scope.status == "unassigned"
    assert label.article_genres.status == "unassigned"
    assert label.license_status.value == "unknown"
    assert label.epistemic_strength.status == "unassigned"
    assert label.function_group.status == "unassigned"
    assert label.intent.status == "unassigned"


def test_approved_anchor_families_propose_only_one_family() -> None:
    assert _labels("[X] outperformed [Y]").function_group.value == "REPORTING_RESULTS"
    assert _labels("[X] suffers from [Y]").function_group.value == "DISCUSSING_FINDINGS"
    assert _labels("[X] is defined as [Y]").general_function.status == "proposed"
    assert _labels("[X] supports future work").function_group.value == "WRITING_CONCLUSIONS"
    assert _labels("[X] outperforms [Y] and fails to [Z]").function_group.status == "unassigned"


def test_negated_and_meaning_shifted_anchor_constructions_are_not_proposed() -> None:
    assert _labels("[X] does not outperform [Y]").function_group.status == "unassigned"
    assert _labels("[X] is without limitation").function_group.status == "unassigned"


def test_read_side_overlay_confirms_human_labels_and_hides_rejected_values() -> None:
    labels = _labels("[X] report [Y]")
    overlay = overlay_candidate_labels(
        labels,
        [
            {
                "label_code": "intent",
                "value": "report_finding",
                "status": "confirmed",
                "source": "ai:2pass",
            },
            {
                "label_code": "function_group",
                "value": "REPORTING_RESULTS",
                "status": "rejected",
                "source": "ai:2pass",
            },
        ],
    )
    assert overlay.intent.status == "confirmed"
    assert overlay.intent.source == "human"
    assert overlay.function_group.status == "rejected"
    assert overlay.function_group.value is None
    assert (
        recommendation_value(
            FrameLabel(value="report_finding", status="proposed", source="ai:2pass")
        )
        is None
    )
    assert recommendation_value(overlay.function_group) is None
