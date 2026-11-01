from collections.abc import Iterable

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from aprkb.modules.audit.models import AuditEvent
from aprkb.modules.audit.service import record_event
from aprkb.modules.corpus.models import License
from aprkb.modules.identity.models import ApiClient
from aprkb.modules.identity.service import authenticate_api_key, bootstrap_admin
from aprkb.modules.patterns.models import PatternVersion, PhrasePattern
from aprkb.modules.taxonomy.models import (
    ArticleGenre,
    Intent,
    Move,
    Section,
    Step,
    TaxonomyRelease,
)
from aprkb.seeds.load import run_seed
from aprkb.shared.models import RefEnum


@pytest.fixture
def session_factory(postgres_test_engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(postgres_test_engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_api_key_hash_lookup_inactive_rejection_and_one_time_admin_bootstrap(
    session_factory: async_sessionmaker,
) -> None:
    async with session_factory() as session:
        admin, plaintext = await bootstrap_admin(session, name="phase 02 test admin")
        await session.commit()

        assert plaintext
        assert plaintext != admin.key_hash
        assert await authenticate_api_key(session, plaintext) == admin
        assert await authenticate_api_key(session, "invalid-key") is None

        stored = await session.get(ApiClient, admin.id)
        assert stored is not None
        stored.is_active = False
        await session.commit()
        assert await authenticate_api_key(session, plaintext) is None

        replacement, replacement_key = await bootstrap_admin(session, name="recovery admin")
        await session.commit()
        assert replacement.id != admin.id
        assert replacement.is_active
        assert await authenticate_api_key(session, replacement_key) == replacement
        with pytest.raises(RuntimeError):
            await bootstrap_admin(session, name="duplicate active admin")


@pytest.mark.asyncio
async def test_audit_event_shares_data_transaction_and_excludes_secret_and_full_text(
    session_factory: async_sessionmaker,
) -> None:
    async with session_factory() as session:
        with pytest.raises(RuntimeError, match="rollback probe"):
            async with session.begin():
                actor = ApiClient(
                    name="audit actor",
                    key_hash="safe-hash",
                    key_prefix="test",
                    role="admin",
                    is_active=True,
                )
                session.add(actor)
                await session.flush()
                event = await record_event(
                    session,
                    actor_id=actor.id,
                    action="update",
                    entity_type="article",
                    entity_id=actor.id,
                    before=None,
                    after={
                        "status": "pending",
                        "api_key": "one-time-plaintext-secret",
                        "full_text": "complete article text",
                    },
                    request_id="req-rollback",
                )
                assert event.actor_id == actor.id
                raise RuntimeError("rollback probe")

        assert await session.scalar(select(func.count()).select_from(ApiClient)) == 0
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 0

        actor = ApiClient(
            name="audit actor",
            key_hash="safe-hash-committed",
            key_prefix="test",
            role="admin",
            is_active=True,
        )
        session.add(actor)
        await session.flush()
        event = await record_event(
            session,
            actor_id=actor.id,
            action="update",
            entity_type="article",
            entity_id=actor.id,
            before=None,
            after={
                "status": "pending",
                "api_key": "one-time-plaintext-secret",
                "full_text": "complete article text",
            },
            request_id="req-commit",
        )
        await session.commit()

        persisted = await session.get(AuditEvent, event.id)
        assert persisted is not None
        assert persisted.after == {"status": "pending"}
        assert "one-time-plaintext-secret" not in repr(persisted.after)
        assert "complete article text" not in repr(persisted.after)


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_contains_required_reference_and_sample_data(
    session_factory: async_sessionmaker,
) -> None:
    models: Iterable[type] = (
        RefEnum,
        License,
        TaxonomyRelease,
        Section,
        Move,
        Step,
        Intent,
        ArticleGenre,
        PhrasePattern,
        PatternVersion,
    )

    async def snapshot() -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        async with session_factory() as session:
            for model in models:
                rows = await session.scalars(select(model.id).order_by(model.id))
                result[model.__tablename__] = [str(row_id) for row_id in rows]
        return result

    async with session_factory() as session:
        await run_seed(session)
        await session.commit()
    first = await snapshot()

    async with session_factory() as session:
        await run_seed(session)
        await session.commit()
    second = await snapshot()

    assert second == first
    assert len(first["phrase_patterns"]) == 6

    async with session_factory() as session:
        licenses = await session.scalars(select(License))
        licenses_by_code = {license.code: license for license in licenses}
        assert set(licenses_by_code) == {
            "CC0",
            "CC-BY",
            "CC-BY-SA",
            "CC-BY-NC",
            "CC-BY-NC-SA",
            "CC-BY-ND",
            "CC-BY-NC-ND",
            "PROPRIETARY",
            "DEV-UNVERIFIED",
        }
        for code in ("CC0", "CC-BY", "CC-BY-SA", "DEV-UNVERIFIED"):
            assert licenses_by_code[code].allows_mining
            assert licenses_by_code[code].allows_display
        for code in ("CC-BY-NC", "CC-BY-NC-SA", "CC-BY-ND", "CC-BY-NC-ND"):
            assert not licenses_by_code[code].allows_mining
            assert not licenses_by_code[code].allows_display
        assert licenses_by_code["CC-BY"].allows_mining
        assert licenses_by_code["CC-BY"].allows_display
        assert not licenses_by_code["PROPRIETARY"].allows_mining
        assert not licenses_by_code["PROPRIETARY"].allows_display

        release = await session.scalar(
            select(TaxonomyRelease).where(TaxonomyRelease.version == "0.1.0")
        )
        assert release is not None and release.status == "published"
        sections = await session.scalars(select(Section.code))
        assert {"INTRO", "DISCUSSION"} <= set(sections)
