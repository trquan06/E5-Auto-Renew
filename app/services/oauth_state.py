"""Signed, expiring, single-use OAuth state tokens."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import ExpiredSignatureError, PyJWTError

from app.config import settings

ALGORITHM = "HS256"
STATE_TTL_MINUTES = 10


class OAuthStateManager:
    def __init__(self) -> None:
        self._consumed: set[str] = set()

    def create(self, *, client_id: str, tenant_id: str, origin: str, account_name: str | None) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "type": "oauth_state",
            "jti": secrets.token_urlsafe(18),
            "client_id": client_id,
            "tenant_id": tenant_id,
            "origin": origin,
            "account_name": account_name or "",
            "iat": now,
            "exp": now + timedelta(minutes=STATE_TTL_MINUTES),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)

    def verify(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        except ExpiredSignatureError as exc:
            raise ValueError("oauth_state_expired") from exc
        except PyJWTError as exc:
            raise ValueError("oauth_state_invalid") from exc
        if payload.get("type") != "oauth_state" or not payload.get("jti"):
            raise ValueError("oauth_state_invalid")
        if payload["jti"] in self._consumed:
            raise ValueError("oauth_state_used")
        return payload

    def consume(self, payload: dict) -> None:
        self._consumed.add(payload["jti"])
        if len(self._consumed) > 2048:
            self._consumed = set(list(self._consumed)[-1024:])


oauth_state_manager = OAuthStateManager()
