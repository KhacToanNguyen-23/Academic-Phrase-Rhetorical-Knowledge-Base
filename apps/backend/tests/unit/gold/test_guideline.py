"""The labeling guideline must stay in step with the policies it describes."""

from aprkb.modules.gold.service import _load_gold_guideline
from aprkb.policies.loader import load_policy_bundle


def test_guideline_version_matches_labeling_policy():
    policy = load_policy_bundle().gold_labeling
    assert (
        "guideline " + policy.guideline_version
        in _load_gold_guideline(policy.guideline_version).casefold()
    )


def test_guideline_lists_every_epistemic_marker():
    bundle = load_policy_bundle()
    guideline = _load_gold_guideline(bundle.gold_labeling.guideline_version)
    missing = [
        marker
        for markers in bundle.epistemic_markers.markers.values()
        for marker in markers
        if marker not in guideline
    ]
    assert missing == []
