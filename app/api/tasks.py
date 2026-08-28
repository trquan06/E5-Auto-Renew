"""
Tasks API Router - Cấu hình tác vụ, tần suất, Jitter và Kích hoạt chạy thủ công "Run Now".
"""
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.account import Account
from app.models.task_config import TaskConfig
from app.services.task_executor import TaskExecutor
from app.services.scheduler_service import scheduler_service
from app.api.auth import get_current_admin

router = APIRouter(prefix="/api/accounts/{account_id}", tags=["Tasks"])


class TaskConfigUpdate(BaseModel):
    interval_hours: Optional[int] = Field(None, ge=1, le=48, description="Chu kỳ chạy (giờ)")
    jitter_min_minutes: Optional[int] = Field(None, ge=0, le=120, description="Jitter tối thiểu (phút)")
    jitter_max_minutes: Optional[int] = Field(None, ge=0, le=240, description="Jitter tối đa (phút)")
    active_hour_start: Optional[int] = Field(None, ge=0, le=23, description="Giờ bắt đầu hoạt động (0-23)")
    active_hour_end: Optional[int] = Field(None, ge=0, le=23, description="Giờ kết thúc hoạt động (0-23)")
    timezone: Optional[str] = Field(None, description="Tên timezone ví dụ Asia/Ho_Chi_Minh")

    enable_mail: Optional[bool] = None
    enable_calendar: Optional[bool] = None
    enable_todo: Optional[bool] = None
    enable_teams: Optional[bool] = None
    enable_onedrive: Optional[bool] = None
    enable_onenote: Optional[bool] = None
    enable_profile: Optional[bool] = None
    skip_ratio: Optional[float] = Field(None, ge=0.0, le=0.8, description="Tỷ lệ bỏ qua tác vụ mô phỏng")

    @model_validator(mode="after")
    def validate_ranges(self):
        if (
            self.jitter_min_minutes is not None
            and self.jitter_max_minutes is not None
            and self.jitter_min_minutes > self.jitter_max_minutes
        ):
            raise ValueError("jitter_min_minutes cannot exceed jitter_max_minutes")
        if (
            self.active_hour_start is not None
            and self.active_hour_end is not None
            and self.active_hour_start == self.active_hour_end
        ):
            raise ValueError("The active-hours window cannot be empty")
        return self


@router.get("/config")
async def get_task_config(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    """Lấy cấu hình tác vụ và lịch trình hiện tại của tài khoản."""
    stmt = select(TaskConfig).where(TaskConfig.account_id == account_id)
    res = await db.execute(stmt)
    config = res.scalar_one_or_none()

    if not config:
        # Tạo mới nếu chưa có
        config = TaskConfig(account_id=account_id)
        db.add(config)
        await db.commit()
        await db.refresh(config)

    return {
        "id": config.id,
        "account_id": config.account_id,
        "interval_hours": config.interval_hours,
        "jitter_min_minutes": config.jitter_min_minutes,
        "jitter_max_minutes": config.jitter_max_minutes,
        "active_hour_start": config.active_hour_start,
        "active_hour_end": config.active_hour_end,
        "timezone": config.timezone,
        "enable_mail": config.enable_mail,
        "enable_calendar": config.enable_calendar,
        "enable_todo": config.enable_todo,
        "enable_teams": config.enable_teams,
        "enable_onedrive": config.enable_onedrive,
        "enable_onenote": config.enable_onenote,
        "enable_profile": config.enable_profile,
        "skip_ratio": config.skip_ratio,
        "next_run_at": config.next_run_at.isoformat() if config.next_run_at else None,
    }


@router.put("/config")
async def update_task_config(
    account_id: int,
    req: TaskConfigUpdate,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    """Cập nhật cấu hình tác vụ và tính toán lại lịch chạy tiếp theo."""
    stmt = select(TaskConfig).where(TaskConfig.account_id == account_id)
    res = await db.execute(stmt)
    config = res.scalar_one_or_none()

    if not config:
        config = TaskConfig(account_id=account_id)
        db.add(config)

    for field, val in req.model_dump(exclude_unset=True).items():
        setattr(config, field, val)

    await db.commit()

    # Lên lịch lại sau khi thay đổi cấu hình
    next_run = await scheduler_service.schedule_account(account_id)

    return {
        "success": True,
        "message": "Task configuration updated.",
        "next_run_at": next_run.isoformat() if next_run else None,
    }


@router.post("/run-now")
async def trigger_run_now(
    account_id: int,
    wait: bool = False,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    """
    Kích hoạt thực thi chuỗi tác vụ Graph API ngay lập tức cho tài khoản.
    """
    stmt = select(Account).where(Account.id == account_id)
    res = await db.execute(stmt)
    account = res.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail={"code": "account_not_found", "message": "Account not found."})

    if wait:
        # Chạy đồng bộ và trả về kết quả ngay
        result = await TaskExecutor.execute_account_tasks(account_id, is_manual=True)
        return result
    else:
        # Chạy nền không chặn response
        asyncio.create_task(TaskExecutor.execute_account_tasks(account_id, is_manual=True))
        return {
            "success": True,
            "message": f"A background run was started for '{account.name}'.",
            "account_id": account_id,
        }
