"""PostgreSQL tests for the separate Metric & Measurement catalog (ADR-0015)."""

import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from aprkb.api.main import create_app
from aprkb.core.config import settings
from aprkb.core.deps import get_db_session
from aprkb.modules.audit.models import AuditEvent
from aprkb.modules.identity.service import create_api_key
from aprkb.modules.measurement.models import MeasurementEntry, MeasurementRelation
from aprkb.modules.patterns.models import PatternVersion, PhrasePattern
from aprkb.policies.loader import load_policy_bundle
from aprkb.seeds.load import run_seed

SEED = Path(__file__).resolve().parents[5] / "data/seed/measurement_catalog.json"


@pytest_asyncio.fixture
async def session_factory(
    postgres_test_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker]:
    factory = async_sessionmaker(postgres_test_engine, expire_on_commit=False)
    async with factory() as session:
        await run_seed(session)
        await session.commit()
    yield factory


@pytest_asyncio.fixture
async def api_client(
    session_factory: async_sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def override_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    monkeypatch.setattr(settings, "measurement_enabled", True)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client,
    ):
        yield client


async def _key(session_factory: async_sessionmaker, role: str) -> dict[str, str]:
    async with session_factory() as session:
        _, key = await create_api_key(session, name=f"measurement {role}", role=role)
        await session.commit()
    return {"X-API-Key": key}


async def _import_seed(client: AsyncClient, headers: dict[str, str]):
    return await client.post(
        "/v1/admin/measurements/imports",
        headers=headers,
        files={"file": ("catalog.json", SEED.read_bytes(), "application/json")},
    )


async def _pattern_with_slot(session_factory: async_sessionmaker) -> tuple[str, str]:
    async with session_factory() as session:
        rows = await session.execute(
            select(PhrasePattern.id, PatternVersion.slots).join(
                PatternVersion, PatternVersion.id == PhrasePattern.current_version_id
            )
        )
        for pattern_id, slots in rows.all():
            if slots:
                return str(pattern_id), next(iter(slots))
    raise AssertionError("seed has no pattern with slots")


@pytest.mark.asyncio
async def test_import_is_idempotent_and_read_api_filters(api_client, session_factory):
    curator = await _key(session_factory, "curator")
    client = await _key(session_factory, "client")

    first = await _import_seed(api_client, curator)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "imported"
    assert first.json()["entries_created"] >= 20
    second = await _import_seed(api_client, curator)
    assert second.json()["status"] == "unchanged"

    async with session_factory() as session:
        entries = await session.scalar(select(func.count()).select_from(MeasurementEntry))
        relations = await session.scalar(select(func.count()).select_from(MeasurementRelation))
        audits = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "measurement.catalog_imported")
        )
    assert entries == first.json()["entries_created"]
    assert relations == first.json()["relations"]
    assert audits == 1

    everything = await api_client.get("/v1/measurements?limit=200", headers=client)
    kinds = [item["kind"] for item in everything.json()["items"]]
    assert kinds == sorted(kinds, key=["metric", "method", "protocol"].index)
    assert everything.json()["total"] == len(kinds)

    metrics = await api_client.get("/v1/measurements?kind=metric", headers=client)
    assert metrics.status_code == 200
    body = metrics.json()
    assert (
        body["catalog_version"] == json.loads(SEED.read_text(encoding="utf-8"))["catalog_version"]
    )
    assert body["items"] and {item["kind"] for item in body["items"]} == {"metric"}

    by_alias = await api_client.get("/v1/measurements?q=five-point", headers=client)
    assert [item["code"] for item in by_alias.json()["items"]] == ["likert_5_point"]
    literal = await api_client.get("/v1/measurements?q=%25_", headers=client)
    assert literal.json()["items"] == []

    detail = await api_client.get("/v1/measurements/likert_5_point", headers=client)
    assert detail.status_code == 200
    related = {(r["relation"], r["direction"], r["code"]) for r in detail.json()["related"]}
    assert ("part_of", "outgoing", "standardised_collection") in related
    assert ("uses_method", "incoming", "cronbachs_alpha") in related
    assert (await api_client.get("/v1/measurements/nope", headers=client)).status_code == 404


