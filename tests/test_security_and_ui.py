import re
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import jwt

from app.config import _read_or_create_secret, settings
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
