"""First-run setup endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.security import RateLimit, client_identity, error_detail, rate_limiter
from app.services.setup_service import setup_manager

router = APIRouter(prefix="/api/setup", tags=["Setup"])


class SetupInitializeRequest(BaseModel):
    setup_code: str = Field(min_length=8, max_length=32)
    password: str = Field(min_length=12, max_length=256)


@router.get("/status")
async def setup_status():
    await setup_manager.ensure_prepared()
    return {"is_initialized": bool(setup_manager.initialized)}


@router.post("/initialize")
async def initialize_setup(payload: SetupInitializeRequest, request: Request, db: AsyncSession = Depends(get_db)):
    identity = client_identity(request)
    await rate_limiter.check(
        "setup",
        identity,
        RateLimit(settings.SETUP_RATE_LIMIT, settings.SETUP_RATE_WINDOW_SECONDS),
    )
    try:
        await setup_manager.initialize(db, payload.setup_code, payload.password)
    except ValueError as exc:
        code = str(exc)
        messages = {
            "already_initialized": "Setup has already been completed.",
            "setup_code_used": "The setup code has already been used.",
            "setup_code_expired": "The setup code has expired. Restart the application to generate a new code.",
            "setup_code_invalid": "The setup code is incorrect.",
        }
        raise HTTPException(status_code=400, detail=error_detail(code, messages.get(code, "Setup failed."))) from exc
    await rate_limiter.clear("setup", identity)
    return {"success": True, "message": "Setup completed successfully."}
