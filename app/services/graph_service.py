"""Microsoft Graph operations used for development and integration testing."""
import random
import string
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Tuple
import httpx

from app.config import settings


# Sample data for exercising delegated development/test workflows.
SAMPLE_EMAIL_TOPICS = [
    ("Weekly Team Sync Agenda", "Hi team,\nPlease find the agenda for our upcoming weekly sync attached. Let me know if you have items to add.\n\nBest regards,"),
    ("Architecture Review Follow-up", "Hello all,\nFollowing up on our architecture discussion, here are the action items and key milestones for Q3.\n\nThanks,"),
    ("Sprint 24 Retrospective Summary", "Team,\nGreat job on delivering the latest release. Below is the summary of feedback and improvement points.\n\nCheers,"),
    ("Cloud Infrastructure Migration Status", "Hi folks,\nThe database migration phase 1 completed smoothly with zero downtime. Monitoring metrics look healthy.\n\nRegards,"),
    ("API Gateway Security Audit Notes", "Hi team,\nPlease review the recommended CORS and OAuth2 token validation policy updates.\n\nBest,"),
]

SAMPLE_MEETING_TOPICS = [
    "Sprint Planning & Backlog Refinement",
    "Quarterly Roadmap Discussion",
    "DevOps & CI/CD Pipeline Review",
    "Security & Compliance Sync",
    "1:1 Engineering Catch-up",
    "Product Design & UX Walkthrough",
]

SAMPLE_TODO_TASKS = [
    "Review pull request for auth service refactoring",
    "Update deployment runbook in repository wiki",
    "Verify database indexes and query execution plans",
    "Rotate stale API keys and review Azure permissions",
    "Benchmark async HTTP client latency",
    "Organize documentation notes in OneNote",
]


