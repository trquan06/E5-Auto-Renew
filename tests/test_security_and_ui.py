import re
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import jwt
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.config import Settings, _read_or_create_secret, settings
from app.services.oauth_state import ALGORITHM, oauth_state_manager

ROOT = Path(__file__).resolve().parents[1]


def test_persistent_secret_is_stable_and_private(tmp_path):
    path = tmp_path / "secret.key"
    first = _read_or_create_secret(path)
    second = _read_or_create_secret(path)
    assert first == second and len(first) >= 32
    if os.name != "nt":
        assert path.stat().st_mode & 0o077 == 0


def test_expired_oauth_state_is_rejected():
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"type": "oauth_state", "jti": "expired", "client_id": "client", "tenant_id": "common", "origin": "http://test", "iat": now-timedelta(minutes=20), "exp": now-timedelta(minutes=10)},
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )
    with pytest.raises(ValueError, match="oauth_state_expired"):
        oauth_state_manager.verify(token)


def catalog_keys(path):
    return set(re.findall(r"^\s*'([^']+)'\s*:", path.read_text(encoding="utf-8"), re.MULTILINE))


def test_translation_catalog_parity():
    folder = ROOT / "app" / "static" / "js" / "i18n"
    keys = [catalog_keys(folder / name) for name in ("en.js", "vi.js", "zh-CN.js")]
    assert keys[0]
    assert keys[0] == keys[1] == keys[2]


def test_static_ui_uses_local_assets_and_modular_i18n():
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert "cdn." not in html.lower()
    assert "/static/css/tailwind.css" in html
    assert "/static/vendor/chart.umd.min.js" in html
    assert 'data-i18n="setup.title"' in html
    assert (ROOT / "app" / "static" / "css" / "tailwind.css").stat().st_size > 1000
    assert (ROOT / "app" / "static" / "vendor" / "chart.umd.min.js").stat().st_size > 10000


def test_release_tree_has_no_known_sample_credentials():
    forbidden = re.compile(r"admin123|ms365_secret_key_super_secure|invalid_token_sample", re.IGNORECASE)
    for folder in (ROOT / "app", ROOT / "docs"):
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".js", ".html", ".md", ".yml", ".yaml"}:
                assert not forbidden.search(path.read_text(encoding="utf-8", errors="ignore")), path


def test_forwarded_proxy_wildcard_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="wildcard trust is forbidden"):
        Settings(DATA_DIR=tmp_path, SECRET_KEY="test-secret-that-is-longer-than-thirty-two-characters", FORWARDED_ALLOW_IPS="*")


@pytest.mark.asyncio
async def test_untrusted_forwarded_headers_do_not_change_client_or_scheme():
    probe = FastAPI()

    @probe.get("/")
    async def identity(request: Request):
        return {"client": request.client.host, "scheme": request.url.scheme, "host": request.url.hostname}

    wrapped = ProxyHeadersMiddleware(probe, trusted_hosts=["127.0.0.1"])
    transport = ASGITransport(app=wrapped, client=("203.0.113.25", 50000))
    async with AsyncClient(transport=transport, base_url="http://service") as probe_client:
        response = await probe_client.get(
            "/",
            headers={"X-Forwarded-For": "198.51.100.90", "X-Forwarded-Proto": "https"},
        )
    assert response.json() == {"client": "203.0.113.25", "scheme": "http", "host": "service"}


@pytest.mark.asyncio
async def test_trusted_proxy_headers_preserve_external_client_and_scheme():
    probe = FastAPI()

    @probe.get("/")
    async def identity(request: Request):
        return {"client": request.client.host, "scheme": request.url.scheme, "host": request.url.hostname}

    wrapped = ProxyHeadersMiddleware(probe, trusted_hosts=["10.0.0.10"])
    transport = ASGITransport(app=wrapped, client=("10.0.0.10", 50000))
    async with AsyncClient(transport=transport, base_url="http://service") as probe_client:
        response = await probe_client.get(
            "/",
            headers={
                "Host": "app.example.test",
                "X-Forwarded-For": "198.51.100.90",
                "X-Forwarded-Proto": "https",
            },
        )
    assert response.json() == {"client": "198.51.100.90", "scheme": "https", "host": "app.example.test"}


@pytest.mark.asyncio
async def test_security_headers_cover_static_and_sensitive_api(client):
    static_response = await client.get("/")
    assert static_response.headers["content-security-policy"] == (
        "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; font-src 'self' data:; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
    )
    assert static_response.headers["x-frame-options"] == "DENY"
    assert static_response.headers["x-content-type-options"] == "nosniff"
    assert static_response.headers["referrer-policy"] == "no-referrer"

    protected_response = await client.get("/api/accounts")
    assert protected_response.status_code == 503
    assert protected_response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_docs_csp_allows_fastapi_assets(initialized_client):
    response = await initialized_client.get("/docs")
    assert response.status_code == 200
    policy = response.headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" in policy
    assert "frame-ancestors 'none'" in policy


@pytest.mark.asyncio
async def test_oauth_popup_keeps_nonce_based_csp(initialized_client, auth_headers):
    authorize = await initialized_client.get(
        "/api/accounts/oauth/authorize-url",
        params={"client_id": "dummy-client-id", "tenant_id": "common"},
        headers={**auth_headers, "Origin": "http://test"},
    )
    state = re.search(r"[?&]state=([^&]+)", authorize.json()["auth_url"]).group(1)
    from urllib.parse import unquote

    callback = await initialized_client.get(
        "/api/accounts/oauth/callback",
        params={"code": "test-code", "state": unquote(state)},
    )
    policy = callback.headers["content-security-policy"]
    assert "script-src 'nonce-" in policy
    assert "style-src 'nonce-" in policy
    assert "unsafe-inline" not in policy
