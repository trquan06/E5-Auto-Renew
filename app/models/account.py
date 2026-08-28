"""
Model Account - Quản lý thông tin tài khoản Microsoft 365.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)                         # Tên gợi nhớ (e.g., "Main E5 Dev")
    client_id = Column(String(100), nullable=False)                    # Azure App (client) ID
    client_secret_encrypted = Column(Text, nullable=True)              # Client Secret (mã hóa AES-GCM)
    tenant_id = Column(String(100), nullable=False, default="common")  # Azure Tenant ID
    refresh_token_encrypted = Column(Text, nullable=True)              # OAuth2 Refresh Token (mã hóa AES-GCM)
    access_token_encrypted = Column(Text, nullable=True)               # Cached Access Token (mã hóa AES-GCM)
    token_expires_at = Column(DateTime, nullable=True)                 # Thời điểm hết hạn token
    auth_mode = Column(String(20), nullable=False, default="delegated")  # Delegated user OAuth only.

    # Thông tin tài khoản lấy từ Graph API /me
    email = Column(String(255), nullable=True)                         # User Principal Name
    display_name = Column(String(255), nullable=True)                  # Tên hiển thị người dùng

    # Trạng thái
    status = Column(String(20), nullable=False, default="active")       # active, expired, error, disabled
    last_run_at = Column(DateTime, nullable=True)                      # Lần chạy gần nhất
    last_status = Column(String(20), nullable=True)                     # success, partial, failed
    last_error = Column(Text, nullable=True)                           # Lỗi gần nhất nếu có

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Quan hệ
    task_config = relationship("TaskConfig", back_populates="account", uselist=False, cascade="all, delete-orphan")
    logs = relationship("ExecutionLog", back_populates="account", cascade="all, delete-orphan", order_by="desc(ExecutionLog.created_at)")
