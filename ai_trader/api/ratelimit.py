"""Lightweight per-process rate limiting (sliding window, in-memory).

Good enough for a single API process; set ``AI_TRADER_RATE_LIMIT=0`` to
disable (development / load-testing).
"""
from __future__ import annotations

import os
import time
from collections import defaultdict

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

ENABLED = os.getenv("AI_TRADER_RATE_LIMIT", "") != "0"
GLOBAL_LIMIT = int(os.getenv("AI_TRADER_GLOBAL_RATE_LIMIT", "240"))
AUTH_LIMIT = int(os.getenv("AI_TRADER_AUTH_RATE_LIMIT", "20"))


class RateLimiter:
    """Sliding-window counter keyed by ``(bucket, key)``."""

    def __init__(self, limit: int, window_s: float) -> None:
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[tuple[str, str], list[float]] = defaultdict(list)

    def check(self, bucket: str, key: str) -> bool:
        now = time.time()
        window = self._hits[(bucket, key)]
        cutoff = now - self.window_s
        window[:] = [t for t in window if t > cutoff]
        if len(window) >= self.limit:
            return False
        window.append(now)
        return True


global_limiter = RateLimiter(GLOBAL_LIMIT, 60.0)
auth_limiter = RateLimiter(AUTH_LIMIT, 60.0)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "?"


def require_auth_rate_limit(request: Request) -> None:
    """Dependency for /api/v1/auth/*: stricter per-IP cap."""
    if ENABLED and not auth_limiter.check("auth", _client_key(request)):
        raise HTTPException(status_code=429, detail="too many auth attempts, slow down")


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """Rejects requests that exceed the global per-IP window."""

    async def dispatch(self, request: Request, call_next):
        if not ENABLED:
            return await call_next(request)
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        bucket = "auth" if "/auth/" in path else "api"
        if not global_limiter.check(bucket, _client_key(request)):
            return JSONResponse(status_code=429, content={"detail": "rate limit exceeded, slow down"})
        return await call_next(request)