@pytest.mark.asyncio
async def test_slot_link_review_controls_suggestions(api_client, session_factory):
    curator = await _key(session_factory, "curator")
    client = await _key(session_factory, "client")
    await _import_seed(api_client, curator)
    pattern_id, slot = await _pattern_with_slot(session_factory)
    suggestions_url = f"/v1/measurements/slot-suggestions?pattern_id={pattern_id}&slot={slot}"

    proposal = {"entry_code": "likert_5_point", "pattern_id": pattern_id, "slot_name": slot}
    created = await api_client.post(
        "/v1/admin/measurements/slot-links", headers=curator, json=proposal
    )
    assert created.status_code == 201, created.text
    assert created.json()["review_status"] == "proposed"
    duplicate = await api_client.post(
        "/v1/admin/measurements/slot-links", headers=curator, json=proposal
    )
    assert duplicate.status_code == 409

    hidden = await api_client.get(suggestions_url, headers=client)
    assert hidden.json()["items"] == []
    detail = await api_client.get("/v1/measurements/likert_5_point", headers=client)
    assert detail.json()["slot_links"] == []

    link_id = created.json()["id"]
    approved = await api_client.post(
        f"/v1/admin/measurements/slot-links/{link_id}/review",
        headers=curator,
        json={"decision": "approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["review_status"] == "approved"
    again = await api_client.post(
        f"/v1/admin/measurements/slot-links/{link_id}/review",
        headers=curator,
        json={"decision": "rejected"},
    )
    assert again.status_code == 409

    shown = await api_client.get(suggestions_url, headers=client)
    assert [item["code"] for item in shown.json()["items"]] == ["likert_5_point"]
    assert "Suggestions only" in shown.json()["notice"]
    detail = await api_client.get("/v1/measurements/likert_5_point", headers=client)
    assert [link["slot_name"] for link in detail.json()["slot_links"]] == [slot]


@pytest.mark.asyncio
async def test_slot_link_validation(api_client, session_factory):
    curator = await _key(session_factory, "curator")
    await _import_seed(api_client, curator)
    pattern_id, _ = await _pattern_with_slot(session_factory)
    url = "/v1/admin/measurements/slot-links"

    unknown_slot = await api_client.post(
        url,
        headers=curator,
        json={"entry_code": "accuracy", "pattern_id": pattern_id, "slot_name": "not_a_slot"},
    )
    assert unknown_slot.status_code == 422
    unknown_entry = await api_client.post(
        url,
        headers=curator,
        json={"entry_code": "nope", "pattern_id": pattern_id, "slot_name": "x"},
    )
    assert unknown_entry.status_code == 404
    unknown_pattern = await api_client.post(
        url,
        headers=curator,
        json={
            "entry_code": "accuracy",
            "pattern_id": "00000000-0000-0000-0000-000000000000",
            "slot_name": "x",
        },
    )
    assert unknown_pattern.status_code == 404


@pytest.mark.asyncio
async def test_roles_flag_and_invalid_upload(api_client, session_factory, monkeypatch):
    client = await _key(session_factory, "client")
    curator = await _key(session_factory, "curator")

    assert (await api_client.get("/v1/measurements")).status_code == 401
    forbidden = await _import_seed(api_client, client)
    assert forbidden.status_code == 403
    links = await api_client.get("/v1/admin/measurements/slot-links", headers=client)
    assert links.status_code == 403

    bad = await api_client.post(
        "/v1/admin/measurements/imports",
        headers=curator,
        files={"file": ("catalog.json", b'{"catalog_version": "1"}', "application/json")},
    )
    assert bad.status_code == 422
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(MeasurementEntry)) == 0

    monkeypatch.setattr(settings, "measurement_enabled", False)
    assert (await api_client.get("/v1/measurements", headers=client)).status_code == 404
    assert (await _import_seed(api_client, curator)).status_code == 404


@pytest.mark.asyncio
async def test_measurement_migration_round_trip(postgres_test_engine):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    root = Path(__file__).resolve().parents[3]

    async with postgres_test_engine.begin() as connection:
        schema = await connection.scalar(text("SELECT current_schema()"))

        def migrate(sync, target: str, *, up: bool) -> None:
            config = Config(str(root / "alembic.ini"))
            config.set_main_option("script_location", str(root / "migrations"))
            config.attributes["connection"] = sync
            config.attributes["version_table_schema"] = schema
            (command.upgrade if up else command.downgrade)(config, target)

        async def table_exists() -> bool:
            return bool(
                await connection.scalar(
                    text("SELECT to_regclass(current_schema() || '.measurement_entries')")
                )
            )

        assert await table_exists()
        await connection.run_sync(migrate, "0015_merge_vocab_research", up=False)
        assert not await table_exists()
        await connection.run_sync(migrate, "head", up=True)
        assert await table_exists()


async def _validate(client: AsyncClient, headers: dict[str, str], text: str, **extra):
    return await client.post(
        "/v1/validate",
        headers=headers,
        json={
            "text": text,
            "claim_type": "descriptive",
            "evidence_level": "multiple_consistent",
            **extra,
        },
    )


@pytest.mark.asyncio
async def test_validate_reports_undeclared_catalog_metric_without_changing_severity(
    api_client, session_factory, monkeypatch
):
    curator = await _key(session_factory, "curator")
    client = await _key(session_factory, "client")
    await _import_seed(api_client, curator)
    text = "Agreement was assessed with Cohen's kappa."

    monkeypatch.setattr(settings, "measurement_enabled", False)
    baseline = await _validate(api_client, client, text)
    assert baseline.status_code == 200
    assert baseline.json()["metric_warnings"] == []
    assert "measurement" not in baseline.json()["policy_versions"]

    monkeypatch.setattr(settings, "measurement_enabled", True)
    flagged = await _validate(api_client, client, text)
    body = flagged.json()
    assert [(w["code"], tuple(w["span"])) for w in body["metric_warnings"]] == [
        ("cohens_kappa", (28, 41))
    ]
    assert any("Cohen's kappa" in warning for warning in body["warnings"])
    assert body["policy_versions"]["measurement"] == load_policy_bundle().measurement.version
    # Report-only: the rule outcomes, severity and completeness match the flag-off run.
    for field in ("severity", "complete", "rules", "checks_unavailable"):
        assert body[field] == baseline.json()[field]

    declared = await _validate(
        api_client, client, text, context="Two raters; agreement reported as kappa."
    )
    assert declared.json()["metric_warnings"] == []


@pytest.mark.asyncio
async def test_purge_removes_catalog_links_and_runs_with_audit(api_client, session_factory):
    from aprkb.modules.measurement.importer import purge_catalog
    from aprkb.modules.measurement.models import MeasurementImportRun, MeasurementSlotLink

    curator = await _key(session_factory, "curator")
    await _import_seed(api_client, curator)
    pattern_id, slot = await _pattern_with_slot(session_factory)
    await api_client.post(
        "/v1/admin/measurements/slot-links",
        headers=curator,
        json={"entry_code": "accuracy", "pattern_id": pattern_id, "slot_name": slot},
    )

    async with session_factory() as session:
        counts = await purge_catalog(session, request_id="test-purge")
    assert counts["entries"] >= 20 and counts["slot_links"] == 1 and counts["import_runs"] == 1

    async with session_factory() as session:
        for model in (MeasurementEntry, MeasurementRelation, MeasurementSlotLink):
            assert await session.scalar(select(func.count()).select_from(model)) == 0
        assert await session.scalar(select(func.count()).select_from(MeasurementImportRun)) == 0
        audit = await session.scalar(
            select(AuditEvent).where(AuditEvent.action == "measurement.catalog_purged")
        )
        patterns = await session.scalar(select(func.count()).select_from(PhrasePattern))
    assert audit is not None and audit.after["entries"] == counts["entries"]
    assert patterns > 0

    # A purge resets idempotency: the same file imports again.
    again = await _import_seed(api_client, curator)
    assert again.json()["status"] == "imported"


@pytest.mark.asyncio
async def test_pattern_level_links_and_pattern_measurements(api_client, session_factory):
    curator = await _key(session_factory, "curator")
    client = await _key(session_factory, "client")
    await _import_seed(api_client, curator)
    pattern_id, _ = await _pattern_with_slot(session_factory)
    url = "/v1/admin/measurements/slot-links"

    created = await api_client.post(
        url, headers=curator, json={"entry_code": "likert_5_point", "pattern_id": pattern_id}
    )
    assert created.status_code == 201, created.text
    assert created.json()["slot_name"] is None
    assert created.json()["origin"] == "manual"
    duplicate = await api_client.post(
        url, headers=curator, json={"entry_code": "likert_5_point", "pattern_id": pattern_id}
    )
    assert duplicate.status_code == 409

    context_url = f"/v1/measurements/pattern-measurements?pattern_id={pattern_id}"
    assert (await api_client.get(context_url, headers=client)).json()["items"] == []
    await api_client.post(
        f"{url}/{created.json()['id']}/review", headers=curator, json={"decision": "approved"}
    )
    items = (await api_client.get(context_url, headers=client)).json()["items"]
    assert [(item["code"], item["slot_name"]) for item in items] == [("likert_5_point", None)]
    detail = await api_client.get("/v1/measurements/likert_5_point", headers=client)
    assert [link["slot_name"] for link in detail.json()["slot_links"]] == [None]


@pytest.mark.asyncio
async def test_propose_links_matches_apb_methods_patterns_once(api_client, session_factory):
    from aprkb.modules.measurement.link_proposer import propose_links
    from aprkb.modules.measurement.models import MeasurementSlotLink
    from aprkb.policies.loader import load_policy_bundle

    curator = await _key(session_factory, "curator")
    await _import_seed(api_client, curator)
    policy = load_policy_bundle().measurement

    async with session_factory() as session:
        dry = await propose_links(session, policy, request_id="t-dry", dry_run=True)
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(MeasurementSlotLink)) == 0
    assert dry["patterns_scanned"] > 0 and dry["created"] > 0

    async with session_factory() as session:
        first = await propose_links(session, policy, request_id="t-1")
    assert first["created"] == dry["created"]
    async with session_factory() as session:
        links = (await session.scalars(select(MeasurementSlotLink))).all()
        codes = {
            code
            for (code,) in (
                await session.execute(
                    select(MeasurementEntry.code).join(
                        MeasurementSlotLink, MeasurementSlotLink.entry_id == MeasurementEntry.id
                    )
                )
            ).all()
        }
    assert all(
        link.review_status == "proposed" and link.origin == "term_match" and link.slot_name is None
        for link in links
    )
    assert "likert_5_point" in codes

    # Proposals stay hidden until approved.
    client = await _key(session_factory, "client")
    hidden = await api_client.get(
        f"/v1/measurements/pattern-measurements?pattern_id={links[0].pattern_id}",
        headers=client,
    )
    assert hidden.json()["items"] == []

    # A rejected proposal is never recreated; a rerun creates nothing new.
    await api_client.post(
        f"/v1/admin/measurements/slot-links/{links[0].id}/review",
        headers=curator,
        json={"decision": "rejected"},
    )
    async with session_factory() as session:
        second = await propose_links(session, policy, request_id="t-2")
    assert second["created"] == 0
    assert second["already_linked"] == first["created"]


