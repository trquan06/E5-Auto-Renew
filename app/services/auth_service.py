"""Delegated Microsoft OAuth and token refresh service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import quote, urlencode

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crypto import decrypt, encrypt
from app.models.account import Account


class AuthService:
    @staticmethod
    def generate_auth_url(
        client_id: str,
        redirect_uri: str,
        tenant_id: str = "common",
        state: Optional[str] = None,
    ) -> str:
        endpoint = f"{settings.MS_AUTHORITY}/{quote(tenant_id, safe='.-')}/oauth2/v2.0/authorize"
        params = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "response_mode": "query",
            "scope": " ".join(settings.MS_SCOPES),
            "prompt": "select_account",
        }
        if state:
            params["state"] = state
        return f"{endpoint}?{urlencode(params)}"

    @staticmethod
    async def exchange_code_for_tokens(
        client_id: str,
        client_secret: Optional[str],
        code: str,
        redirect_uri: str,
        tenant_id: str = "common",
    ) -> dict[str, Any]:
        token_endpoint = f"{settings.MS_AUTHORITY}/{quote(tenant_id, safe='.-')}/oauth2/v2.0/token"
        data = {
            "client_id": client_id,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "scope": " ".join(settings.MS_SCOPES),
        }
        if client_secret:
            data["client_secret"] = client_secret
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(token_endpoint, data=data)
        if response.status_code != 200:
            try:
                error_description = response.json().get("error_description", response.text)
            except ValueError:
                error_description = response.text
            raise ValueError(f"OAuth token exchange returned HTTP {response.status_code}: {error_description[:500]}")
        return response.json()

    @staticmethod
    async def refresh_access_token(account: Account, db_session: AsyncSession) -> str:
        if account.auth_mode != "delegated":
            raise ValueError("Only delegated OAuth accounts are supported in v2.0.")
        if not account.refresh_token_encrypted:
            raise ValueError(f"Account '{account.name}' does not have a delegated refresh token.")

        refresh_token = decrypt(account.refresh_token_encrypted, settings.AES_KEY)
        client_secret = (
            decrypt(account.client_secret_encrypted, settings.AES_KEY)
            if account.client_secret_encrypted
            else None
        )
        token_endpoint = f"{settings.MS_AUTHORITY}/{quote(account.tenant_id, safe='.-')}/oauth2/v2.0/token"
        data = {
            "client_id": account.client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": " ".join(settings.MS_SCOPES),
        }
        if client_secret:
            data["client_secret"] = client_secret

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(token_endpoint, data=data)
        if response.status_code != 200:
            account.status = "expired"
            account.last_status = "failed"
            account.last_error = f"Token refresh returned HTTP {response.status_code}: {response.text[:200]}"
            await db_session.commit()
            raise ValueError(f"Unable to refresh the token for '{account.name}': {account.last_error}")

        token_data = response.json()
        access_token = token_data["access_token"]
        account.access_token_encrypted = encrypt(access_token, settings.AES_KEY)
        if token_data.get("refresh_token"):
            account.refresh_token_encrypted = encrypt(token_data["refresh_token"], settings.AES_KEY)
        account.token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=max(60, token_data.get("expires_in", 3600) - 120)
        )
        account.status = "active"
        account.last_error = None
        await db_session.commit()
        return access_token

    @staticmethod
    async def get_valid_access_token(account: Account, db_session: AsyncSession) -> str:
        if account.auth_mode != "delegated":
            raise ValueError("Only delegated OAuth accounts are supported in v2.0.")
        now = datetime.now(timezone.utc)
        if account.token_expires_at and account.access_token_encrypted:
            expires_at = account.token_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at > now:
                return decrypt(account.access_token_encrypted, settings.AES_KEY)
        return await AuthService.refresh_access_token(account, db_session)

    @staticmethod
    async def fetch_user_profile(access_token: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{settings.MS_GRAPH_BASE}/v1.0/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        return response.json() if response.status_code == 200 else {}
