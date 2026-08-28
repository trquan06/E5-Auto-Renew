"""
Test suite cho GraphService và TaskExecutor với Mock HTTP responses.
"""
import pytest
from unittest.mock import patch, AsyncMock
from httpx import Response

from app.services.graph_service import GraphService
from app.services.task_executor import TaskExecutor
from app.database import AsyncSessionLocal, init_db
from app.models.account import Account
from app.models.task_config import TaskConfig
from app.crypto import encrypt
from app.config import settings


@pytest.mark.asyncio
async def test_graph_service_mock_calls():
    """Kiểm tra các phương thức của GraphService hoạt động đúng khi mock HTTP responses."""
    graph = GraphService("mock_access_token_123")

    mock_resp = Response(
        status_code=200,
        headers={"content-type": "application/json"},
        json={"value": [{"id": "msg_1", "subject": "Test Message", "isRead": True}]},
    )

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_resp

        # 1. Mail
        res_mail = await graph.get_messages()
        assert res_mail["is_success"] is True
        assert res_mail["status_code"] == 200

        # 2. Calendar
        res_cal = await graph.get_events()
        assert res_cal["is_success"] is True

        # 3. To-Do
        res_todo = await graph.get_todo_lists()
        assert res_todo["is_success"] is True

        # 4. Profile
        res_prof = await graph.get_user_profile()
        assert res_prof["is_success"] is True


@pytest.mark.asyncio
async def test_task_executor_full_mock_run():
    """Kiểm tra TaskExecutor thực thi trọn vẹn chu kỳ tác vụ với mock data."""
    await init_db()

    async with AsyncSessionLocal() as session:
        # Tạo test account
        acc = Account(
            name="Mock Test Account",
            client_id="mock-client-id",
            tenant_id="common",
            access_token_encrypted=encrypt("valid_mock_token", settings.AES_KEY),
            auth_mode="delegated",
            status="active",
        )
        session.add(acc)
        await session.flush()
        
        cfg = TaskConfig(account_id=acc.id, enable_mail=True, enable_calendar=False, enable_todo=False, enable_teams=False, enable_onedrive=False, enable_onenote=False, enable_profile=True)
        session.add(cfg)
        await session.commit()
        acc_id = acc.id

    mock_resp = Response(
        status_code=200,
        headers={"content-type": "application/json"},
        json={"value": [], "displayName": "Mock User"},
    )

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_req, \
         patch("app.services.auth_service.AuthService.get_valid_access_token", new_callable=AsyncMock) as mock_token, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        
        mock_req.return_value = mock_resp
        mock_token.return_value = "valid_mock_token"

        result = await TaskExecutor.execute_account_tasks(acc_id, is_manual=True)
        assert result["success"] is True
        assert result["total_calls"] > 0
