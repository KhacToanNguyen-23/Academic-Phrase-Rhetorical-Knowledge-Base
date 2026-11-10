from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest

from aprkb.modules.extraction import repository, service
from aprkb.policies.loader import load_policy_bundle


def _candidate(candidate_id):
    return SimpleNamespace(
        id=candidate_id,
        canonical_frame="[X] report [Y]",
        cluster_key=None,
        slots={},
        epistemic_strength=None,
        status="pending",
        source_sentence_ids=[],
        occurrences=[],
    )


@pytest.mark.asyncio
async def test_phrase_listing_exposes_distribution_and_filters_unknown_single_paper(monkeypatch):
    unknown_one, unknown_two, known_one = (_candidate(uuid4()) for _ in range(3))
    candidates = [unknown_one, unknown_two, known_one]

    async def count_phrases(*_args, **_kwargs):
        return len(candidates)

    async def list_phrases(_session, *, limit, offset, **_kwargs):
        return candidates[offset : offset + limit], len(candidates)

    async def candidate_section_sources(_session, candidate_ids):
        return {
            unknown_one.id: [("paper-a", None)],
            unknown_two.id: [("paper-a", None), ("paper-b", None)],
            known_one.id: [("paper-c", "RESULTS")],
        }

    async def source_rows(*_args, **_kwargs):
        return {}

    monkeypatch.setattr(repository, "count_phrases", count_phrases)
    monkeypatch.setattr(repository, "list_phrases", list_phrases)
    monkeypatch.setattr(repository, "candidate_section_sources", candidate_section_sources)
    monkeypatch.setattr(repository, "source_rows", source_rows)
    monkeypatch.setattr(
        service.candidate_label_repository,
        "labels_for_candidates",
        _empty_labels,
    )

    policies = load_policy_bundle()
    enabled_filter = policies.mining_filter.model_copy(update={"unknown_single_paper_filter": True})
    monkeypatch.setattr(
        service,
        "_POLICIES",
        replace(policies, mining_filter=enabled_filter),
    )
    page = await service.list_phrases(None, status="pending", scope=None, limit=10, offset=0)

    assert [item.id for item in page.items] == [unknown_two.id, known_one.id]
    assert page.total == 2
    assert page.filtered_reason_counts == {"unknown_single_paper": 1}
    assert page.items[0].section_distribution.is_unknown is True
    assert page.items[0].section_distribution.paper_count == 2
    assert page.items[1].section_distribution.dominant_code == "RESULTS"


@pytest.mark.asyncio
async def test_phrase_listing_keeps_unknown_single_paper_when_policy_is_off(monkeypatch):
    candidate = _candidate(uuid4())

    async def count_phrases(*_args, **_kwargs):
        return 1

    async def list_phrases(*_args, **_kwargs):
        return [candidate], 1

    async def candidate_section_sources(*_args, **_kwargs):
        return {candidate.id: [("paper-a", None)]}

    async def source_rows(*_args, **_kwargs):
        return {}

    monkeypatch.setattr(repository, "count_phrases", count_phrases)
    monkeypatch.setattr(repository, "list_phrases", list_phrases)
    monkeypatch.setattr(repository, "candidate_section_sources", candidate_section_sources)
    monkeypatch.setattr(repository, "source_rows", source_rows)
    monkeypatch.setattr(
        service.candidate_label_repository,
        "labels_for_candidates",
        _empty_labels,
    )
    policies = load_policy_bundle()
    disabled_filter = policies.mining_filter.model_copy(
        update={"unknown_single_paper_filter": False}
    )
    monkeypatch.setattr(
        service,
        "_POLICIES",
        replace(policies, mining_filter=disabled_filter),
    )

    page = await service.list_phrases(None, status="pending", scope=None, limit=10, offset=0)

    assert [item.id for item in page.items] == [candidate.id]
    assert page.total == 1
    assert page.filtered_reason_counts == {}


async def _empty_labels(*_args, **_kwargs):
    return {}
