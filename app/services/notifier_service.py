"""Telegram and Discord execution notifications."""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.system_setting import SystemSetting


class NotifierService:
    """Service hỗ trợ gửi thông báo qua Telegram và Discord."""

    @staticmethod
    async def get_setting_value(db_session: AsyncSession, key: str, default: str = "") -> str:
        """Lấy giá trị cấu hình từ DB (fallback về config.py nếu chưa lưu trong DB)."""
        result = await db_session.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = result.scalar_one_or_none()
        if setting and setting.value:
            return setting.value
        return getattr(settings, key.upper(), default)

    @classmethod
    async def send_telegram(
        cls,
        message: str,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        db_session: Optional[AsyncSession] = None,
    ) -> bool:
        """Gửi thông báo Markdown qua Telegram Bot."""
        if db_session:
            if not bot_token:
                bot_token = await cls.get_setting_value(db_session, "telegram_bot_token")
            if not chat_id:
                chat_id = await cls.get_setting_value(db_session, "telegram_chat_id")

        if not bot_token or not chat_id:
            return False

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload)
                return res.status_code == 200
        except Exception:
            return False

    @classmethod
    async def send_discord(
        cls,
        title: str,
        description: str,
        color: int = 0x3498DB,  # Default blue
        fields: Optional[List[Dict[str, Any]]] = None,
        webhook_url: Optional[str] = None,
        db_session: Optional[AsyncSession] = None,
    ) -> bool:
        """Gửi thông báo Rich Embed qua Discord Webhook."""
        if db_session and not webhook_url:
            webhook_url = await cls.get_setting_value(db_session, "discord_webhook_url")

        if not webhook_url:
            return False

        embed = {
            "title": title,
            "description": description,
            "color": color,
            "fields": fields or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": "MS365 Auto Renew System"},
        }
        payload = {"embeds": [embed]}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(webhook_url, json=payload)
                return res.status_code in [200, 204]
        except Exception:
            return False

    @classmethod
    async def notify_execution_summary(
        cls,
        account_name: str,
        total_tasks: int,
        success_tasks: int,
        failed_tasks: int,
        skipped_tasks: int,
        duration_ms: int,
        error_msg: Optional[str] = None,
        db_session: Optional[AsyncSession] = None,
    ) -> None:
        """Gửi tóm tắt chu kỳ thực thi đến các kênh đã cấu hình."""
        is_success = failed_tasks == 0
        status_text = "Successful" if is_success else "Completed with errors"
        color = 0x2ECC71 if is_success else 0xE74C3C  # Green or Red

        # 1. Telegram message
        tg_msg = (
            f"*[MS365 Auto Renew] Development/test run: {account_name}*\n"
            f"- Status: *{status_text}*\n"
            f"- Calls: `{total_tasks}` (successful: `{success_tasks}`, failed: `{failed_tasks}`, skipped: `{skipped_tasks}`)\n"
            f"- Duration: `{duration_ms}ms`\n"
        )
        if error_msg:
            tg_msg += f"- Error: `{error_msg[:150]}`\n"
        tg_msg += f"- Time: `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`"

        # 2. Discord Embed
        fields = [
            {"name": "Status", "value": status_text, "inline": True},
            {"name": "Duration", "value": f"{duration_ms}ms", "inline": True},
            {"name": "Results", "value": f"Successful {success_tasks} | Failed {failed_tasks} | Skipped {skipped_tasks}", "inline": False},
        ]
        if error_msg:
            fields.append({"name": "Error detail", "value": f"```{error_msg[:300]}```", "inline": False})

        # Gửi thông báo song song (không chặn luồng)
        await cls.send_telegram(tg_msg, db_session=db_session)
        await cls.send_discord(
            title=f"MS365 Auto Renew: {account_name}",
            description=f"The delegated Graph development/test run for **{account_name}** completed.",
            color=color,
            fields=fields,
            db_session=db_session,
        )
