from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_gitignore_covers_runtime_data_and_secrets():
    rules = {line.strip() for line in read(".gitignore").splitlines() if line.strip() and not line.startswith("#")}
    required = {
        "data/*",
        "!data/.gitkeep",
        "*.db",
        "*.db-journal",
        "*.db-shm",
        "*.db-wal",
        "*.sqlite",
        "*.sqlite-journal",
        "*.sqlite-shm",
        "*.sqlite-wal",
        "*.sqlite3",
        "*.sqlite3-journal",
        "*.sqlite3-shm",
        "*.sqlite3-wal",
        "*.key",
        "*.log",
        ".env",
        ".env.*",
        "!.env.example",
    }
    assert required <= rules
    assert (ROOT / "data" / ".gitkeep").is_file()


def test_dockerignore_excludes_sensitive_context_without_dropping_inputs():
    rules = {line.strip() for line in read(".dockerignore").splitlines() if line.strip() and not line.startswith("#")}
    assert {".git", ".env", ".env.*", "data", "*.db", "*.key", "*.log", "node_modules", "__pycache__"} <= rules
    assert "package-lock.json" not in rules
    assert "requirements.txt" not in rules
    assert "app" not in rules


def test_environment_template_matches_supported_release_configuration():
    template = read(".env.example")
    expected = {
        "HOST_BIND": "127.0.0.1",
        "HOST_PORT": "8080",
        "DATA_DIR": "./data",
        "PUBLIC_BASE_URL": "",
        "ALLOWED_ORIGINS": "",
        "SECRET_KEY": "",
        "DEFAULT_TIMEZONE": "UTC",
        "LOG_RETENTION_DAYS": "30",
        "LOG_LEVEL": "INFO",
        "FORWARDED_ALLOW_IPS": "127.0.0.1",
    }
    values = {}
    for line in template.splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    assert values == expected
    assert "Leave empty to generate and persist" in template
    assert "Migration bridge only" in template


def test_compose_uses_real_image_safe_binding_and_named_volume():
    published = read("compose.yml")
    local = read("compose.build.yml")
    assert "ghcr.io/trquan06/e5-auto-renew:2.0.0" in published
    for content in (published, local):
        assert "DATA_DIR: /app/data" in content
        assert "${HOST_BIND:-127.0.0.1}:${HOST_PORT:-8080}:8080" in content
        assert "FORWARDED_ALLOW_IPS: ${FORWARDED_ALLOW_IPS:-127.0.0.1}" in content
        assert "e5_data:/app/data" in content
        assert "./data:/app/data" not in content


def test_dockerfile_is_non_root_and_has_no_wildcard_proxy_trust():
    dockerfile = read("Dockerfile")
    assert 'org.opencontainers.image.source="https://github.com/trquan06/E5-Auto-Renew"' in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert 'FORWARDED_ALLOW_IPS=127.0.0.1' in dockerfile
    assert "--forwarded-allow-ips" not in dockerfile
    assert re.search(r"COPY --chown=app:app run\.py ./run\.py", dockerfile)
    assert "HEALTHCHECK" in dockerfile
    assert "http://127.0.0.1:8080/health" in dockerfile


def test_release_version_is_synchronized():
    project = tomllib.loads(read("pyproject.toml"))
    package = json.loads(read("package.json"))
    lock = json.loads(read("package-lock.json"))
    config = read("app/config.py")
    assert project["project"]["version"] == "2.0.0"
    assert package["version"] == "2.0.0"
    assert lock["version"] == "2.0.0"
    assert lock["packages"][""]["version"] == "2.0.0"
    assert 'APP_VERSION: str = "2.0.0"' in config
    assert (ROOT / "CHANGELOG.md").is_file()


def test_release_consumers_have_no_legacy_owner_or_wrong_folder_placeholders():
    forbidden = ("OW" + "NER", "cd " + "ms365-auto-renew", "MS365_" + "IMAGE")
    consumers = [
        "Dockerfile",
        "compose.yml",
        "compose.build.yml",
        "README.md",
        "README.vi.md",
        "GITHUB_PACKAGE.md",
        "PLAN.md",
        "TASK_CHECKLIST.md",
        "docs/DEPLOYMENT.md",
        "docs/ENTRA_SETUP.md",
        "docs/OPERATIONS.md",
        "portainer/stack.image.yml",
        "portainer/stack.build.yml",
    ]
    for name in consumers:
        content = read(name)
        assert all(marker not in content for marker in forbidden), name


def test_windows_launcher_uses_repository_root_and_has_dependency_check():
    batch = read("run.bat")
    assert 'cd /d "%~dp0"' in batch
    assert '"%PYTHON_LAUNCHER%" run.py' in batch
    assert 'import fastapi, uvicorn' in batch
    assert "--check" in batch
    assert "%~dp0" + "ms365-auto-renew" not in batch
