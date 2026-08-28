"""Execute configured Graph development/test workflows with scheduling variance."""
import asyncio
import random
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.account import Account
from app.models.task_config import TaskConfig
from app.models.execution_log import ExecutionLog
from app.services.auth_service import AuthService
from app.services.graph_service import GraphService
from app.services.notifier_service import NotifierService


class TaskExecutor:
    """Điều phối và chạy chuỗi hành động Graph API cho một tài khoản."""

    @staticmethod
    async def execute_account_tasks(account_id: int, is_manual: bool = False) -> Dict[str, Any]:
        """
        Thực thi toàn bộ chu kỳ tác vụ cho tài khoản được chỉ định.
        """
        async with AsyncSessionLocal() as session:
            # 1. Lấy thông tin tài khoản và cấu hình
            stmt = (
                select(Account)
                .where(Account.id == account_id)
                .options(selectinload(Account.task_config))
            )
            result = await session.execute(stmt)
            account = result.scalar_one_or_none()

            if not account:
                return {"success": False, "error": f"Account ID {account_id} was not found."}

            if account.status == "disabled" and not is_manual:
                return {"success": False, "error": "The account is disabled."}

            config: TaskConfig = account.task_config
            if not config:
                # Tạo config mặc định nếu chưa có
                config = TaskConfig(account_id=account.id)
                session.add(config)
                await session.commit()
                await session.refresh(config)

            # 2. Lấy Access Token hợp lệ
            start_all = time.perf_counter()
            try:
                access_token = await AuthService.get_valid_access_token(account, session)
            except Exception as exc:
                err_msg = f"Authentication or token refresh failed: {exc}"
                account.last_status = "failed"
                account.last_error = err_msg
                account.last_run_at = datetime.now(timezone.utc)
                
                # Ghi log lỗi vào execution_logs
                log_entry = ExecutionLog(
                    account_id=account.id,
                    task_type="auth",
                    endpoint="/oauth2/v2.0/token",
                    method="POST",
                    status_code=401,
                    duration_ms=int((time.perf_counter() - start_all) * 1000),
                    is_success=False,
                    error_message=err_msg,
                )
                session.add(log_entry)
                await session.commit()

                # Gửi thông báo lỗi
                await NotifierService.notify_execution_summary(
                    account_name=account.name,
                    total_tasks=1,
                    success_tasks=0,
                    failed_tasks=1,
                    skipped_tasks=0,
                    duration_ms=int((time.perf_counter() - start_all) * 1000),
                    error_msg=err_msg,
                    db_session=session,
                )
                return {"success": False, "error": err_msg}

            # 3. Khởi tạo Graph Service
            graph = GraphService(access_token)

            # 4. Chuẩn bị danh sách các hành động có thể chạy
            available_tasks = []

            # ── Module Profile ──────────────────────────────────────────────
            if config.enable_profile:
                async def run_profile():
                    logs = []
                    # GET Profile & Drive Quota
                    res1 = await graph.get_user_profile()
                    logs.append(("profile", res1))
                    res2 = await graph.get_drive_quota()
                    logs.append(("profile", res2))
                    return logs
                available_tasks.append(("Profile & Quota", run_profile, False))

            # ── Module Mail ─────────────────────────────────────────────────
            if config.enable_mail:
                async def run_mail():
                    logs = []
                    res_get = await graph.get_messages(top=10)
                    logs.append(("mail", res_get))
                    # Tạo email nháp
                    res_draft = await graph.create_draft_message()
                    logs.append(("mail", res_draft))
                    return logs
                available_tasks.append(("Mail / Outlook", run_mail, False))

            # ── Module Calendar ─────────────────────────────────────────────
            if config.enable_calendar:
                async def run_calendar():
                    logs = []
                    res_events = await graph.get_events(top=10)
                    logs.append(("calendar", res_events))
                    res_create = await graph.create_calendar_event()
                    logs.append(("calendar", res_create))
                    # Dọn dẹp sự kiện cũ
                    cleanup_logs = await graph.cleanup_old_calendar_events()
                    for cl in cleanup_logs:
                        logs.append(("calendar", cl))
                    return logs
                available_tasks.append(("Calendar", run_calendar, True))

            # ── Module To-Do ────────────────────────────────────────────────
            if config.enable_todo:
                async def run_todo():
                    logs = []
                    lists_res = await graph.get_todo_lists()
                    logs.append(("todo", lists_res))
                    if lists_res["is_success"] and lists_res.get("data"):
                        lists = lists_res["data"].get("value", [])
                        if lists:
                            list_id = lists[0]["id"]
                            task_title = f"Sprint item - {random.choice(['Code review', 'Database sync', 'Doc update'])} #{random.randint(100, 999)}"
                            task_res = await graph.create_todo_task(list_id, task_title)
                            logs.append(("todo", task_res))
                            if task_res["is_success"] and task_res.get("data"):
                                task_id = task_res["data"]["id"]
                                done_res = await graph.complete_todo_task(list_id, task_id)
                                logs.append(("todo", done_res))
                    return logs
                available_tasks.append(("Microsoft To-Do", run_todo, True))

            # ── Module Teams & Groups ───────────────────────────────────────
            if config.enable_teams:
                async def run_teams():
                    logs = []
                    t_res = await graph.get_joined_teams()
                    logs.append(("teams", t_res))
                    g_res = await graph.get_groups(top=10)
                    logs.append(("teams", g_res))
                    if t_res["is_success"] and t_res.get("data"):
                        teams = t_res["data"].get("value", [])
                        if teams:
                            ch_res = await graph.get_team_channels(teams[0]["id"])
                            logs.append(("teams", ch_res))
                    return logs
                available_tasks.append(("Teams & Groups", run_teams, True))

            # ── Module OneDrive ─────────────────────────────────────────────
            if config.enable_onedrive:
                async def run_onedrive():
                    logs = []
                    root_res = await graph.get_drive_root_children()
                    logs.append(("onedrive", root_res))
                    # Upload random test file
                    up_res = await graph.upload_random_onedrive_file()
                    logs.append(("onedrive", up_res))
                    # Cleanup retention policy
                    cleanup_logs = await graph.cleanup_old_onedrive_files(max_files=10)
                    for cl in cleanup_logs:
                        logs.append(("onedrive", cl))
                    return logs
                available_tasks.append(("OneDrive File Ops", run_onedrive, False))

            # ── Module OneNote ──────────────────────────────────────────────
            if config.enable_onenote:
                async def run_onenote():
                    logs = []
                    note_res = await graph.get_onenote_notebooks()
                    logs.append(("onenote", note_res))
                    return logs
                available_tasks.append(("OneNote Notebooks", run_onenote, True))

            # 5. Scheduling variance: shuffled modules and optional sampling.
            random.shuffle(available_tasks)

            total_calls = 0
            success_calls = 0
            failed_calls = 0
            skipped_tasks_count = 0
            last_error_detail = None

            for task_name, task_func, is_optional in available_tasks:
                # Kiểm tra xác suất ngẫu nhiên bỏ qua tác vụ không bắt buộc
                if is_optional and not is_manual and len(available_tasks) > 3:
                    if random.random() < config.skip_ratio:
                        skipped_tasks_count += 1
                        continue

                # Thực thi tác vụ
                try:
                    action_results = await task_func()
                    for task_type, item in action_results:
                        total_calls += 1
                        if item["is_success"]:
                            success_calls += 1
                        else:
                            failed_calls += 1
                            if not last_error_detail:
                                last_error_detail = item.get("error_message") or f"HTTP status {item.get('status_code')}"

                        # Lưu vào ExecutionLog
                        log_obj = ExecutionLog(
                            account_id=account.id,
                            task_type=task_type,
                            endpoint=item.get("endpoint"),
                            method=item.get("method", "GET"),
                            status_code=item.get("status_code"),
                            duration_ms=item.get("duration_ms", 0),
                            is_success=item.get("is_success", False),
                            response_snippet=item.get("response_snippet"),
                            error_message=item.get("error_message"),
                        )
                        session.add(log_obj)

                    # Trì hoãn ngẫu nhiên 2 - 5 giây giữa các nhóm tác vụ để mô phỏng người dùng
                    await asyncio.sleep(random.uniform(1.5, 4.0))

                except Exception as exc:
                    failed_calls += 1
                    last_error_detail = str(exc)
                    log_obj = ExecutionLog(
                        account_id=account.id,
                        task_type="error",
                        endpoint="/error",
                        method="GET",
                        status_code=500,
                        duration_ms=0,
                        is_success=False,
                        error_message=f"Unhandled error while running {task_name}: {exc}",
                    )
                    session.add(log_obj)

            total_duration_ms = int((time.perf_counter() - start_all) * 1000)

            # 6. Cập nhật trạng thái Account
            account.last_run_at = datetime.now(timezone.utc)
            if failed_calls == 0 and success_calls > 0:
                account.last_status = "success"
                account.last_error = None
            elif success_calls > 0 and failed_calls > 0:
                account.last_status = "partial"
                account.last_error = last_error_detail
            else:
                account.last_status = "failed"
                account.last_error = last_error_detail or "No Graph API call was executed."

            # Lưu toàn bộ logs và cập nhật DB
            await session.commit()

            # 7. Gửi thông báo tóm tắt
            await NotifierService.notify_execution_summary(
                account_name=account.name,
                total_tasks=total_calls,
                success_tasks=success_calls,
                failed_tasks=failed_calls,
                skipped_tasks=skipped_tasks_count,
                duration_ms=total_duration_ms,
                error_msg=last_error_detail if failed_calls > 0 else None,
                db_session=session,
            )

            return {
                "success": failed_calls == 0,
                "account_id": account.id,
                "account_name": account.name,
                "total_calls": total_calls,
                "success_calls": success_calls,
                "failed_calls": failed_calls,
                "skipped_tasks": skipped_tasks_count,
                "duration_ms": total_duration_ms,
            }
