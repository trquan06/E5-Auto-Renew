"""System settings and notification test endpoints."""

from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_admin
from app.config import settings
from app.database import get_db
from app.models.system_setting import SystemSetting
from app.services.notifier_service import NotifierService
from app.services.setup_service import pwd_context

router = APIRouter(prefix="/api/settings", tags=["Settings"])


class SettingsUpdate(BaseModel):
    webui_password: Optional[str] = Field(default=None, min_length=12, max_length=256)
    telegram_bot_token: Optional[str] = Field(default=None, max_length=512)
    telegram_chat_id: Optional[str] = Field(default=None, max_length=100)
    discord_webhook_url: Optional[str] = Field(default=None, max_length=2048)


class TestNotificationRequest(BaseModel):
    channel: Literal["telegram", "discord", "all"] = "all"
    custom_message: Optional[str] = Field(default=None, max_length=1000)


async def get_or_set_setting(db: AsyncSession, key: str, value: Optional[str] = None) -> Optional[str]:
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    if value is not None:
        if setting:
            setting.value = value
        else:
            db.add(SystemSetting(key=key, value=value))
        await db.commit()
        return value
    return setting.value if setting else getattr(settings, key.upper(), "")


@router.get("")
async def get_settings(db: AsyncSession = Depends(get_db), admin: str = Depends(get_current_admin)):
    telegram_token = await get_or_set_setting(db, "telegram_bot_token")
    telegram_chat = await get_or_set_setting(db, "telegram_chat_id")
    discord_url = await get_or_set_setting(db, "discord_webhook_url")
    password_hash = await get_or_set_setting(db, "webui_password_hash")
    return {
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "timezone": settings.DEFAULT_TIMEZONE,
        "public_base_url": settings.PUBLIC_BASE_URL,
        "telegram_bot_token": f"{telegram_token[:6]}…{telegram_token[-4:]}" if telegram_token and len(telegram_token) > 10 else ("Configured" if telegram_token else ""),
        "telegram_chat_id": telegram_chat or "",
        "discord_webhook_url": f"{discord_url[:20]}…{discord_url[-6:]}" if discord_url and len(discord_url) > 26 else ("Configured" if discord_url else ""),
        "has_telegram": bool(telegram_token and telegram_chat),
        "has_discord": bool(discord_url),
        "has_password": bool(password_hash),
    }


@router.put("")
async def update_settings(
    payload: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    if payload.webui_password:
        await get_or_set_setting(db, "webui_password_hash", pwd_context.hash(payload.webui_password))
    if payload.telegram_bot_token is not None:
        await get_or_set_setting(db, "telegram_bot_token", payload.telegram_bot_token)
    if payload.telegram_chat_id is not None:
        await get_or_set_setting(db, "telegram_chat_id", payload.telegram_chat_id)
    if payload.discord_webhook_url is not None:
        await get_or_set_setting(db, "discord_webhook_url", payload.discord_webhook_url)
    return {"success": True, "message": "Settings saved."}


@router.post("/test-notification")
async def test_notification(
    payload: TestNotificationRequest,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    message = payload.custom_message or "Test notification from MS365 Auto Renew."
    results: dict[str, str] = {}
    if payload.channel in {"telegram", "all"}:
        ok = await NotifierService.send_telegram(f"*[MS365 Auto Renew]*\n{message}", db_session=db)
        results["telegram"] = "sent" if ok else "failed"
    if payload.channel in {"discord", "all"}:
        ok = await NotifierService.send_discord(
            title="MS365 Auto Renew: test notification",
            description=message,
            color=0x3498DB,
            db_session=db,
        )
        results["discord"] = "sent" if ok else "failed"
    return {"success": any(value == "sent" for value in results.values()), "results": results}
