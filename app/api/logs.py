"""Execution log and dashboard analytics endpoints."""
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.account import Account
from app.models.execution_log import ExecutionLog
from app.models.task_config import TaskConfig
from app.api.auth import get_current_admin
from app.services.scheduler_service import scheduler_service

router = APIRouter(prefix="/api/logs", tags=["Logs & Analytics"])


@router.get("")
async def get_logs(
    account_id: Optional[int] = Query(None, description="Filter by account ID"),
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    is_success: Optional[bool] = Query(None, description="Filter by success state"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=5, le=100, description="Entries per page"),
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    """Lấy danh sách lịch sử gọi API có hỗ trợ lọc và phân trang."""
    filters = []
    if account_id is not None:
        filters.append(ExecutionLog.account_id == account_id)
    if task_type:
        filters.append(ExecutionLog.task_type == task_type)
    if is_success is not None:
        filters.append(ExecutionLog.is_success == is_success)

    # Đếm tổng số bản ghi khớp bộ lọc
    count_stmt = select(func.count(ExecutionLog.id))
    if filters:
        count_stmt = count_stmt.where(and_(*filters))
    total_records = (await db.execute(count_stmt)).scalar() or 0

    # Lấy dữ liệu phân trang
    offset = (page - 1) * page_size
    query_stmt = (
        select(ExecutionLog)
        .options(selectinload(ExecutionLog.account))
        .order_by(desc(ExecutionLog.created_at))
        .offset(offset)
        .limit(page_size)
    )
    if filters:
        query_stmt = query_stmt.where(and_(*filters))

    res = await db.execute(query_stmt)
    logs = res.scalars().all()

    items = []
    for log in logs:
        items.append({
            "id": log.id,
            "account_id": log.account_id,
            "account_name": log.account.name if log.account else f"Account #{log.account_id}",
            "task_type": log.task_type,
            "endpoint": log.endpoint,
            "method": log.method,
            "status_code": log.status_code,
            "duration_ms": log.duration_ms,
            "is_success": log.is_success,
            "response_snippet": log.response_snippet,
            "error_message": log.error_message,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    total_pages = (total_records + page_size - 1) // page_size if total_records > 0 else 1

    return {
        "items": items,
        "total": total_records,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    """Lấy tổng hợp thống kê thời gian thực cho giao diện Dashboard."""
    # 1. Thống kê tài khoản
    total_accounts_stmt = select(func.count(Account.id))
    total_accounts = (await db.execute(total_accounts_stmt)).scalar() or 0

    active_accounts_stmt = select(func.count(Account.id)).where(Account.status == "active")
    active_accounts = (await db.execute(active_accounts_stmt)).scalar() or 0

    # 2. Thống kê lượt gọi API
    total_calls_stmt = select(func.count(ExecutionLog.id))
    total_calls = (await db.execute(total_calls_stmt)).scalar() or 0

    success_calls_stmt = select(func.count(ExecutionLog.id)).where(ExecutionLog.is_success == True)
    success_calls = (await db.execute(success_calls_stmt)).scalar() or 0

    failed_calls = total_calls - success_calls
    success_rate = round((success_calls / total_calls * 100), 1) if total_calls > 0 else 100.0

    # 3. Lượt gọi trong 24 giờ qua
    past_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    calls_24h_stmt = select(func.count(ExecutionLog.id)).where(ExecutionLog.created_at >= past_24h)
    calls_last_24h = (await db.execute(calls_24h_stmt)).scalar() or 0

    # 4. Phân bổ theo loại tác vụ (Task type breakdown)
    type_stmt = (
        select(ExecutionLog.task_type, func.count(ExecutionLog.id))
        .group_by(ExecutionLog.task_type)
    )
    type_res = await db.execute(type_stmt)
    type_breakdown = {row[0]: row[1] for row in type_res.all()}

    # 5. Dữ liệu biểu đồ 7 ngày gần nhất (Daily stats)
    daily_stats = []
    for i in range(6, -1, -1):
        day_start = (datetime.now(timezone.utc) - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        day_success_stmt = select(func.count(ExecutionLog.id)).where(
            ExecutionLog.created_at >= day_start,
            ExecutionLog.created_at < day_end,
            ExecutionLog.is_success == True,
        )
        day_failed_stmt = select(func.count(ExecutionLog.id)).where(
            ExecutionLog.created_at >= day_start,
            ExecutionLog.created_at < day_end,
            ExecutionLog.is_success == False,
        )
        s_cnt = (await db.execute(day_success_stmt)).scalar() or 0
        f_cnt = (await db.execute(day_failed_stmt)).scalar() or 0

        daily_stats.append({
            "date": day_start.strftime("%d/%m"),
            "success": s_cnt,
            "failed": f_cnt,
        })

    # 6. Danh sách 8 hoạt động mới nhất
    recent_stmt = (
        select(ExecutionLog)
        .options(selectinload(ExecutionLog.account))
        .order_by(desc(ExecutionLog.created_at))
        .limit(8)
    )
    recent_res = await db.execute(recent_stmt)
    recent_logs = []
    for log in recent_res.scalars().all():
        recent_logs.append({
            "id": log.id,
            "account_name": log.account.name if log.account else f"Account #{log.account_id}",
            "task_type": log.task_type,
            "endpoint": log.endpoint,
            "status_code": log.status_code,
            "is_success": log.is_success,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    next_run = (await db.execute(select(func.min(TaskConfig.next_run_at)))).scalar()
    return {
        "total_accounts": total_accounts,
        "active_accounts": active_accounts,
        "total_calls": total_calls,
        "success_calls": success_calls,
        "failed_calls": failed_calls,
        "success_rate": success_rate,
        "calls_last_24h": calls_last_24h,
        "type_breakdown": type_breakdown,
        "daily_stats": daily_stats,
        "recent_logs": recent_logs,
        "scheduler_running": scheduler_service.is_running,
        "next_run_at": next_run.isoformat() if next_run else None,
    }


@router.delete("/clear")
async def clear_logs(
    days: int = Query(30, ge=1, description="Delete logs older than this many days"),
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    """Xóa các bản ghi log cũ trong Database."""
    threshold = datetime.now(timezone.utc) - timedelta(days=days)
    del_stmt = select(ExecutionLog).where(ExecutionLog.created_at < threshold)
    res = await db.execute(del_stmt)
    logs_to_del = res.scalars().all()
    count = len(logs_to_del)

    for l in logs_to_del:
        await db.delete(l)
    await db.commit()

    return {"success": True, "message": f"Deleted {count} log entries older than {days} days."}
