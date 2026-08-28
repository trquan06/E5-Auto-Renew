import os
import tempfile
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="ms365-v2-tests-"))
os.environ["DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["SECRET_KEY"] = "test-only-stable-secret-key-that-is-longer-than-thirty-two-characters"
os.environ.pop("WEBUI_PASSWORD", None)

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.security import rate_limiter  # noqa: E402
from app.services.oauth_state import oauth_state_manager  # noqa: E402
from app.services.setup_service import setup_manager  # noqa: E402

ADMIN_PASSWORD = "correct horse battery staple"


@pytest_asyncio.fixture(autouse=True)
async def clean_runtime():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    setup_manager.initialized = False
    setup_manager._code_digest = None
    setup_manager._expires_at = None
    setup_manager._used = False
    rate_limiter._events.clear()
    oauth_state_manager._consumed.clear()
    yield


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as instance:
        yield instance


@pytest_asyncio.fixture
async def initialized_client(client):
    code = setup_manager.issue_code()
    response = await client.post("/api/setup/initialize", json={"setup_code": code, "password": ADMIN_PASSWORD})
    assert response.status_code == 200
    return client


@pytest_asyncio.fixture
async def auth_headers(initialized_client):
    response = await initialized_client.post("/api/auth/login", json={"password": ADMIN_PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
