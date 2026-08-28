"""
Test suite cho SchedulerService và tính toán Jitter / Active Hours (scheduler_service.py).
"""
import pytest
from datetime import datetime, timezone
import pytz

from app.models.task_config import TaskConfig
from app.services.scheduler_service import scheduler_service


def test_jitter_interval_range():
    """Kiểm tra thời gian chạy tiếp theo luôn nằm trong khoảng hợp lý của Jitter."""
    config = TaskConfig(
        interval_hours=2,
        jitter_min_minutes=15,
        jitter_max_minutes=30,
        active_hour_start=0,
        active_hour_end=24,
        timezone="Asia/Ho_Chi_Minh",
    )
    now = datetime(2026, 8, 27, 10, 0, 0, tzinfo=timezone.utc)
    next_run = scheduler_service.calculate_next_run_time(config, from_time=now)

    assert next_run > now
    diff_minutes = (next_run - now).total_seconds() / 60.0
    # Interval = 120m, Jitter = ±15~30m -> Range: 90m ~ 150m
    assert 85 <= diff_minutes <= 155


def test_active_hours_late_night_rescheduling():
    """Kiểm tra nếu thời gian chạy rơi vào ban đêm (sau 22:00) thì tự động chuyển sang sáng hôm sau (08:00+)."""
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    # 15:30 UTC = 22:30 giờ VN
    late_night_utc = datetime(2026, 8, 27, 15, 30, 0, tzinfo=timezone.utc)

    config = TaskConfig(
        interval_hours=1,
        jitter_min_minutes=10,
        jitter_max_minutes=20,
        active_hour_start=8,
        active_hour_end=22,
        timezone="Asia/Ho_Chi_Minh",
    )

    next_run = scheduler_service.calculate_next_run_time(config, from_time=late_night_utc)
    next_run_local = next_run.astimezone(tz)

    # Phải được chuyển sang sáng ngày hôm sau vào khung 08:00
    assert next_run_local.day == 28
    assert next_run_local.hour == 8
    assert 5 <= next_run_local.minute <= 40
