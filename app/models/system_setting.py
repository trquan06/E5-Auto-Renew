"""
Model SystemSetting - Lưu trữ cấu hình toàn cục hệ thống (WebUI Password, Webhooks).
"""
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime

from app.database import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True, unique=True, index=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
