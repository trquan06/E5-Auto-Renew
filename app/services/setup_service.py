"""First-run setup lifecycle."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.system_setting import SystemSetting

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


class SetupManager:
    def __init__(self) -> None:
        self.initialized: bool | None = None
        self._code_digest: str | None = None
        self._expires_at: datetime | None = None
        self._used = False

    @staticmethod
    async def _password_setting(db: AsyncSession) -> SystemSetting | None:
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == "webui_password_hash"))
        return result.scalar_one_or_none()

    @staticmethod
    async def _set_setting(db: AsyncSession, key: str, value: str) -> None:
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            db.add(SystemSetting(key=key, value=value))

    async def prepare(self, db: AsyncSession) -> None:
        password_setting = await self._password_setting(db)
        if not password_setting and settings.WEBUI_PASSWORD:
            password_setting = SystemSetting(key="webui_password_hash", value=pwd_context.hash(settings.WEBUI_PASSWORD))
            db.add(password_setting)
            await self._set_setting(db, "setup_completed_at", datetime.now(timezone.utc).isoformat())
            await db.commit()
            logger.info("Migrated the legacy WEBUI_PASSWORD environment value to the database.")

        self.initialized = bool(password_setting and password_setting.value)
        if self.initialized:
            self._code_digest = None
            self._expires_at = None
            return
        self.issue_code()

    async def ensure_prepared(self) -> None:
        if self.initialized is not None:
            return
        async with AsyncSessionLocal() as db:
            await self.prepare(db)

    def issue_code(self) -> str:
        code = "-".join(
            "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(4))
            for _ in range(3)
        )
        self._code_digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
        self._expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.SETUP_CODE_TTL_SECONDS)
        self._used = False
        logger.warning("MS365 Auto Renew one-time setup code: %s", code)
        logger.warning("The setup code expires in 15 minutes and will change after a restart.")
        return code

    def validate_code(self, code: str) -> None:
        now = datetime.now(timezone.utc)
        supplied = hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()
        if self._used:
            raise ValueError("setup_code_used")
        if not self._expires_at or now >= self._expires_at:
            raise ValueError("setup_code_expired")
        if not self._code_digest or not secrets.compare_digest(supplied, self._code_digest):
            raise ValueError("setup_code_invalid")

    async def initialize(self, db: AsyncSession, code: str, password: str) -> None:
        if self.initialized:
            raise ValueError("already_initialized")
        self.validate_code(code)
        self._used = True
        password_setting = await self._password_setting(db)
        if password_setting:
            password_setting.value = pwd_context.hash(password)
        else:
            db.add(SystemSetting(key="webui_password_hash", value=pwd_context.hash(password)))
        await self._set_setting(db, "setup_completed_at", datetime.now(timezone.utc).isoformat())
        await db.commit()
        self.initialized = True
        self._code_digest = None
        self._expires_at = None


setup_manager = SetupManager()
