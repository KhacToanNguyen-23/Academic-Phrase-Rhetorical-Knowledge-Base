"""Developer CLI entry points."""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from aprkb.core.config import settings
from aprkb.modules.audit.service import record_event
from aprkb.modules.identity.service import bootstrap_admin


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
    commands.add_parser("bootstrap-key")
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
    reference_import = commands.add_parser(
        "import-reference-library", help="Import quarantined internal reference data"
    )
    reference_import.add_argument("--file", type=Path, required=True)
    commands.add_parser("purge-reference-library", help="Remove all reference-library data")
    args = parser.parse_args()
    if args.command == "bootstrap-key":
        asyncio.run(_bootstrap_key())
    elif args.command == "export-openapi":
        _export_openapi(check=args.check)
    elif args.command == "reingest":
        asyncio.run(_reingest(source=args.source))
    elif args.command == "delete-gold-batch":
        asyncio.run(_delete_gold_batch(sample_batch=args.sample_batch))
    elif args.command == "eval-mining":
        asyncio.run(_eval_mining(split=args.split))
    elif args.command == "import-reference-library":
        asyncio.run(_import_reference_library(file_path=args.file))
    elif args.command == "purge-reference-library":
        asyncio.run(_purge_reference_library())


if __name__ == "__main__":
    main()