@pytest.mark.asyncio
async def test_pattern_link_migration_round_trip(postgres_test_engine):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    root = Path(__file__).resolve().parents[3]
    async with postgres_test_engine.begin() as connection:
        schema = await connection.scalar(text("SELECT current_schema()"))

        def migrate(sync, target: str, *, up: bool) -> None:
            config = Config(str(root / "alembic.ini"))
            config.set_main_option("script_location", str(root / "migrations"))
            config.attributes["connection"] = sync
            config.attributes["version_table_schema"] = schema
            (command.upgrade if up else command.downgrade)(config, target)

        async def column(name: str) -> str | None:
            return await connection.scalar(
                text(
                    "SELECT is_nullable FROM information_schema.columns "
                    "WHERE table_schema = current_schema() "
                    "AND table_name = 'measurement_slot_links' AND column_name = :name"
                ),
                {"name": name},
            )

        assert await column("slot_name") == "YES" and await column("origin") == "NO"
        await connection.run_sync(migrate, "0021_apb_offline_proposals", up=False)
        assert await column("slot_name") == "NO" and await column("origin") is None
        await connection.run_sync(migrate, "head", up=True)
        assert await column("slot_name") == "YES"


@pytest.mark.asyncio
async def test_proposal_losing_the_race_returns_409_not_500(
    api_client, session_factory, monkeypatch
):
    """Simulate a concurrent insert: the existence check passes but the row already exists."""
    from aprkb.modules.measurement import repository

    curator = await _key(session_factory, "curator")
    await _import_seed(api_client, curator)
    pattern_id, _ = await _pattern_with_slot(session_factory)
    body = {"entry_code": "accuracy", "pattern_id": pattern_id}
    first = await api_client.post("/v1/admin/measurements/slot-links", headers=curator, json=body)
    assert first.status_code == 201

    async def no_existing_link(*_args, **_kwargs):
        return None

    monkeypatch.setattr(repository, "find_link", no_existing_link)
    raced = await api_client.post("/v1/admin/measurements/slot-links", headers=curator, json=body)
    assert raced.status_code == 409


