"""Small security primitives shared by API routes."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status

from app.config import settings


def error_detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


@dataclass(frozen=True)
class RateLimit:
    attempts: int
    window_seconds: int


class InMemoryRateLimiter:
    """Per-process sliding-window limiter suitable for this single-user app."""

    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, bucket: str, identity: str, limit: RateLimit) -> None:
        now = time.monotonic()
        key = (bucket, identity)
        async with self._lock:
            events = self._events[key]
            while events and now - events[0] >= limit.window_seconds:
                events.popleft()
            if len(events) >= limit.attempts:
                retry_after = max(1, int(limit.window_seconds - (now - events[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=error_detail("rate_limited", "Too many attempts. Please try again later."),
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(now)

    async def clear(self, bucket: str, identity: str) -> None:
        async with self._lock:
            self._events.pop((bucket, identity), None)


rate_limiter = InMemoryRateLimiter()


def client_identity(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _validated_origin(value: str) -> str:
    parsed = urlsplit(value.strip().rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=400, detail=error_detail("invalid_origin", "A valid WebUI origin is required."))
    hostname = parsed.hostname.lower()
    if parsed.scheme != "https" and hostname not in {"localhost", "127.0.0.1", "::1", "test"}:
        raise HTTPException(
            status_code=400,
            detail=error_detail("https_required", "HTTPS is required for non-local OAuth redirects."),
        )
    return f"{parsed.scheme}://{parsed.netloc}"


def public_origin(request: Request) -> str:
    """Resolve the only redirect/postMessage origin the backend will use."""
    if settings.PUBLIC_BASE_URL:
        return _validated_origin(settings.PUBLIC_BASE_URL)

    request_origin = request.headers.get("origin")
    base_origin = f"{request.url.scheme}://{request.url.netloc}"
    if request_origin:
        candidate = _validated_origin(request_origin)
        allowed = set(settings.allowed_origins)
        if candidate != base_origin.rstrip("/") and candidate not in allowed:
            raise HTTPException(status_code=400, detail=error_detail("origin_not_allowed", "The WebUI origin is not allowed."))
        return candidate
    return _validated_origin(base_origin)
