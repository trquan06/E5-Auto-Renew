"""Delegated Microsoft 365 account CRUD and OAuth endpoints."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_admin
from app.config import settings
from app.crypto import encrypt
from app.database import get_db
from app.models.account import Account
from app.models.task_config import TaskConfig
from app.security import error_detail, public_origin
from app.services.auth_service import AuthService
from app.services.oauth_state import oauth_state_manager
from app.services.scheduler_service import scheduler_service

router = APIRouter(prefix="/api/accounts", tags=["Accounts"])
TENANT_PATTERN = r"^[A-Za-z0-9.-]{1,100}$"


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    client_id: str = Field(min_length=8, max_length=100)
    client_secret: Optional[str] = Field(default=None, max_length=512)
    tenant_id: str = Field(default="common", pattern=TENANT_PATTERN)
    refresh_token: Optional[str] = Field(default=None, max_length=8192)


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    client_id: Optional[str] = Field(default=None, min_length=8, max_length=100)
    client_secret: Optional[str] = Field(default=None, max_length=512)
    tenant_id: Optional[str] = Field(default=None, pattern=TENANT_PATTERN)
    refresh_token: Optional[str] = Field(default=None, max_length=8192)
    status: Optional[Literal["active", "expired", "error", "disabled"]] = None


class OAuthCallbackRequest(BaseModel):
    code: str = Field(min_length=4, max_length=4096)
    state: str = Field(min_length=16, max_length=4096)
    client_secret: Optional[str] = Field(default=None, max_length=512)


def _config_payload(config: TaskConfig | None) -> dict | None:
    if not config:
        return None
    return {
        "id": config.id,
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


def _account_payload(account: Account) -> dict:
    return {
        "id": account.id,
        "name": account.name,
        "client_id": account.client_id,
        "tenant_id": account.tenant_id,
        "auth_mode": "delegated",
        "email": account.email,
        "display_name": account.display_name,
        "status": account.status,
        "has_secret": bool(account.client_secret_encrypted),
        "has_refresh_token": bool(account.refresh_token_encrypted),
        "token_expires_at": account.token_expires_at.isoformat() if account.token_expires_at else None,
        "last_run_at": account.last_run_at.isoformat() if account.last_run_at else None,
        "last_status": account.last_status,
        "last_error": account.last_error,
        "created_at": account.created_at.isoformat() if account.created_at else None,
        "task_config": _config_payload(account.task_config),
    }


def _script_json(value: object) -> str:
    return (
        json.dumps(value, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _callback_html(payload: dict, *, status_code: int = 200) -> HTMLResponse:
    nonce = secrets.token_urlsafe(18)
    data = _script_json(payload)
    translations = _script_json(
        {
            "en": {
                "processing": "Completing Microsoft sign-in…",
                "success": "Microsoft sign-in completed",
                "successDetail": "The authorization code was sent securely to the WebUI.",
                "error": "Microsoft sign-in failed",
                "noOpener": "Return to the WebUI and start the connection again.",
            },
            "vi": {
                "processing": "Đang hoàn tất đăng nhập Microsoft…",
                "success": "Đăng nhập Microsoft hoàn tất",
                "successDetail": "Mã ủy quyền đã được gửi an toàn về WebUI.",
                "error": "Đăng nhập Microsoft thất bại",
                "noOpener": "Quay lại WebUI và bắt đầu kết nối lại.",
            },
            "zh-CN": {
                "processing": "正在完成 Microsoft 登录…",
                "success": "Microsoft 登录已完成",
                "successDetail": "授权代码已安全发送到 WebUI。",
                "error": "Microsoft 登录失败",
                "noOpener": "请返回 WebUI 并重新开始连接。",
            },
        }
    )
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MS365 Auto Renew · OAuth</title>
<style nonce="{nonce}">body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#07111f;color:#e8eef8;font:16px system-ui,sans-serif}}main{{width:min(28rem,calc(100% - 2rem));padding:2rem;border:1px solid #29415e;border-radius:1rem;background:#101d2e;text-align:center;box-shadow:0 1rem 3rem #0007}}.mark{{font-size:2.5rem}}h1{{font-size:1.25rem}}p{{color:#a9bad0;line-height:1.6}}</style></head>
<body><main role="status" aria-live="polite"><div class="mark" id="mark">◌</div><h1 id="title"></h1><p id="detail"></p></main>
<script nonce="{nonce}">(() => {{
const payload={data};const catalogs={translations};
const locale=localStorage.getItem('ms365.locale')||'en';const messages=catalogs[locale]||catalogs.en;
const title=document.getElementById('title');const detail=document.getElementById('detail');const mark=document.getElementById('mark');
title.textContent=messages.processing;history.replaceState({{}},document.title,location.pathname);
if(payload.type==='code'&&window.opener&&!window.opener.closed){{
  window.opener.postMessage({{type:'ms365-oauth-callback',code:payload.code,state:payload.state}},payload.targetOrigin);
  payload.code='';mark.textContent='✓';title.textContent=messages.success;detail.textContent=messages.successDetail;setTimeout(()=>window.close(),900);
}}else if(payload.type==='error'){{
  if(window.opener&&!window.opener.closed&&payload.targetOrigin)window.opener.postMessage({{type:'ms365-oauth-callback',error:payload.message}},payload.targetOrigin);
  mark.textContent='!';title.textContent=messages.error;detail.textContent=payload.message;
}}else{{mark.textContent='!';title.textContent=messages.error;detail.textContent=messages.noOpener;}}
}})();</script></body></html>"""
    return HTMLResponse(
        content=html,
        status_code=status_code,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": f"default-src 'none'; style-src 'nonce-{nonce}'; script-src 'nonce-{nonce}'",
            "Referrer-Policy": "no-referrer",
        },
    )


