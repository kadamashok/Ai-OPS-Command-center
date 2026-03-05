from __future__ import annotations

import os
import time
from collections import defaultdict

from fastapi import FastAPI
from redis import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class SreRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, limit_per_minute: int = 120) -> None:
        super().__init__(app)
        self.limit_per_minute = limit_per_minute
        self._local_buckets: dict[str, list[float]] = defaultdict(list)
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        try:
            self.redis = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=1)
            self.redis.ping()
        except Exception:
            self.redis = None

    async def dispatch(self, request: Request, call_next):
        key = self._key(request)
        if self.redis:
            allowed = self._check_redis(key)
        else:
            allowed = self._check_local(key)

        if not allowed:
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        return await call_next(request)

    def _key(self, request: Request) -> str:
        ip = request.client.host if request.client else "unknown"
        return f"sre-agent:ratelimit:{ip}:{request.url.path}"

    def _check_redis(self, key: str) -> bool:
        now_slot = int(time.time() // 60)
        redis_key = f"{key}:{now_slot}"
        count = self.redis.incr(redis_key)
        if count == 1:
            self.redis.expire(redis_key, 70)
        return int(count) <= self.limit_per_minute

    def _check_local(self, key: str) -> bool:
        now = time.time()
        bucket = [ts for ts in self._local_buckets[key] if now - ts < 60]
        if len(bucket) >= self.limit_per_minute:
            self._local_buckets[key] = bucket
            return False
        bucket.append(now)
        self._local_buckets[key] = bucket
        return True


def apply_sre_security(app: FastAPI) -> None:
    limit = int(os.getenv("SRE_RATE_LIMIT_PER_MIN", "120"))
    app.add_middleware(SreRateLimitMiddleware, limit_per_minute=limit)