@pytest.mark.asyncio
async def test_catalog_import_waits_for_the_catalog_lock(api_client, session_factory):
    """A second writer blocks while another transaction holds the catalog lock."""
    import asyncio

    from sqlalchemy import text

    from aprkb.modules.measurement.importer import _CATALOG_LOCK, import_catalog, load_catalog
    from aprkb.modules.measurement.models import MeasurementImportRun

    catalog = load_catalog(SEED, load_policy_bundle().measurement)
    async with session_factory() as holder:
        await holder.execute(_CATALOG_LOCK)

        async def second_writer():
            async with session_factory() as session:
                return await import_catalog(session, catalog, actor_id=None, request_id="t-lock")

        task = asyncio.create_task(second_writer())
        waiting = 0
        async with session_factory() as probe:
            for _ in range(100):
                waiting = await probe.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE wait_event_type = 'Lock' AND wait_event = 'advisory' "
                        "AND datname = current_database()"
                    )
                )
                if waiting or task.done():
                    break
                await asyncio.sleep(0.1)
        assert waiting == 1, "the second import must block on the catalog advisory lock"
        assert not task.done()
        await holder.commit()  # releases the transaction-scoped lock
    result = await asyncio.wait_for(task, timeout=30)
    assert result["status"] == "imported"
    again = await _import_seed(api_client, await _key(session_factory, "curator"))
    assert again.json()["status"] == "unchanged"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(MeasurementImportRun)) == 1


