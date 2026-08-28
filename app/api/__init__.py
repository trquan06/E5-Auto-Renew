"""
API package initialization.
"""
from app.api.auth import router as auth_router
from app.api.accounts import router as accounts_router
from app.api.tasks import router as tasks_router
from app.api.logs import router as logs_router
from app.api.settings import router as settings_router
from app.api.setup import router as setup_router

__all__ = [
    "auth_router",
    "accounts_router",
    "tasks_router",
    "logs_router",
    "settings_router",
    "setup_router",
]
