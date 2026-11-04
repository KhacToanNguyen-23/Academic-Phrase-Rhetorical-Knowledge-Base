"""Pack transfer between rolled-back source data and a clean isolated test database."""

import hashlib
import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from aprkb.modules.audit.models import AuditEvent
from aprkb.modules.corpus.models import Article, License, Sentence
from aprkb.modules.identity.service import create_api_key
from aprkb.modules.mining.models import Candidate
from aprkb.modules.pack.service import check_import, export_pack, import_pack
from aprkb.modules.pack.validator import validate_pack
from aprkb.modules.patterns.models import (
    EvidenceProvenance,
    PatternVersion,
    PhrasePattern,
    ReviewDecision,
    UsageConstraint,
)
from aprkb.modules.taxonomy.models import Intent
from aprkb.seeds.load import init_reference

SAMPLE = Path(__file__).resolve().parents[5] / "data/packs/sample-demo"


async def test_export_validate_import_preserves_native_reviews_and_rejects_changes(
    postgres_test_engine,
    tmp_path,
):
    factory = async_sessionmaker(postgres_test_engine, expire_on_commit=False)
    async with factory() as session:
        await init_reference(session)
        await session.commit()

    async with factory() as session:
        # Preserve the sample JSON while avoiding checkout newline conversion in the fixture.
        sample = tmp_path / "sample"
        sample.mkdir()
        sample_content = (SAMPLE / "patterns.json").read_text(encoding="utf-8").encode("utf-8")
        (sample / "patterns.json").write_bytes(sample_content)
        sample_manifest = json.loads((SAMPLE / "manifest.json").read_text(encoding="utf-8"))
        sample_manifest["files"][0]["sha256"] = hashlib.sha256(sample_content).hexdigest()
        (sample / "manifest.json").write_bytes(json.dumps(sample_manifest).encode("utf-8"))
        imported, sample_counts = await import_pack(session, sample)
        assert not imported.has_errors
        reviewer, _ = await create_api_key(session, name="Invented reviewer", role="reviewer")
        intent = await session.scalar(select(Intent).order_by(Intent.code))
        license_row = await session.scalar(select(License).where(License.code == "CC-BY"))
        assert intent is not None and license_row is not None
        article = Article(
            source="invented",
            external_id="test-article",
            doi="10.0000/invented",
            license_id=license_row.id,
            blob_key="private-corpus-text",
            ingest_status="ready",
        )
        session.add(article)
        pattern = PhrasePattern(intent_id=intent.id, status="approved")
        session.add(pattern)
        await session.flush()
        sentence = Sentence(
            article_id=article.id,
            text="PRIVATE: invented article sentence",
            char_start=0,
            char_end=34,
        )
        session.add(sentence)
        await session.flush()
        candidate = Candidate(
            canonical_frame="[X] suggest that [Y].",
            slots={"X": {"type": "noun_phrase", "signals": []}, "Y": {"type": "clause"}},
            matched_pattern_id=pattern.id,
            intent_id=intent.id,
            status="accepted",
            source_sentence_ids=[sentence.id],
        )
        session.add(candidate)
        version = PatternVersion(
            pattern_id=pattern.id,
            version_no=1,
            canonical_frame=candidate.canonical_frame,
            slots=candidate.slots,
            claim_type="descriptive",
            epistemic_strength="moderate",
        )
        session.add(version)
        await session.flush()
        pattern.current_version_id = version.id
        session.add_all(
            [
                UsageConstraint(
                    pattern_version_id=version.id,
                    allowed_sections=["RESULTS"],
                    allowed_genres=[],
                ),
                EvidenceProvenance(
                    pattern_version_id=version.id,
                    source_type="mined",
                    article_id=article.id,
                    license_id=license_row.id,
                    sentence_ids=[sentence.id],
                ),
                *[
                    ReviewDecision(
                        candidate_id=candidate.id,
                        round=round_no,
                        decision="approve",
                        reviewer_id=reviewer.id,
                        comment="PRIVATE: a sentence quoted from the article",
                    )
                    for round_no in (1, 2)
                ],
            ]
        )
        await session.flush()
        native_id = str(pattern.id)
        counts = await export_pack(session, tmp_path / "source")
        repeated = await export_pack(session, tmp_path / "repeated")
        assert counts == repeated
        assert counts["patterns"] == sample_counts["patterns"] + 1
        assert counts["excluded"] == []
        for name in ("patterns.json", "manifest.json"):
            assert (tmp_path / "source" / name).read_bytes() == (
                tmp_path / "repeated" / name
            ).read_bytes()
        # Discard all source rows; only committed reference data remains for destination import.
        await session.rollback()

    assert not validate_pack(tmp_path / "source").has_errors
    payload = (tmp_path / "source/patterns.json").read_text(encoding="utf-8")
    assert "PRIVATE:" not in payload and "sentence_ids" not in payload
    graphs = json.loads(payload)
    mined = next(row for row in graphs if row["pattern_id"] == native_id)["versions"][0]
    assert mined["canonical_frame"] == "{X} suggest that {Y}."
    assert mined["provenance"]["source_sentence_count"] == 1
    assert [row["reviewer"] for row in mined["reviews"]] == ["Invented reviewer"] * 2

    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(PhrasePattern)) == 0
        report, added = await import_pack(session, tmp_path / "source")
        assert not report.has_errors
        assert added["patterns"] == counts["patterns"]
        await session.commit()
        audit_count = await session.scalar(select(func.count()).select_from(AuditEvent))
        report, added = await import_pack(session, tmp_path / "source")
        assert not report.has_errors and added == {"patterns": 0, "versions": 0}
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == audit_count
        await export_pack(session, tmp_path / "destination")
        assert (tmp_path / "source/patterns.json").read_bytes() == (
            tmp_path / "destination/patterns.json"
        ).read_bytes()

        graphs[0]["versions"][0]["canonical_frame"] += " Invented edit."
        changed = json.dumps(graphs, sort_keys=True).encode("utf-8")
        (tmp_path / "source/patterns.json").write_bytes(changed)
        manifest_path = tmp_path / "source/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"][0]["sha256"] = hashlib.sha256(changed).hexdigest()
        manifest_path.write_bytes(json.dumps(manifest).encode("utf-8"))
        changed_report = await check_import(session, tmp_path / "source")
        assert "E15" in {finding.code for finding in changed_report.findings}