@pytest.mark.asyncio
async def test_link_proposer_ignores_rows_inserted_after_its_check(
    api_client, session_factory, monkeypatch
):
    """A concurrent proposer or manual link must not make a run fail or duplicate rows."""
    from aprkb.modules.measurement import repository
    from aprkb.modules.measurement.link_proposer import propose_links
    from aprkb.modules.measurement.models import MeasurementSlotLink

    curator = await _key(session_factory, "curator")
    await _import_seed(api_client, curator)
    policy = load_policy_bundle().measurement
    async with session_factory() as session:
        first = await propose_links(session, policy, request_id="p-1")
    assert first["created"] > 0

    async def no_existing_link(*_args, **_kwargs):
        return None

    monkeypatch.setattr(repository, "find_link", no_existing_link)
    async with session_factory() as session:
        second = await propose_links(session, policy, request_id="p-2")
    assert second["created"] == 0
    assert second["already_linked"] == first["created"]
    async with session_factory() as session:
        total = await session.scalar(select(func.count()).select_from(MeasurementSlotLink))
    assert total == first["created"]


@pytest.mark.asyncio
async def test_search_folds_typographic_apostrophes(api_client, session_factory):
    curator = await _key(session_factory, "curator")
    client = await _key(session_factory, "client")
    await _import_seed(api_client, curator)
    found = await api_client.get(
        "/v1/measurements", params={"q": "Cronbach\u2019s"}, headers=client
    )
    assert [item["code"] for item in found.json()["items"]] == ["cronbachs_alpha"]
