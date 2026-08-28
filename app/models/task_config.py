"""
Model TaskConfig - Cấu hình tác vụ, tần suất, Jitter và Active Hours cho từng tài khoản.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Boolean, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship

from app.database import Base


class TaskConfig(Base):
    __tablename__ = "task_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Interval and bounded scheduling variance.
    interval_hours = Column(Integer, default=3)           # Khoảng cách giữa các lần chạy (giờ)
    jitter_min_minutes = Column(Integer, default=15)      # Sai số ngẫu nhiên tối thiểu (phút)
    jitter_max_minutes = Column(Integer, default=40)      # Sai số ngẫu nhiên tối đa (phút)

    # Khung giờ hoạt động (Active Hours)
    active_hour_start = Column(Integer, default=8)        # Giờ bắt đầu hoạt động trong ngày (0-23)
    active_hour_end = Column(Integer, default=22)         # Giờ kết thúc hoạt động trong ngày (0-23)
    timezone = Column(String(50), default="Asia/Ho_Chi_Minh")

    # Bật / tắt các nhóm tác vụ Microsoft Graph
    enable_mail = Column(Boolean, default=True)           # Đọc thư, tạo thư nháp ngẫu nhiên
    enable_calendar = Column(Boolean, default=True)       # Đọc lịch, tạo cuộc họp giả lập, dọn dẹp
    enable_todo = Column(Boolean, default=True)           # Microsoft To-Do task management
    enable_teams = Column(Boolean, default=True)          # Đọc Teams, Groups, Channels
    enable_onedrive = Column(Boolean, default=True)       # Upload file ngẫu nhiên & dọn dẹp theo quota
    enable_onenote = Column(Boolean, default=True)        # Đọc OneNote notebooks
    enable_profile = Column(Boolean, default=True)        # Đọc Profile & Quota info

    # Optional sampling ratio used to keep development/test volume bounded.
    skip_ratio = Column(Float, default=0.15)

    # Thời gian chạy kế tiếp (được Scheduler cập nhật)
    next_run_at = Column(DateTime, nullable=True)

    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Quan hệ
    account = relationship("Account", back_populates="task_config")
