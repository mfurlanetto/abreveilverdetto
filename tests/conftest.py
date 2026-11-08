import os
import uuid

import pytest

from abreveilverdetto.storage import MemoryStorage, PostgresStorage

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(params=["memory", "postgres"])
async def storage(request):
    """Ogni test di storage gira su entrambe le implementazioni.

    Postgres richiede TEST_DATABASE_URL; ogni test usa uno schema isolato.
    """
    if request.param == "memory":
        s = MemoryStorage()
        await s.setup()
        yield s
        return

    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL non impostato")
    import asyncpg

    schema = f"test_{uuid.uuid4().hex[:12]}"
    admin = await asyncpg.connect(TEST_DATABASE_URL)
    await admin.execute(f'CREATE SCHEMA "{schema}"')
    sep = "&" if "?" in TEST_DATABASE_URL else "?"
    s = PostgresStorage(f"{TEST_DATABASE_URL}{sep}options=-csearch_path%3D{schema}")
    await s.setup()
    try:
        yield s
    finally:
        await s.close()
        await admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
        await admin.close()
