from __future__ import annotations

import json
from typing import Any

import redis
import redis.asyncio as aioredis

from .config import get_settings

_pool: redis.ConnectionPool | None = None
_async_client: aioredis.Redis | None = None


def get_redis() -> redis.Redis:
    global _pool
    settings = get_settings()
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)
    return redis.Redis(connection_pool=_pool)


def get_async_redis() -> aioredis.Redis:
    global _async_client
    settings = get_settings()
    if _async_client is None:
        _async_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _async_client


def ping_redis() -> bool:
    try:
        return bool(get_redis().ping())
    except redis.RedisError:
        return False


def publish_alert(payload: dict[str, Any]) -> None:
    settings = get_settings()
    try:
        get_redis().publish(settings.redis_alerts_channel, json.dumps(payload, default=str))
    except redis.RedisError:
        pass


def mark_tx_seen(tx_hash: str, ttl_seconds: int = 7 * 24 * 3600) -> bool:
    """Returns True if this tx hash was not seen before (first time)."""
    key = f"podium:seen:{tx_hash}"
    try:
        return bool(get_redis().set(key, "1", nx=True, ex=ttl_seconds))
    except redis.RedisError:
        # Without Redis, rely on DB unique tx_hash constraint only.
        return True


def cache_price(symbol: str, usd: float, ttl_seconds: int = 90) -> None:
    get_redis().setex(f"podium:price:{symbol.upper()}", ttl_seconds, str(usd))


def get_cached_price(symbol: str) -> float | None:
    raw = get_redis().get(f"podium:price:{symbol.upper()}")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None
