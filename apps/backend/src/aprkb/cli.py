"""Developer CLI entry points."""

import argparse
import asyncio
import json
import sys
from contextlib import suppress
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from aprkb.core.config import settings
from aprkb.modules.audit.service import record_event
from aprkb.modules.identity.service import bootstrap_admin


def _print_pack_report(report: object, *, output_format: str = "text") -> bool:
    from aprkb.modules.pack.validator import ValidationReport

    if not isinstance(report, ValidationReport):
        raise TypeError("Expected a pack validation report")
    if output_format == "json":
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for item in report.findings:
            print(f"{item.severity.upper()} {item.code} {item.path}: {item.message}")
        print(f"Pack: {'invalid' if report.has_errors else 'valid'}")
    return not report.has_errors


def _validate_pack(*, path: Path, output_format: str, reference_dir: Path | None) -> None:
    from aprkb.modules.pack.validator import load_references, validate_pack

    try:
        refs = load_references(reference_dir) if reference_dir else None
        report = validate_pack(path, refs)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Unreadable pack or references: {error}", file=sys.stderr)
        raise SystemExit(2) from error
    if not _print_pack_report(report, output_format=output_format):
        raise SystemExit(1)


async def _import_pack(*, path: Path, dry_run: bool) -> None:
    from aprkb.api.main import app as _app  # noqa: F401 - register ORM mappings
    from aprkb.modules.pack.service import import_pack

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            try:
                report, counts = await import_pack(session, path, dry_run=dry_run)
                if report.has_errors:
                    await session.rollback()
                    _print_pack_report(report)
                    raise SystemExit(1)
                if dry_run:
                    await session.rollback()
                else:
                    await session.commit()
            except (OSError, ValueError, json.JSONDecodeError) as error:
                await session.rollback()
                print(f"Import failed: {error}", file=sys.stderr)
                raise SystemExit(2) from error
        verb = "Would import" if dry_run else "Imported"
        print(f"{verb} {counts['patterns']} patterns, {counts['versions']} versions.")
        _print_pack_report(report)
    finally:
        await engine.dispose()


async def _init_phrasebank(*, path: Path, dry_run: bool) -> None:
    from aprkb.api.main import app as _app  # noqa: F401 - register ORM mappings
    from aprkb.modules.phrasebank.service import initialize_phrasebank

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            try:
                result = await initialize_phrasebank(session, path, dry_run=dry_run)
            except (OSError, ValueError) as error:
                print(f"Phrasebank initialization failed: {error}", file=sys.stderr)
                raise SystemExit(1) from error
        print(json.dumps(result, indent=2, sort_keys=True))
    finally:
        await engine.dispose()


async def _export_pack(*, out: Path, only_approved: bool) -> None:
    from aprkb.api.main import app as _app  # noqa: F401 - register ORM mappings
    from aprkb.modules.pack.service import export_pack

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            counts = await export_pack(session, out, only_approved=only_approved)
        print(f"Exported {counts['patterns']} patterns, {counts['versions']} versions to {out}.")
        for excluded in counts["excluded"]:
            for finding in excluded["findings"]:
                print(
                    f"Excluded {excluded['pattern_id']}: {finding['code']} {finding['path']}",
                    file=sys.stderr,
                )
        if counts["excluded"]:
            print(f"Excluded {len(counts['excluded'])} approved patterns.", file=sys.stderr)
    finally:
        await engine.dispose()


async def _init_reference() -> None:
    from aprkb.api.main import app as _app  # noqa: F401 - register ORM mappings
    from aprkb.seeds.load import init_reference

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            await init_reference(session)
            await session.commit()
        print("Initialized reference data without sample patterns or DEV-UNVERIFIED.")
    finally:
        await engine.dispose()


def _export_pack_schema() -> None:
    from aprkb.modules.pack.models import PackSchema

    output = Path(__file__).resolve().parents[4] / "packages/contracts/data-pack/pack.schema.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(PackSchema.model_json_schema(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output}")


