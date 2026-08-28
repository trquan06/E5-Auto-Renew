from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import func, select

from app.database import AsyncSessionLocal
from app.models.account import Account
from app.models.execution_log import ExecutionLog
from app.models.system_setting import SystemSetting
from app.services.oauth_state import oauth_state_manager
from app.services.setup_service import pwd_context, setup_manager
ADMIN_PASSWORD = "correct horse battery staple"


@pytest.mark.asyncio
async def test_health_endpoints(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["version"] == "2.0.0"


@pytest.mark.asyncio
async def test_setup_gate_and_status_do_not_leak_code(client):
    status = await client.get("/api/setup/status")
    assert status.json() == {"is_initialized": False}
    assert "code" not in status.text.lower()
    protected = await client.get("/api/accounts")
    assert protected.status_code == 503
    assert protected.json()["detail"]["code"] == "setup_required"


@pytest.mark.asyncio
async def test_setup_wrong_valid_and_reuse(client):
    code = setup_manager.issue_code()
    wrong = await client.post("/api/setup/initialize", json={"setup_code": "AAAA-BBBB-CCCC", "password": ADMIN_PASSWORD})
    assert wrong.status_code == 400
    assert wrong.json()["detail"]["code"] == "setup_code_invalid"
    valid = await client.post("/api/setup/initialize", json={"setup_code": code, "password": ADMIN_PASSWORD})
    assert valid.status_code == 200
    reused = await client.post("/api/setup/initialize", json={"setup_code": code, "password": ADMIN_PASSWORD})
    assert reused.status_code == 400
    assert reused.json()["detail"]["code"] == "already_initialized"
    async with AsyncSessionLocal() as db:
        value = (await db.execute(select(SystemSetting.value).where(SystemSetting.key == "webui_password_hash"))).scalar_one()
        assert ADMIN_PASSWORD not in value
        assert pwd_context.verify(ADMIN_PASSWORD, value)


@pytest.mark.asyncio
async def test_setup_expired_code(client):
    code = setup_manager.issue_code()
    setup_manager._expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    response = await client.post("/api/setup/initialize", json={"setup_code": code, "password": ADMIN_PASSWORD})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "setup_code_expired"


@pytest.mark.asyncio
async def test_auth_and_login_flow(initialized_client, auth_headers):
    wrong = await initialized_client.post("/api/auth/login", json={"password": "wrong password"})
    assert wrong.status_code == 401
    accounts = await initialized_client.get("/api/accounts", headers=auth_headers)
    stats = await initialized_client.get("/api/logs/stats", headers=auth_headers)
    assert accounts.status_code == 200 and accounts.json() == []
    assert stats.status_code == 200 and stats.json()["total_accounts"] == 0
    assert (await initialized_client.get("/api/accounts")).status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limit(initialized_client):
    for _ in range(5):
        assert (await initialized_client.post("/api/auth/login", json={"password": "incorrect"})).status_code == 401
    limited = await initialized_client.post("/api/auth/login", json={"password": "incorrect"})
    assert limited.status_code == 429
    assert limited.json()["detail"]["code"] == "rate_limited"


@pytest.mark.asyncio
async def test_untrusted_forwarded_for_cannot_evade_login_rate_limit(initialized_client):
    for attempt in range(5):
        response = await initialized_client.post(
            "/api/auth/login",
            json={"password": "incorrect"},
            headers={"X-Forwarded-For": f"198.51.100.{attempt + 1}"},
        )
        assert response.status_code == 401
    limited = await initialized_client.post(
        "/api/auth/login",
        json={"password": "incorrect"},
        headers={"X-Forwarded-For": "203.0.113.250"},
    )
    assert limited.status_code == 429


@pytest.mark.asyncio
async def test_untrusted_forwarded_for_cannot_evade_setup_rate_limit(client):
    for attempt in range(5):
        response = await client.post(
            "/api/setup/initialize",
            json={"setup_code": "AAAA-BBBB-CCCC", "password": ADMIN_PASSWORD},
            headers={"X-Forwarded-For": f"198.51.100.{attempt + 1}"},
        )
        assert response.status_code == 400
    limited = await client.post(
        "/api/setup/initialize",
        json={"setup_code": "AAAA-BBBB-CCCC", "password": ADMIN_PASSWORD},
        headers={"X-Forwarded-For": "203.0.113.250"},
    )
    assert limited.status_code == 429


@pytest.mark.asyncio
async def test_oauth_endpoints(initialized_client, auth_headers):
    response = await initialized_client.get(
        "/api/accounts/oauth/authorize-url",
        params={"client_id": "dummy-client-id", "tenant_id": "common", "account_name": "Demo"},
        headers={**auth_headers, "Origin": "http://test"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["redirect_uri"] == "http://test/api/accounts/oauth/callback"
    query = parse_qs(urlsplit(data["auth_url"]).query)
    state = query["state"][0]
    state_payload = oauth_state_manager.verify(state)
    assert state_payload["origin"] == "http://test"
    callback = await initialized_client.get("/api/accounts/oauth/callback", params={"code": "mock-code-123", "state": state})
    assert callback.status_code == 200
    assert "history.replaceState" in callback.text
    assert "ms365-oauth-callback" in callback.text
    assert "postMessage" in callback.text
    invalid_redirect = await initialized_client.get(
        "/api/accounts/oauth/authorize-url",
        params={"client_id": "dummy-client-id", "redirect_uri": "https://evil.example/callback"},
        headers=auth_headers,
    )
    assert invalid_redirect.status_code == 400

    forwarded_spoof = await initialized_client.get(
        "/api/accounts/oauth/authorize-url",
        params={"client_id": "dummy-client-id", "tenant_id": "common", "account_name": "Demo"},
        headers={
            **auth_headers,
            "Origin": "http://test",
            "X-Forwarded-Host": "evil.example",
            "X-Forwarded-Proto": "https",
        },
    )
    assert forwarded_spoof.status_code == 200
    assert forwarded_spoof.json()["redirect_uri"] == "http://test/api/accounts/oauth/callback"


@pytest.mark.asyncio
async def test_oauth_exchange_is_single_use(initialized_client, auth_headers):
    auth = await initialized_client.get(
        "/api/accounts/oauth/authorize-url",
        params={"client_id": "dummy-client-id", "tenant_id": "common", "account_name": "Demo"},
        headers=auth_headers,
    )
    state = parse_qs(urlsplit(auth.json()["auth_url"]).query)["state"][0]
    tokens = {"access_token": "access-value", "refresh_token": "refresh-value", "expires_in": 3600}
    profile = {"userPrincipalName": "demo@example.test", "displayName": "Demo User"}
    with patch("app.api.accounts.AuthService.exchange_code_for_tokens", new=AsyncMock(return_value=tokens)), patch(
        "app.api.accounts.AuthService.fetch_user_profile", new=AsyncMock(return_value=profile)
    ), patch("app.api.accounts.scheduler_service.schedule_account", new=AsyncMock(return_value=None)):
        payload = {"code": "one-use-code", "state": state}
        first = await initialized_client.post("/api/accounts/oauth/callback", json=payload, headers=auth_headers)
        second = await initialized_client.post("/api/accounts/oauth/callback", json=payload, headers=auth_headers)
    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["detail"]["code"] == "oauth_state_used"
    async with AsyncSessionLocal() as db:
        account = (await db.execute(select(Account))).scalar_one()
        assert account.auth_mode == "delegated"
        assert "one-use-code" not in (account.refresh_token_encrypted or "")


@pytest.mark.asyncio
async def test_delegated_account_crud(initialized_client, auth_headers):
    payload = {"name": "Test", "client_id": "client-id-123", "tenant_id": "common", "refresh_token": "test-refresh"}
    with patch("app.api.accounts.scheduler_service.schedule_account", new=AsyncMock(return_value=None)):
        created = await initialized_client.post("/api/accounts", json=payload, headers=auth_headers)
    assert created.status_code == 201
    account = created.json()["account"]
    assert account["auth_mode"] == "delegated"
    assert "refresh_token" not in account
    account_id = account["id"]
    updated = await initialized_client.put(f"/api/accounts/{account_id}", json={"status": "disabled"}, headers=auth_headers)
    assert updated.status_code == 200
    deleted = await initialized_client.delete(f"/api/accounts/{account_id}", headers=auth_headers)
    assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_log_retention_clear(initialized_client, auth_headers):
    async with AsyncSessionLocal() as db:
        account = Account(name="Logs", client_id="client-id-logs", tenant_id="common", auth_mode="delegated")
        db.add(account);await db.flush()
        db.add_all([
            ExecutionLog(account_id=account.id, task_type="profile", is_success=True, created_at=datetime.now(timezone.utc)-timedelta(days=40)),
            ExecutionLog(account_id=account.id, task_type="profile", is_success=True, created_at=datetime.now(timezone.utc)),
        ])
        await db.commit()
    response = await initialized_client.delete("/api/logs/clear?days=30", headers=auth_headers)
    assert response.status_code == 200
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(func.count(ExecutionLog.id)))).scalar_one() == 1
