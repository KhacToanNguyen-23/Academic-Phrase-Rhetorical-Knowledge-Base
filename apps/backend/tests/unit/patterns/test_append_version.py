"""Version edits retain restrictions and source metadata from the previous version."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.identity.models import ApiClient
from aprkb.modules.patterns import service
from aprkb.modules.patterns.models import (
    EvidenceProvenance,
    PatternVersion,
    PhrasePattern,
    UsageConstraint,
)
from aprkb.modules.patterns.schemas import PatternVersionCreate


@pytest.mark.parametrize("with_metadata", [True, False])
async def test_append_preserves_restrictions_and_provenance(monkeypatch, with_metadata):
    old_id = uuid4()
    pattern = PhrasePattern(id=uuid4(), current_version_id=old_id)
    old_version = PatternVersion(id=old_id, version_no=1, canonical_frame="Old phrase")
    usage = UsageConstraint(
        pattern_version_id=old_id,
        allowed_sections=["RESULTS"],
        allowed_genres=["RESEARCH_ARTICLE"],
        evidence_min="multiple_consistent" if with_metadata else None,
        forbidden_contexts=["INTRO"] if with_metadata else [],
    )
    source = EvidenceProvenance(
        pattern_version_id=old_id,
        source_type="mined",
        article_id=uuid4(),
        license_id=uuid4(),
        sentence_ids=[] if with_metadata else [uuid4()],
        source_sentence_count=12 if with_metadata else None,
        occurrence_hash="invented-hash" if with_metadata else None,
        source_section_code="RESULTS" if with_metadata else None,
    )
    monkeypatch.setattr(
        service.repository, "get_current_version", AsyncMock(return_value=old_version)
    )
    monkeypatch.setattr(service.repository, "get_usage_constraint", AsyncMock(return_value=usage))
    monkeypatch.setattr(service.repository, "get_provenance", AsyncMock(return_value=source))
    monkeypatch.setattr(service, "record_event", AsyncMock())
    session = Mock(spec=AsyncSession)
    session.scalar.side_effect = [pattern, 1]

    def assign_version_id(row):
        if isinstance(row, PatternVersion):
            row.id = uuid4()

    session.add.side_effect = assign_version_id
    version = await service.append_version(
        session,
        pattern_id=pattern.id,
        payload=PatternVersionCreate(
            canonical_frame="Updated phrase",
            epistemic_strength="moderate",
            claim_type="descriptive",
        ),
        actor=ApiClient(id=uuid4()),
        request_id="test-append",
    )

    added = [call.args[0] for call in session.add.call_args_list]
    copied_usage = next(row for row in added if isinstance(row, UsageConstraint))
    copied_source = next(row for row in added if isinstance(row, EvidenceProvenance))
    assert version.version_no == 2 and version.canonical_frame == "Updated phrase"
    assert pattern.current_version_id == version.id != old_id
    assert copied_usage.pattern_version_id == copied_source.pattern_version_id == version.id
    for field in ("allowed_sections", "allowed_genres", "evidence_min", "forbidden_contexts"):
        assert getattr(copied_usage, field) == getattr(usage, field)
    for field in (
        "source_type",
        "article_id",
        "license_id",
        "sentence_ids",
        "source_sentence_count",
        "occurrence_hash",
        "source_section_code",
    ):
        assert getattr(copied_source, field) == getattr(source, field)
    assert old_version.id == old_id and old_version.canonical_frame == "Old phrase"
    assert usage.pattern_version_id == source.pattern_version_id == old_id
    assert copied_usage.allowed_sections is not usage.allowed_sections
    assert copied_usage.allowed_genres is not usage.allowed_genres
    assert copied_usage.forbidden_contexts is not usage.forbidden_contexts
    assert copied_source.sentence_ids is not source.sentence_ids
    session.commit.assert_awaited_once()
