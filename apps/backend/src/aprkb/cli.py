"""Developer CLI entry points."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

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
    args = parser.parse_args()
    if args.command == "bootstrap-key":
        asyncio.run(_bootstrap_key())
    elif args.command == "export-openapi":
        _export_openapi(check=args.check)
    elif args.command == "reingest":
        asyncio.run(_reingest(source=args.source))


if __name__ == "__main__":
    main()