async def _bootstrap_key() -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    plaintext: str | None = None
    try:
        async with factory() as session:
            try:
                client, plaintext = await bootstrap_admin(session)
                await record_event(
                    session,
                    actor_id=None,
                    action="api_key.bootstrap",
                    entity_type="api_client",
                    entity_id=client.id,
                    after={"id": str(client.id), "name": client.name, "role": client.role},
                    request_id="bootstrap",
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        if plaintext is None:
            raise RuntimeError("Admin bootstrap did not produce an API key")
        print(f"Admin API key (shown once): {plaintext}")
    finally:
        await engine.dispose()


async def _import_vocabulary(*, files: list[Path]) -> None:
    from aprkb.api.main import app as _app  # noqa: F401 - load all ORM models
    from aprkb.modules.vocabulary.service import import_workbook
    from aprkb.policies.loader import load_policy_bundle

    policy = load_policy_bundle().vocabulary_import
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        for file_path in files:
            content = file_path.read_bytes()
            async with factory() as session:
                result = await import_workbook(
                    session,
                    content=content,
                    filename=file_path.name,
                    actor=None,
                    request_id="cli-vocab-import",
                    policy=policy,
                )
            print(
                f"{file_path.name}: {result.source_kind}, rows={result.rows_read}, "
                f"inserted={result.inserted}, updated={result.updated}, skipped={result.skipped}"
            )
    finally:
        await engine.dispose()


async def _build_vocabulary_research(*, path: Path) -> None:
    from aprkb.api.main import app as _app  # noqa: F401 - load all ORM models
    from aprkb.modules.vocabulary.research_builder import ResearchManifest, build_research_snapshot

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine)
    try:
        manifest = ResearchManifest.model_validate_json(path.read_bytes())
        async with factory.begin() as session:
            groups, stats = await build_research_snapshot(session, manifest)
        print(
            f"Built evidence from {len(manifest.papers)} papers "
            f"for {groups} field/subfield groups with {stats} lemma associations."
        )
    except (OSError, ValueError) as error:
        print(f"Vocabulary research build failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
    finally:
        await engine.dispose()


async def _reingest(*, source: str) -> None:
    from aprkb.api.main import app as _app  # noqa: F401
    from aprkb.modules.corpus.models import Article
    from aprkb.worker.handlers import local_blob_store, reingest_article

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    blob_store = local_blob_store()
    try:
        async with factory() as session:
            article_ids = list(
                await session.scalars(
                    select(Article.id).where(Article.source == source).order_by(Article.created_at)
                )
            )
        print(f"Re-ingesting {len(article_ids)} article(s) from source {source!r}")
        for article_id in article_ids:
            async with factory() as session:
                article = await session.get(Article, article_id)
                if article is None:
                    continue
                try:
                    result = await reingest_article(session, article, blob_store)
                    await record_event(
                        session,
                        actor_id=None,
                        action="article.reingest",
                        entity_type="article",
                        entity_id=article.id,
                        after={
                            "status": result.status,
                            "sentences_before": result.sentences_before,
                            "sentences_after": result.sentences_after,
                            "pending_candidates_removed": result.pending_candidates_removed,
                        },
                        request_id="cli-reingest",
                    )
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
            print(
                f"{article_id}: {result.status}, sentences {result.sentences_before}"
                f" -> {result.sentences_after}, pending candidates removed"
                f" {result.pending_candidates_removed}"
                + (f", error: {result.error}" if result.error else "")
            )
    finally:
        await engine.dispose()


async def _delete_gold_batch(*, sample_batch: str) -> None:
    from aprkb.api.main import app as _app  # noqa: F401 - load all ORM models
    from aprkb.modules.gold.service import delete_sample_batch

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            try:
                count = await delete_sample_batch(
                    session,
                    sample_batch=sample_batch,
                    request_id="cli-gold-delete",
                )
            except Exception:
                await session.rollback()
                raise
        print(f"Deleted {count} unlabeled gold item(s) from sample batch {sample_batch}.")
    finally:
        await engine.dispose()


async def _import_reference_library(*, file_path: Path) -> None:
    from aprkb.api.main import app as _app  # noqa: F401 - load all ORM models
    from aprkb.modules.reference_library.importer import import_library, load_document

    library = load_document(file_path)
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            try:
                counts = await import_library(session, library, request_id="cli-reference-import")
            except Exception:
                await session.rollback()
                raise
        print(
            f"Imported reference library: {counts['categories']} categories, "
            f"{counts['entries']} entries, {counts['blocks']} blocks, {counts['tables']} tables."
        )
    finally:
        await engine.dispose()


async def _import_measurement_catalog(*, file_path: Path) -> None:
    from aprkb.api.main import app as _app  # noqa: F401 - load all ORM models
    from aprkb.modules.measurement.importer import import_catalog, load_catalog
    from aprkb.policies.loader import load_policy_bundle

    catalog = load_catalog(file_path, load_policy_bundle().measurement)
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            try:
                result = await import_catalog(
                    session, catalog, actor_id=None, request_id="cli-measurement-import"
                )
            except Exception:
                await session.rollback()
                raise
        print(
            f"Measurement catalog {result['catalog_version']}: {result['status']}, "
            f"{result['entries_created']} created, {result['entries_updated']} updated, "
            f"{result['relations']} relations, {len(result['missing_codes'])} missing code(s)."
        )
    finally:
        await engine.dispose()


async def _purge_measurement_catalog() -> None:
    from aprkb.api.main import app as _app  # noqa: F401 - load all ORM models
    from aprkb.modules.measurement.importer import purge_catalog

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            try:
                counts = await purge_catalog(session, request_id="cli-measurement-purge")
            except Exception:
                await session.rollback()
                raise
        print(
            f"Purged measurement catalog: {counts['entries']} entries, "
            f"{counts['relations']} relations, {counts['slot_links']} slot links, "
            f"{counts['import_runs']} import runs."
        )
    finally:
        await engine.dispose()


async def _purge_reference_library() -> None:
    from aprkb.api.main import app as _app  # noqa: F401 - load all ORM models
    from aprkb.modules.reference_library.importer import purge_library

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            try:
                count = await purge_library(session, request_id="cli-reference-purge")
            except Exception:
                await session.rollback()
                raise
        print(f"Purged reference-library data: {count} source(s).")
    finally:
        await engine.dispose()


async def _export_reference_mapping_template() -> None:
    from aprkb.api.main import app as _app  # noqa: F401 - load all ORM models
    from aprkb.modules.reference_library.mapping import export_template

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            print(await export_template(session), end="")
    finally:
        await engine.dispose()


async def _import_reference_mapping(*, file_path: Path) -> None:
    from aprkb.api.main import app as _app  # noqa: F401 - load all ORM models
    from aprkb.modules.reference_library.mapping import import_mapping_file

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            try:
                count = await import_mapping_file(session, file_path)
            except Exception:
                await session.rollback()
                raise
        print(f"Imported {count} reference-taxonomy mapping row(s).")
    finally:
        await engine.dispose()


async def _eval_mining(*, split: str) -> None:
    from aprkb.api.main import app as _app  # noqa: F401 - load all ORM models
    from aprkb.modules.corpus.models import Article, ArticleSection, License, Sentence
    from aprkb.modules.gold.models import GoldItem
    from aprkb.modules.mining.evaluation import evaluate_approved_items
    from aprkb.policies.loader import load_policy_bundle

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            gold_rows = list(
                await session.execute(
                    select(GoldItem, Article.id, License.allows_mining)
                    .join(Article, Article.id == GoldItem.article_id)
                    .join(License, License.id == Article.license_id)
                    .where(
                        GoldItem.status == "approved",
                        GoldItem.split == split,
                        GoldItem.sentence_id.is_not(None),
                        Article.source == "slr",
                    )
                    .order_by(GoldItem.id)
                    .with_for_update(of=[GoldItem, License])
                )
            )
            if not gold_rows:
                raise RuntimeError("No approved gold items exist for the requested split")
            if any(not allows_mining for _, _, allows_mining in gold_rows):
                raise RuntimeError("Gold evaluation source is no longer licensed for mining")
            article_ids = {article_id for _, article_id, _ in gold_rows}
            source_rows = (
                list(
                    await session.execute(
                        select(Sentence, ArticleSection.section_code)
                        .join(Article, Article.id == Sentence.article_id)
                        .join(License, License.id == Article.license_id)
                        .outerjoin(ArticleSection, ArticleSection.id == Sentence.article_section_id)
                        .where(Article.id.in_(article_ids), License.allows_mining.is_(True))
                        .order_by(Sentence.article_id, Sentence.char_start, Sentence.id)
                    )
                )
                if article_ids
                else []
            )
            source_by_id = {sentence.id: (sentence, section) for sentence, section in source_rows}
            previous_by_id: dict[UUID, str | None] = {}
            last_by_section: dict[tuple[UUID, str], str] = {}
            for sentence, section in source_rows:
                previous_by_id[sentence.id] = None
                if section:
                    key = (sentence.article_id, section)
                    previous_by_id[sentence.id] = last_by_section.get(key)
                    last_by_section[key] = sentence.text
            prepared = []
            stale_count = 0
            import hashlib

            for item, _article_id, _ in gold_rows:
                source = (
                    source_by_id.get(item.sentence_id) if item.sentence_id is not None else None
                )
                if source is None:
                    stale_count += 1
                    continue
                sentence, section = source
                if (
                    sentence.article_id != item.article_id
                    or hashlib.sha256(sentence.text.encode("utf-8")).hexdigest() != item.text_sha256
                ):
                    stale_count += 1
                    continue
                prepared.append((item, sentence, previous_by_id.get(sentence.id), section))
            if not prepared:
                raise RuntimeError("No current approved gold sources are available for evaluation")
            metrics = evaluate_approved_items(prepared, load_policy_bundle(), split=split)
            metrics["stale_count"] = stale_count
            output_dir = Path(__file__).resolve().parents[2] / "data" / "eval"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"mining-{split}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
            output_path.write_text(
                json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            print(json.dumps(metrics, indent=2, sort_keys=True))
    finally:
        await engine.dispose()


async def _mining_stats(*, sample: int, seed: int) -> None:
    from aprkb.api.main import app as _app  # noqa: F401 - load all ORM models
    from aprkb.modules.corpus.models import Article, ArticleSection, License, Sentence
    from aprkb.modules.mining.stats import StatsSentence, compute_mining_stats
    from aprkb.nlp.features import SentenceAnalysis
    from aprkb.nlp.syntax import usable_tokens
    from aprkb.policies.loader import load_policy_bundle

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            rows = await session.execute(
                select(Sentence, ArticleSection.section_code, Article.nlp_engine)
                .join(Article, Article.id == Sentence.article_id)
                .join(License, License.id == Article.license_id)
                .outerjoin(ArticleSection, ArticleSection.id == Sentence.article_section_id)
                .where(
                    Article.source == "slr",
                    Article.ingest_status == "ready",
                    License.allows_mining.is_(True),
                )
                .order_by(Sentence.article_id, Sentence.char_start, Sentence.id)
            )
            sentences = []
            for sentence, section_code, nlp_engine in rows:
                analysis = None
                if sentence.nlp_features is not None:
                    try:
                        analysis = SentenceAnalysis.from_json(sentence.nlp_features)
                    except ValueError:
                        analysis = None
                tokens = usable_tokens(analysis)
                locator = (
                    f"syntax:{nlp_engine['model_name']}:{nlp_engine['model_version']}"
                    if tokens is not None
                    and isinstance(nlp_engine, dict)
                    and nlp_engine.get("engine") == "spacy"
                    and isinstance(nlp_engine.get("model_name"), str)
                    and isinstance(nlp_engine.get("model_version"), str)
                    else None
                )
                sentences.append(
                    StatsSentence(
                        text=sentence.text,
                        section_code=section_code,
                        sentence_id=sentence.id,
                        char_start=sentence.char_start,
                        tokens=tokens,
                        locator=locator,
                    )
                )
        stats = compute_mining_stats(sentences, load_policy_bundle(), sample=sample, seed=seed)
        _print_mining_stats(stats)
    finally:
        await engine.dispose()


async def _phrase_stats(
    *,
    focal_batch: UUID | None,
    focal_journal: UUID | None,
    background_batches: list[UUID],
    background_journals: list[UUID],
    all_other: bool,
    top: int | None,
    output_format: str,
) -> None:
    from aprkb.modules.extraction.phrase_stats import PhraseStatsRequest, compute_phrase_stats
    from aprkb.modules.extraction.phrase_stats_repository import candidate_articles
    from aprkb.policies.loader import load_policy_bundle

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            rows = await candidate_articles(session)
        result = compute_phrase_stats(
            rows,
            PhraseStatsRequest(
                focal_batch_id=focal_batch,
                focal_journal_id=focal_journal,
                background_batch_ids=tuple(background_batches),
                background_journal_ids=tuple(background_journals),
                all_other=all_other,
                top_n=top,
            ),
            load_policy_bundle().phrase_stats,
        )
        if output_format == "json":
            print(json.dumps(asdict(result), ensure_ascii=False, indent=2, default=str))
            return
        print("candidate statuses: pending, accepted (rejected excluded)")
        print(f"focal articles: {result.n_focal}; background articles: {result.n_bg}")
        for notice in result.notices:
            print(f"notice: {notice}")
        ranking = result.recurrence_ranking if result.notices else result.score_ranking
        print("ranking: recurrence" if result.notices else "ranking: smoothed contrast")
        print("frame | df_focal/n_focal | df_bg/n_bg | occurrences | score | sample_sentence_ids")
        for row in ranking:
            print(
                f"{row.frame} | {row.df_focal}/{row.n_focal} | {row.df_bg}/{row.n_bg} | "
                f"{row.occurrences} | {row.score:.4f} | "
                f"{','.join(str(value) for value in row.sample_sentence_ids)}"
            )
    finally:
        await engine.dispose()


def _print_mining_stats(stats: object) -> None:
    from aprkb.modules.mining.stats import MiningStats

    if not isinstance(stats, MiningStats):
        raise TypeError("stats must be MiningStats")
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        with suppress(ValueError):
            # Test captures and embedded consoles may reject stream reconfiguration.
            reconfigure(encoding="utf-8", errors="replace")
    print(f"sentences: {stats.total_sentences}")
    print(f"filter kept: {stats.filter_kept}")
    if stats.filter_rejected:
        print(f"filter rejected: {stats.filter_rejected}")
    print(f"imperative accepted: {stats.imperative_accepted}")
    print(f"construction matches: {stats.construction_matches}")
    print(f"construction rejections: {stats.construction_rejections}")
    denominator = stats.filter_kept or 1
    print("extraction reasons (percent of filter-kept sentences):")
    for reason, count in stats.extraction_reasons.items():
        print(f"  {reason}: {count} ({count / denominator:.1%})")
    print(f"distinct frames: {stats.distinct_frames}")
    print("top frames:")
    for frame, count in stats.top_frames:
        print(f"  {count}: {frame}")
    if stats.extracted_samples:
        print("sample extracted sentences:")
        for record in stats.extracted_samples:
            print(f"  {record.text[:140]} -> {record.frame}")
    if stats.missed_samples:
        print("sample missed sentences:")
        for record in stats.missed_samples:
            print(f"  {record.text[:140]} -> {record.reason}")


def _export_openapi(*, check: bool) -> None:
    from aprkb.api.main import app

    output = Path(__file__).resolve().parents[4] / "packages/contracts/openapi/openapi.json"
    rendered = json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if check:
        if not output.exists() or output.read_text(encoding="utf-8") != rendered:
            print(
                "OpenAPI contract is stale; run `make contracts` and commit the result.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        print("OpenAPI contract is up to date.")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {output}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="aprkb")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate-pack")
    validate.add_argument("path", type=Path)
    validate.add_argument("--format", choices=("text", "json"), default="text")
    validate.add_argument("--reference-dir", type=Path)
    importer = commands.add_parser("import-pack")
    importer.add_argument("path", type=Path)
    importer.add_argument("--dry-run", action="store_true")
    exporter = commands.add_parser("export-pack")
    exporter.add_argument("--out", type=Path, required=True)
    exporter.add_argument("--only-approved", action="store_true")
    commands.add_parser("export-pack-schema")
    commands.add_parser("init-reference")
    phrasebank = commands.add_parser(
        "init-phrasebank", help="Initialize both Phrasebank sources from one JSON manifest"
    )
    phrasebank.add_argument("--file", type=Path, required=True)
    phrasebank.add_argument("--dry-run", action="store_true")
    commands.add_parser("bootstrap-key")
    vocabulary_import = commands.add_parser("vocab-import")
    vocabulary_import.add_argument("--file", type=Path, action="append", required=True)
    vocabulary_research = commands.add_parser(
        "build-vocabulary-research",
        help="Replace local vocabulary research evidence using a classified-paper manifest",
    )
    vocabulary_research.add_argument("manifest", type=Path)
    openapi = commands.add_parser("export-openapi")
    openapi.add_argument("--check", action="store_true")
    reingest = commands.add_parser(
        "reingest", help="Re-parse imported articles with the current splitter and policies"
    )
    reingest.add_argument("--source", required=True, help='Article source, e.g. "slr"')
    delete_gold = commands.add_parser(
        "delete-gold-batch", help="Delete a gold sample batch only while it has no labels"
    )
    delete_gold.add_argument("--sample-batch", required=True)
    evaluator = commands.add_parser(
        "eval-mining", help="Evaluate mining against approved gold only"
    )
    evaluator.add_argument("--split", choices=("dev", "test"), required=True)
    mining_stats = commands.add_parser(
        "mining-stats", help="Report unlabeled mining coverage for rights-cleared SLR articles"
    )
    mining_stats.add_argument("--sample", type=int, default=0)
    mining_stats.add_argument("--seed", type=int, default=0)
    phrase_stats = commands.add_parser(
        "phrase-stats", help="Contrast masked-frame document frequency across article sets"
    )
    focal = phrase_stats.add_mutually_exclusive_group(required=True)
    focal.add_argument("--focal-batch", type=UUID)
    focal.add_argument("--focal-journal", type=UUID)
    phrase_stats.add_argument("--background-batch", type=UUID, action="append", default=[])
    phrase_stats.add_argument("--background-journal", type=UUID, action="append", default=[])
    phrase_stats.add_argument("--background", choices=("all-other",))
    phrase_stats.add_argument("--top", type=int)
    phrase_stats.add_argument("--format", choices=("table", "json"), default="table")
    reference_import = commands.add_parser(
        "import-reference-library", help="Import quarantined internal reference data"
    )
    reference_import.add_argument("--file", type=Path, required=True)
    commands.add_parser("purge-reference-library", help="Remove all reference-library data")
    measurement_import = commands.add_parser(
        "measurement-import", help="Import the self-authored Metric & Measurement catalog"
    )
    measurement_import.add_argument("--file", type=Path, required=True)
    commands.add_parser(
        "measurement-purge", help="Remove the measurement catalog and its slot links"
    )
    commands.add_parser(
        "export-reference-mapping-template",
        help="Print an empty reference-to-taxonomy mapping template",
    )
    mapping_import = commands.add_parser(
        "import-reference-mapping", help="Validate and import reviewed reference mappings"
    )
    mapping_import.add_argument("--file", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "validate-pack":
        _validate_pack(path=args.path, output_format=args.format, reference_dir=args.reference_dir)
    elif args.command == "import-pack":
        asyncio.run(_import_pack(path=args.path, dry_run=args.dry_run))
    elif args.command == "export-pack":
        asyncio.run(_export_pack(out=args.out, only_approved=args.only_approved))
    elif args.command == "export-pack-schema":
        _export_pack_schema()
    elif args.command == "init-reference":
        asyncio.run(_init_reference())
    elif args.command == "init-phrasebank":
        asyncio.run(_init_phrasebank(path=args.file, dry_run=args.dry_run))
    elif args.command == "bootstrap-key":
        asyncio.run(_bootstrap_key())
    elif args.command == "vocab-import":
        asyncio.run(_import_vocabulary(files=args.file))
    elif args.command == "build-vocabulary-research":
        asyncio.run(_build_vocabulary_research(path=args.manifest))
    elif args.command == "export-openapi":
        _export_openapi(check=args.check)
    elif args.command == "reingest":
        asyncio.run(_reingest(source=args.source))
    elif args.command == "delete-gold-batch":
        asyncio.run(_delete_gold_batch(sample_batch=args.sample_batch))
    elif args.command == "eval-mining":
        asyncio.run(_eval_mining(split=args.split))
    elif args.command == "mining-stats":
        if args.sample < 0:
            parser.error("--sample must be non-negative")
        asyncio.run(_mining_stats(sample=args.sample, seed=args.seed))
    elif args.command == "phrase-stats":
        if args.top is not None and args.top < 1:
            parser.error("--top must be positive")
        if args.background == "all-other" and (args.background_batch or args.background_journal):
            parser.error("--background all-other cannot be combined with explicit background IDs")
        if args.background != "all-other" and not (
            args.background_batch or args.background_journal
        ):
            parser.error("provide background IDs or --background all-other")
        asyncio.run(
            _phrase_stats(
                focal_batch=args.focal_batch,
                focal_journal=args.focal_journal,
                background_batches=args.background_batch,
                background_journals=args.background_journal,
                all_other=args.background == "all-other",
                top=args.top,
                output_format=args.format,
            )
        )
    elif args.command == "import-reference-library":
        asyncio.run(_import_reference_library(file_path=args.file))
    elif args.command == "measurement-import":
        asyncio.run(_import_measurement_catalog(file_path=args.file))
    elif args.command == "measurement-purge":
        asyncio.run(_purge_measurement_catalog())
    elif args.command == "purge-reference-library":
        asyncio.run(_purge_reference_library())
    elif args.command == "export-reference-mapping-template":
        asyncio.run(_export_reference_mapping_template())
    elif args.command == "import-reference-mapping":
        asyncio.run(_import_reference_mapping(file_path=args.file))


if __name__ == "__main__":
    main()
