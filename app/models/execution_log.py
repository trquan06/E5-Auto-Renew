"""
Model ExecutionLog - Lưu trữ lịch sử chi tiết từng lệnh gọi Microsoft Graph API.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.database import Base


class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    task_type = Column(String(50), nullable=False, index=True)     # mail, calendar, todo, teams, onedrive, onenote, profile, full_cycle
    endpoint = Column(String(255), nullable=True)                  # /v1.0/me/messages, etc.
    method = Column(String(10), nullable=True, default="GET")       # GET, POST, PATCH, PUT, DELETE
    status_code = Column(Integer, nullable=True)                   # 200, 201, 401, 500, etc.
    duration_ms = Column(Integer, nullable=True)                   # Thời gian phản hồi tính bằng mili-giây
    is_success = Column(Boolean, nullable=False, default=True, index=True)

    response_snippet = Column(Text, nullable=True)                 # Tóm tắt kết quả trả về
    error_message = Column(Text, nullable=True)                    # Chi tiết lỗi nếu thất bại

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Quan hệ
    account = relationship("Account", back_populates="logs")