class GraphService:
    """Execute delegated Microsoft Graph requests with an access token."""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = settings.MS_GRAPH_BASE
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        content: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 25.0,
    ) -> Dict[str, Any]:
        """
        Thực hiện HTTP request tới Graph API và đo lường thời gian, kết quả trả về.
        """
        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"
        req_headers = dict(self.headers)
        if headers:
            req_headers.update(headers)

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=req_headers,
                    json=json_data,
                    content=content,
                )
                duration_ms = int((time.perf_counter() - start_time) * 1000)

                is_success = 200 <= response.status_code < 300
                res_snippet = ""
                error_msg = None

                if response.status_code == 204:
                    res_snippet = "204 No Content (success)"
                else:
                    try:
                        res_json = response.json()
                        res_snippet = str(res_json)[:400]
                        if not is_success:
                            error_msg = str(res_json.get("error", {}).get("message", response.text))[:400]
                    except Exception:
                        res_snippet = response.text[:400]
                        if not is_success:
                            error_msg = response.text[:400]

                return {
                    "method": method,
                    "endpoint": path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "is_success": is_success,
                    "response_snippet": res_snippet,
                    "error_message": error_msg,
                    "data": response.json() if is_success and response.headers.get("content-type", "").startswith("application/json") else None,
                }
            except httpx.RequestError as exc:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                return {
                    "method": method,
                    "endpoint": path,
                    "status_code": 0,
                    "duration_ms": duration_ms,
                    "is_success": False,
                    "response_snippet": None,
                    "error_message": f"Network error: {str(exc)}",
                    "data": None,
                }

    # ══════════════════════════════════════════════════════════════════════
    # 1. HỘP THƯ (MAIL / OUTLOOK)
    # ══════════════════════════════════════════════════════════════════════

    async def get_messages(self, top: int = 10) -> Dict[str, Any]:
        """Đọc danh sách email gần nhất."""
        path = f"/v1.0/me/messages?$top={top}&$select=id,subject,receivedDateTime,isRead"
        return await self._request("GET", path)

    async def create_draft_message(self) -> Dict[str, Any]:
        """Tạo một bản nháp email ngẫu nhiên mô phỏng hoạt động công việc."""
        subject, body_text = random.choice(SAMPLE_EMAIL_TOPICS)
        random_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        subject = f"[Dev Test] {subject} - {random_suffix}"

        payload = {
            "subject": subject,
            "importance": "normal",
            "body": {
                "contentType": "Text",
                "content": f"{body_text}\n\nAuto generated at {datetime.now(timezone.utc).isoformat()}",
            },
        }
        return await self._request("POST", "/v1.0/me/messages", json_data=payload)

    async def update_message_flag(self, message_id: str, is_read: bool = True) -> Dict[str, Any]:
        """Đánh dấu trạng thái email."""
        payload = {"isRead": is_read}
        return await self._request("PATCH", f"/v1.0/me/messages/{message_id}", json_data=payload)

    # ══════════════════════════════════════════════════════════════════════
    # 2. LỊCH LÀM VIỆC (CALENDAR / EVENTS)
    # ══════════════════════════════════════════════════════════════════════

    async def get_events(self, top: int = 10) -> Dict[str, Any]:
        """Lấy danh sách sự kiện/cuộc họp trong lịch."""
        path = f"/v1.0/me/events?$top={top}&$select=id,subject,start,end,createdDateTime"
        return await self._request("GET", path)

    async def create_calendar_event(self) -> Dict[str, Any]:
        """Tạo sự kiện hoặc cuộc họp mô phỏng trên lịch."""
        topic = random.choice(SAMPLE_MEETING_TOPICS)
        random_id = "".join(random.choices(string.digits, k=4))
        subject = f"[Sync] {topic} #{random_id}"

        # Đặt lịch cho ngày mai vào 14:00 - 15:00
        start_dt = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
        end_dt = start_dt + timedelta(hours=1)

        payload = {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": f"<p>Auto generated meeting for workflow continuity. Subject: {topic}</p>",
            },
            "start": {
                "dateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC",
            },
            "location": {
                "displayName": "Microsoft Teams Meeting Room",
            },
        }
        return await self._request("POST", "/v1.0/me/events", json_data=payload)

    async def cleanup_old_calendar_events(self) -> List[Dict[str, Any]]:
        """Dọn dẹp các sự kiện auto-renew thử nghiệm đã qua."""
        logs = []
        events_res = await self.get_events(top=25)
        logs.append(events_res)
        if events_res["is_success"] and events_res.get("data"):
            events = events_res["data"].get("value", [])
            for ev in events:
                subj = ev.get("subject", "")
                if "[Sync]" in subj or "[Dev Test]" in subj or "[Renew Activity]" in subj:
                    del_res = await self._request("DELETE", f"/v1.0/me/events/{ev['id']}")
                    logs.append(del_res)
        return logs

    # ══════════════════════════════════════════════════════════════════════
    # 3. TÁC VỤ CÔNG VIỆC (MICROSOFT TO-DO)
    # ══════════════════════════════════════════════════════════════════════

    async def get_todo_lists(self) -> Dict[str, Any]:
        """Lấy danh sách các bảng việc To-Do."""
        return await self._request("GET", "/v1.0/me/todo/lists")

    async def create_todo_task(self, list_id: str, title: str) -> Dict[str, Any]:
        """Tạo một task mới trong bảng To-Do."""
        payload = {
            "title": title,
            "importance": "normal",
            "body": {
                "content": f"Task created at {datetime.now(timezone.utc).isoformat()}",
                "contentType": "text",
            },
        }
        return await self._request("POST", f"/v1.0/me/todo/lists/{list_id}/tasks", json_data=payload)

    async def complete_todo_task(self, list_id: str, task_id: str) -> Dict[str, Any]:
        """Đánh dấu hoàn thành task To-Do."""
        payload = {"status": "completed"}
        return await self._request("PATCH", f"/v1.0/me/todo/lists/{list_id}/tasks/{task_id}", json_data=payload)

    # ══════════════════════════════════════════════════════════════════════
    # 4. ĐỘI NHÓM & KÊNH (TEAMS & GROUPS)
    # ══════════════════════════════════════════════════════════════════════

    async def get_joined_teams(self) -> Dict[str, Any]:
        """Liệt kê danh sách Microsoft Teams mà tài khoản đang tham gia."""
        return await self._request("GET", "/v1.0/me/joinedTeams")

    async def get_groups(self, top: int = 10) -> Dict[str, Any]:
        """Đọc danh sách Microsoft 365 Groups."""
        path = f"/v1.0/groups?$top={top}&$select=id,displayName,description,mailNickname"
        return await self._request("GET", path)

    async def get_team_channels(self, team_id: str) -> Dict[str, Any]:
        """Lấy danh sách các kênh làm việc (channels) trong 1 team."""
        return await self._request("GET", f"/v1.0/teams/{team_id}/channels")

    # ══════════════════════════════════════════════════════════════════════
    # 5. TẬP TIN ONEDRIVE (UPLOAD & AUTO CLEANUP)
    # ══════════════════════════════════════════════════════════════════════

    async def get_drive_root_children(self) -> Dict[str, Any]:
        """Duyệt danh sách tập tin và thư mục ở thư mục gốc OneDrive."""
        return await self._request("GET", "/v1.0/me/drive/root/children?$top=10")

    async def upload_random_onedrive_file(self) -> Dict[str, Any]:
        """
        Upload a generated text fixture into the 'MS365_DevTest_Files' folder.
        Tự động tạo thư mục nếu chưa tồn tại.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        random_hash = "".join(random.choices(string.hexdigits[:16], k=8))
        filename = f"activity_log_{timestamp}_{random_hash}.txt"

        sample_content = (
            f"=== MICROSOFT 365 DEVELOPMENT TEST RECORD ===\n"
            f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n"
            f"Session ID: {random_hash}\n"
            f"Status: Test fixture generated\n"
            f"Payload Metrics: cpu_load=0.12, memory_alloc_mb=42, network_status=stable\n"
            f"Activity note: Delegated Graph workflow verification.\n"
            f"================================================\n"
        ).encode("utf-8")

        path = f"/v1.0/me/drive/root:/MS365_DevTest_Files/{filename}:/content"
        headers = {"Content-Type": "text/plain"}
        return await self._request("PUT", path, content=sample_content, headers=headers)

    async def get_drive_item_content(self, item_id: str) -> Dict[str, Any]:
        """Tải về nội dung của một file OneDrive để kiểm tra tính toàn vẹn."""
        return await self._request("GET", f"/v1.0/me/drive/items/{item_id}/content")

    async def cleanup_old_onedrive_files(self, max_files: int = 10) -> List[Dict[str, Any]]:
        """
        Dọn dẹp các file cũ trong thư mục E5_Renew_AutoFiles để tránh tràn dung lượng.
        Chỉ giữ lại tối đa `max_files` tập tin mới nhất.
        """
        logs = []
        list_res = await self._request("GET", "/v1.0/me/drive/root:/MS365_DevTest_Files:/children?$top=50&$select=id,name,createdDateTime")
        logs.append(list_res)

        if list_res["is_success"] and list_res.get("data"):
            files = list_res["data"].get("value", [])
            if len(files) > max_files:
                # Sắp xếp từ cũ nhất đến mới nhất theo createdDateTime
                sorted_files = sorted(files, key=lambda f: f.get("createdDateTime", ""))
                files_to_delete = sorted_files[: len(files) - max_files]

                for f in files_to_delete:
                    del_res = await self._request("DELETE", f"/v1.0/me/drive/items/{f['id']}")
                    logs.append(del_res)

        return logs

    # ══════════════════════════════════════════════════════════════════════
    # 6. THÔNG TIN TÀI KHOẢN & SỔ GHI CHÉP (PROFILE & ONENOTE)
    # ══════════════════════════════════════════════════════════════════════

    async def get_user_profile(self) -> Dict[str, Any]:
        """Đọc thông tin profile người dùng hiện tại."""
        return await self._request("GET", "/v1.0/me")

    async def get_drive_quota(self) -> Dict[str, Any]:
        """Đọc dung lượng và hạn ngạch lưu trữ OneDrive."""
        return await self._request("GET", "/v1.0/me/drive")

    async def get_onenote_notebooks(self) -> Dict[str, Any]:
        """Đọc danh sách sổ ghi chép OneNote."""
        return await self._request("GET", "/v1.0/me/onenote/notebooks?$top=10")
