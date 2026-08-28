"""Password authentication for the single administrator WebUI."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt.exceptions import PyJWTError
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.system_setting import SystemSetting
from app.security import RateLimit, client_identity, error_detail, rate_limiter
from app.services.setup_service import pwd_context

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
security = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


async def verify_password(plain_password: str, db: AsyncSession) -> bool:
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == "webui_password_hash")
    )
    password_setting = result.scalar_one_or_none()
    if not password_setting or not password_setting.value:
        return False
    try:
        return pwd_context.verify(plain_password, password_setting.value)
    except (ValueError, TypeError):
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    payload.update(
        {
            "exp": datetime.now(timezone.utc) + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)),
            "iat": datetime.now(timezone.utc),
            "sub": "admin",
            "type": "access",
        }
    )
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


async def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_detail("authentication_required", "Sign in to continue."),
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("sub") != "admin" or payload.get("type") != "access":
            raise PyJWTError("Unexpected token claims")
        return "admin"
    except PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_detail("session_expired", "The session is invalid or has expired."),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    identity = client_identity(request)
    await rate_limiter.check(
        "login",
        identity,
        RateLimit(settings.LOGIN_RATE_LIMIT, settings.LOGIN_RATE_WINDOW_SECONDS),
    )
    if not await verify_password(payload.password, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_detail("invalid_password", "The password is incorrect."),
        )
    await rate_limiter.clear("login", identity)
    access_token = create_access_token({"sub": "admin"})
    return LoginResponse(access_token=access_token, expires_in=ACCESS_TOKEN_EXPIRE_DAYS * 86400)


@router.get("/status")
async def auth_status(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    is_authenticated = False
    if credentials:
        try:
            payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[ALGORITHM])
            is_authenticated = payload.get("sub") == "admin" and payload.get("type") == "access"
        except PyJWTError:
            pass
    return {
        "auth_required": True,
        "is_authenticated": is_authenticated,
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
    }


@router.post("/logout")
async def logout():
    return {"success": True, "message": "Signed out successfully."}
