"""
SchedulerService - Quản lý APScheduler độc lập cho từng tài khoản.
Tích hợp tính toán Random Jitter (±15~40m) và kiểm tra khung giờ hoạt động (Active Hours Window).
"""
import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import Optional
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.account import Account
from app.models.task_config import TaskConfig


class SchedulerService:
    """Service điều phối lịch trình chạy tự động đa tài khoản."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=timezone.utc)
        self.is_running = False

    def start(self) -> None:
        """Khởi động APScheduler."""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True

    def shutdown(self) -> None:
        """Dừng APScheduler."""
        if self.is_running:
            self.scheduler.shutdown(wait=False)
            self.is_running = False

    @staticmethod
    def calculate_next_run_time(config: TaskConfig, from_time: Optional[datetime] = None) -> datetime:
        """
        Tính toán thời điểm chạy tiếp theo có tính đến:
        1. Chu kỳ lặp cơ sở (interval_hours)
        2. Random Jitter (± min ~ max minutes)
        3. Khung giờ hoạt động (Active Hours Window theo múi giờ tài khoản)
        
        Returns:
            datetime dạng UTC có timezone info.
        """
        now_utc = from_time or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        # 1. Tính khoảng thời gian ngẫu nhiên (Interval + Jitter)
        base_minutes = max(1, config.interval_hours or 3) * 60
        j_min = max(0, config.jitter_min_minutes if config.jitter_min_minutes is not None else 15)
        j_max = max(j_min, config.jitter_max_minutes if config.jitter_max_minutes is not None else 40)
        
        jitter_delta = random.randint(j_min, j_max)
        sign = random.choice([-1, 1])
        total_delay_minutes = max(20, base_minutes + (sign * jitter_delta))

        target_utc = now_utc + timedelta(minutes=total_delay_minutes)

        # 2. Xử lý khung giờ hoạt động (Active Hours) theo Timezone
        try:
            tz = pytz.timezone(config.timezone or "Asia/Ho_Chi_Minh")
        except Exception:
            tz = pytz.timezone("Asia/Ho_Chi_Minh")

        start_h = config.active_hour_start if config.active_hour_start is not None else 8
        end_h = config.active_hour_end if config.active_hour_end is not None else 22

        # Chuyển target_utc sang múi giờ địa phương
        local_dt = target_utc.astimezone(tz)
        local_hour = local_dt.hour + (local_dt.minute / 60.0)

        # Trường hợp 1: target_utc rơi vào ban đêm sau giờ kết thúc (ví dụ sau 22:00)
        if local_hour >= end_h:
            # Chuyển sang sáng hôm sau vào start_hour + ngẫu nhiên 5~35 phút jitter
            morning_jitter = random.randint(5, 35)
            next_day = local_dt.date() + timedelta(days=1)
            adjusted_local = tz.localize(
                datetime(next_day.year, next_day.month, next_day.day, start_h, morning_jitter, 0)
            )
            target_utc = adjusted_local.astimezone(timezone.utc)

        # Trường hợp 2: target_utc rơi vào rạng sáng trước giờ bắt đầu (ví dụ 03:00 sáng)
        elif local_hour < start_h:
            morning_jitter = random.randint(5, 35)
            current_day = local_dt.date()
            adjusted_local = tz.localize(
                datetime(current_day.year, current_day.month, current_day.day, start_h, morning_jitter, 0)
            )
            target_utc = adjusted_local.astimezone(timezone.utc)

        return target_utc

    async def schedule_account(self, account_id: int, initial_delay_seconds: Optional[int] = None) -> Optional[datetime]:
        """
        Lên lịch tác vụ kế tiếp cho tài khoản và lưu `next_run_at` vào Database.
        """
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Account)
                .where(Account.id == account_id)
                .options(selectinload(Account.task_config))
            )
            result = await session.execute(stmt)
            account = result.scalar_one_or_none()

            if not account or account.status == "disabled":
                self.remove_job(account_id)
                return None

            config = account.task_config
            if not config:
                config = TaskConfig(account_id=account.id)
                session.add(config)
                await session.commit()
                await session.refresh(config)

            if initial_delay_seconds is not None:
                next_run = datetime.now(timezone.utc) + timedelta(seconds=initial_delay_seconds)
            else:
                next_run = self.calculate_next_run_time(config)

            config.next_run_at = next_run
            await session.commit()

            # Đăng ký / Thay thế job trong APScheduler
            job_id = f"account_job_{account_id}"
            
            # Xóa job cũ nếu có
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)

            self.scheduler.add_job(
                self._run_job_wrapper,
                trigger=DateTrigger(run_date=next_run),
                id=job_id,
                args=[account_id],
                replace_existing=True,
                name=f"MS365 development test for account #{account_id}",
            )

            return next_run

    def remove_job(self, account_id: int) -> None:
        """Hủy lịch chạy của tài khoản."""
        job_id = f"account_job_{account_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

    async def _run_job_wrapper(self, account_id: int) -> None:
        """
        Hàm callback khi trigger DateTrigger kích hoạt:
        1. Thực thi tác vụ qua TaskExecutor
        2. Tự động tính toán và đặt lịch chạy chu kỳ tiếp theo
        """
        from app.services.task_executor import TaskExecutor

        try:
            await TaskExecutor.execute_account_tasks(account_id, is_manual=False)
        except Exception as exc:
            pass  # Lỗi đã được TaskExecutor ghi log
        finally:
            # Lên lịch cho chu kỳ tiếp theo
            await self.schedule_account(account_id)

    async def load_and_schedule_all(self) -> None:
        """
        Khởi tạo và lên lịch cho tất cả tài khoản đang active khi ứng dụng khởi động.
        Phân bổ thời gian khởi chạy ban đầu (staggering) để tránh chạy dồn dập cùng 1 lúc.
        """
        async with AsyncSessionLocal() as session:
            stmt = select(Account).where(Account.status != "disabled")
            result = await session.execute(stmt)
            accounts = result.scalars().all()

            for i, account in enumerate(accounts):
                # Stagger delay: mỗi tài khoản cách nhau 30-90 giây ở lần khởi động đầu
                stagger_seconds = 15 + (i * 45) + random.randint(5, 20)
                await self.schedule_account(account.id, initial_delay_seconds=stagger_seconds)


# Singleton instance
scheduler_service = SchedulerService()
