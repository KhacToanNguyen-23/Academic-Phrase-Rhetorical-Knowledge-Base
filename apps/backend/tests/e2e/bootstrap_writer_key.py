"""Create a disposable client key for the isolated browser-test database."""

import asyncio
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from aprkb.modules.identity.service import create_api_key


async def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    if "/aprkb_test" not in database_url:
        raise RuntimeError("Browser test key may only be created in aprkb_test")
    output = Path(os.environ["WRITER_E2E_KEY_FILE"])
    engine = create_async_engine(database_url)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            _, key = await create_api_key(session, name="writer browser test", role="client")
            await session.commit()
        output.write_text(key, encoding="utf-8")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
