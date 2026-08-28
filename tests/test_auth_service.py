"""
Test suite cho AuthService (auth_service.py).
"""
import pytest
from app.config import settings
from app.services.auth_service import AuthService


def test_generate_auth_url():
    """Kiểm tra việc tạo OAuth2 Authorization URL chính xác."""
    client_id = "test-client-id-12345"
    redirect_uri = "http://localhost:8080/api/accounts/oauth/callback"
    tenant_id = "common"
    state = "random_state_xyz"

    url = AuthService.generate_auth_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        tenant_id=tenant_id,
        state=state,
    )

    assert "https://login.microsoftonline.com/common/oauth2/v2.0/authorize" in url
    assert f"client_id={client_id}" in url
    assert "response_type=code" in url
    assert "prompt=select_account" in url
    assert "offline_access" in url
    assert f"state={state}" in url


@pytest.mark.asyncio
async def test_fetch_user_profile_invalid_token():
    """Kiểm tra fetch_user_profile với token không hợp lệ trả về dict rỗng."""
    profile = await AuthService.fetch_user_profile("invalid_token_sample")
    assert profile == {}
