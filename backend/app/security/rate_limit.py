"""Redis fixed-window rate limiting. Active in hardened mode only.

Fails open if Redis is unavailable (we never want the target to 500 on VectorGuard
just because Redis blinked) but still enforces limits when reachable.
"""
from __future__ import annotations

import time

import redis.asyncio as aioredis
from fastapi import HTTPException, status

from ..config import settings
from .mode import is_hardened

_redis: aioredis.Redis | None = None


def _client() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def enforce(bucket: str, identity: str, per_minute: int) -> None:
    if not is_hardened():
        return  # naive mode has no rate limiting by design
    window = int(time.time() // 60)
    key = f"rl:{bucket}:{identity}:{window}"
    try:
        client = _client()
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, 60)
    except Exception:
        return  # fail open
    if count > per_minute:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Rate limit exceeded ({per_minute}/min for {bucket})",
        )