# OAuth routes are declared before /{account_id} so they cannot be shadowed.
@router.get("/oauth/authorize-url")
async def get_oauth_authorize_url(
    request: Request,
    client_id: str = Query(min_length=8, max_length=100),
    tenant_id: str = Query(default="common", pattern=TENANT_PATTERN),
    account_name: Optional[str] = Query(default=None, max_length=100),
    redirect_uri: Optional[str] = Query(default=None, description="Deprecated compatibility check; cannot override the backend URI."),
    admin: str = Depends(get_current_admin),
):
    origin = public_origin(request)
    expected_redirect_uri = f"{origin}/api/accounts/oauth/callback"
    if redirect_uri and redirect_uri.rstrip("/") != expected_redirect_uri:
        raise HTTPException(
            status_code=400,
            detail=error_detail("redirect_uri_not_allowed", "The redirect URI must match the WebUI callback URI."),
        )
    state_token = oauth_state_manager.create(
        client_id=client_id,
        tenant_id=tenant_id,
        origin=origin,
        account_name=account_name,
    )
    return {
        "auth_url": AuthService.generate_auth_url(client_id, expected_redirect_uri, tenant_id, state_token),
        "redirect_uri": expected_redirect_uri,
    }


@router.get("/oauth/callback", response_class=HTMLResponse)
async def oauth_callback_page(
    code: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    state: Optional[str] = None,
):
    if not state:
        return _callback_html({"type": "invalid"}, status_code=400)
    try:
        state_payload = oauth_state_manager.verify(state)
    except ValueError:
        return _callback_html({"type": "invalid"}, status_code=400)
    target_origin = state_payload["origin"]
    if code:
        return _callback_html({"type": "code", "code": code, "state": state, "targetOrigin": target_origin})
    message = error_description or error or "Microsoft did not return an authorization code."
    return _callback_html({"type": "error", "message": message, "targetOrigin": target_origin})


@router.post("/oauth/callback")
async def handle_oauth_callback(
    payload: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    try:
        state_payload = oauth_state_manager.verify(payload.state)
    except ValueError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=400,
            detail=error_detail(code, "The OAuth state is invalid, expired, or has already been used."),
        ) from exc

    # Consume before exchanging the authorization code so concurrent replays
    # cannot race two token requests with the same signed state.
    oauth_state_manager.consume(state_payload)
    redirect_uri = f"{state_payload['origin']}/api/accounts/oauth/callback"
    try:
        token_result = await AuthService.exchange_code_for_tokens(
            client_id=state_payload["client_id"],
            client_secret=payload.client_secret,
            code=payload.code,
            redirect_uri=redirect_uri,
            tenant_id=state_payload["tenant_id"],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=error_detail("token_exchange_failed", f"Microsoft token exchange failed: {exc}"),
        ) from exc

    access_token = token_result.get("access_token")
    refresh_token = token_result.get("refresh_token")
    if not access_token or not refresh_token:
        raise HTTPException(
            status_code=400,
            detail=error_detail(
                "refresh_token_missing",
                "Microsoft did not return the required delegated refresh token. Confirm that offline_access is granted.",
            ),
        )

    profile = await AuthService.fetch_user_profile(access_token)
    email = profile.get("userPrincipalName") or profile.get("mail")
    display_name = profile.get("displayName") or email or state_payload.get("account_name") or "Microsoft 365 account"
    account_name = state_payload.get("account_name") or display_name

    existing = None
    if email:
        existing = (await db.execute(select(Account).where(Account.email == email))).scalar_one_or_none()
    if existing:
        account = existing
        account.name = account_name
        account.client_id = state_payload["client_id"]
        account.tenant_id = state_payload["tenant_id"]
        account.email = email
        account.display_name = display_name
        account.status = "active"
        account.last_error = None
        account.auth_mode = "delegated"
    else:
        account = Account(
            name=account_name,
            client_id=state_payload["client_id"],
            tenant_id=state_payload["tenant_id"],
            email=email,
            display_name=display_name,
            auth_mode="delegated",
            status="active",
        )
        db.add(account)
        await db.flush()
        db.add(TaskConfig(account_id=account.id))

    if payload.client_secret:
        account.client_secret_encrypted = encrypt(payload.client_secret, settings.AES_KEY)
    account.refresh_token_encrypted = encrypt(refresh_token, settings.AES_KEY)
    account.access_token_encrypted = encrypt(access_token, settings.AES_KEY)
    account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(60, token_result.get("expires_in", 3600) - 120))
    await db.commit()
    await scheduler_service.schedule_account(account.id)
    return {
        "success": True,
        "message": "Microsoft account connected successfully.",
        "account": {"id": account.id, "name": account.name, "email": account.email, "display_name": account.display_name},
    }


