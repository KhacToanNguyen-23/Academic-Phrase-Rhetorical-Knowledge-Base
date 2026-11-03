from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from aprkb.modules.vocabulary.models import VocabLemma


@pytest.mark.asyncio
async def test_lemma_word_pos_is_unique(postgres_test_engine: AsyncEngine) -> None:
    factory = async_sessionmaker(postgres_test_engine, expire_on_commit=False)
    async with factory() as session:
        session.add(VocabLemma(word=f"schema-{uuid4().hex[:8]}", pos="n"))
        await session.commit()
        lemma = await session.scalar(select(VocabLemma).order_by(VocabLemma.created_at.desc()))
        assert lemma is not None
        session.add(VocabLemma(word=lemma.word, pos=lemma.pos))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
