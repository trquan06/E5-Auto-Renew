"""Application configuration and persistent secret management."""

from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings


def _read_or_create_secret(path: Path) -> str:
    """Read a durable secret or atomically create a mode-0600 secret file."""
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if len(value) < 32:
            raise RuntimeError(f"Secret file is invalid: {path}")
        return value

    value = secrets.token_urlsafe(48)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.write("\n")
    except FileExistsError:
        return _read_or_create_secret(path)

    try:
        path.chmod(0o600)
    except OSError:
        pass
    return value


def _normalise_base_url(value: str) -> str:
    if not value:
        return ""
    candidate = value.strip().rstrip("/")
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("PUBLIC_BASE_URL must be an absolute http(s) URL")
    if parsed.query or parsed.fragment:
        raise ValueError("PUBLIC_BASE_URL cannot contain a query or fragment")
    return candidate


class Settings(BaseSettings):
    APP_NAME: str = "MS365 Auto Renew"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8080

    DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"
    DATABASE_URL: str = ""
    SECRET_KEY: str = ""
    # Compatibility bridge for explicitly configured v1 installations.
    WEBUI_PASSWORD: str = ""

    PUBLIC_BASE_URL: str = ""
    ALLOWED_ORIGINS: str = ""
    SETUP_CODE_TTL_SECONDS: int = 900
    LOGIN_RATE_LIMIT: int = 5
    LOGIN_RATE_WINDOW_SECONDS: int = 60
    SETUP_RATE_LIMIT: int = 5
    SETUP_RATE_WINDOW_SECONDS: int = 900

    MS_AUTHORITY: str = "https://login.microsoftonline.com"
    MS_GRAPH_BASE: str = "https://graph.microsoft.com"
    MS_SCOPES: list[str] = [
        "https://graph.microsoft.com/Mail.ReadWrite",
        "https://graph.microsoft.com/Calendars.ReadWrite",
        "https://graph.microsoft.com/Tasks.ReadWrite",
        "https://graph.microsoft.com/Files.ReadWrite",
        "https://graph.microsoft.com/Team.ReadBasic.All",
        "https://graph.microsoft.com/Group.Read.All",
        "https://graph.microsoft.com/User.Read",
        "https://graph.microsoft.com/Notes.Read",
        "offline_access",
    ]

    DEFAULT_INTERVAL_HOURS: int = 3
    DEFAULT_JITTER_MIN_MINUTES: int = 15
    DEFAULT_JITTER_MAX_MINUTES: int = 40
    DEFAULT_ACTIVE_HOUR_START: int = 8
    DEFAULT_ACTIVE_HOUR_END: int = 22
    DEFAULT_TIMEZONE: str = "UTC"

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    DISCORD_WEBHOOK_URL: str = ""
    ONEDRIVE_MAX_FILES: int = 10
    LOG_RETENTION_DAYS: int = 30

    def model_post_init(self, __context: object) -> None:
        data_dir = self.DATA_DIR.expanduser().resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        object.__setattr__(self, "DATA_DIR", data_dir)

        if not self.DATABASE_URL:
            db_path = (data_dir / "renew.db").as_posix()
            object.__setattr__(self, "DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

        if not self.SECRET_KEY:
            object.__setattr__(self, "SECRET_KEY", _read_or_create_secret(data_dir / "secret.key"))

        object.__setattr__(self, "PUBLIC_BASE_URL", _normalise_base_url(self.PUBLIC_BASE_URL))
        object.__setattr__(self, "LOG_LEVEL", self.LOG_LEVEL.upper())

    @property
    def AES_KEY(self) -> bytes:
        return hashlib.sha256(self.SECRET_KEY.encode("utf-8")).digest()

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