@router.get("")
async def list_accounts(db: AsyncSession = Depends(get_db), admin: str = Depends(get_current_admin)):
    result = await db.execute(select(Account).options(selectinload(Account.task_config)).order_by(Account.id.asc()))
    return [_account_payload(account) for account in result.scalars().all()]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_account(payload: AccountCreate, db: AsyncSession = Depends(get_db), admin: str = Depends(get_current_admin)):
    account = Account(
        name=payload.name,
        client_id=payload.client_id,
        tenant_id=payload.tenant_id,
        auth_mode="delegated",
        status="active",
    )
    if payload.client_secret:
        account.client_secret_encrypted = encrypt(payload.client_secret, settings.AES_KEY)
    if payload.refresh_token:
        account.refresh_token_encrypted = encrypt(payload.refresh_token, settings.AES_KEY)
    db.add(account)
    await db.flush()
    db.add(TaskConfig(account_id=account.id))
    await db.commit()
    account = (
        await db.execute(select(Account).where(Account.id == account.id).options(selectinload(Account.task_config)))
    ).scalar_one()
    await scheduler_service.schedule_account(account.id)
    return {"success": True, "message": "Account created.", "account": _account_payload(account)}


@router.get("/{account_id}")
async def get_account(account_id: int, db: AsyncSession = Depends(get_db), admin: str = Depends(get_current_admin)):
    result = await db.execute(
        select(Account).where(Account.id == account_id).options(selectinload(Account.task_config))
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail=error_detail("account_not_found", "Account not found."))
    return _account_payload(account)


@router.put("/{account_id}")
async def update_account(
    account_id: int,
    payload: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    account = (await db.execute(select(Account).where(Account.id == account_id))).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail=error_detail("account_not_found", "Account not found."))
    changes = payload.model_dump(exclude_unset=True)
    client_secret = changes.pop("client_secret", None)
    refresh_token = changes.pop("refresh_token", None)
    for field, value in changes.items():
        setattr(account, field, value)
    account.auth_mode = "delegated"
    if client_secret is not None:
        account.client_secret_encrypted = encrypt(client_secret, settings.AES_KEY) if client_secret else None
    if refresh_token is not None:
        account.refresh_token_encrypted = encrypt(refresh_token, settings.AES_KEY) if refresh_token else None
    await db.commit()
    await scheduler_service.schedule_account(account.id)
    return {"success": True, "message": "Account updated."}


@router.delete("/{account_id}")
async def delete_account(account_id: int, db: AsyncSession = Depends(get_db), admin: str = Depends(get_current_admin)):
    account = (await db.execute(select(Account).where(Account.id == account_id))).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail=error_detail("account_not_found", "Account not found."))
    scheduler_service.remove_job(account_id)
    await db.delete(account)
    await db.commit()
    return {"success": True, "message": "Account deleted."}


@router.post("/{account_id}/toggle")
async def toggle_account_status(account_id: int, db: AsyncSession = Depends(get_db), admin: str = Depends(get_current_admin)):
    account = (await db.execute(select(Account).where(Account.id == account_id))).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail=error_detail("account_not_found", "Account not found."))
    account.status = "active" if account.status == "disabled" else "disabled"
    await db.commit()
    if account.status == "active":
        await scheduler_service.schedule_account(account.id)
    else:
        scheduler_service.remove_job(account.id)
    return {"success": True, "status": account.status}


@router.post("/{account_id}/test")
async def test_account_connection(account_id: int, db: AsyncSession = Depends(get_db), admin: str = Depends(get_current_admin)):
    account = (await db.execute(select(Account).where(Account.id == account_id))).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail=error_detail("account_not_found", "Account not found."))
    try:
        access_token = await AuthService.get_valid_access_token(account, db)
        profile = await AuthService.fetch_user_profile(access_token)
        if not profile:
            raise ValueError("Microsoft Graph did not return a user profile.")
        account.email = profile.get("userPrincipalName") or profile.get("mail") or account.email
        account.display_name = profile.get("displayName") or account.display_name
        account.status = "active"
        account.last_error = None
        await db.commit()
        return {"success": True, "message": "Microsoft Graph connection succeeded.", "profile": profile}
    except Exception as exc:
        account.status = "error"
        account.last_error = str(exc)
        await db.commit()
        raise HTTPException(status_code=400, detail=error_detail("graph_connection_failed", f"Connection failed: {exc}")) from exc
