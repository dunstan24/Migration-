"""
cache/redis_client.py
Redis client — HTTP response cache + background job queue broker
Per README: /api/data/* responses cached with TTL
"""
import logging
import time
from config import settings

logger = logging.getLogger(__name__)
_redis = None
_redis_failed = False
_local_cache = {}


async def get_redis():
    global _redis, _redis_failed
    if _redis is None and not _redis_failed:
        try:
            import redis.asyncio as aioredis
            r = await aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
            )
            # Ping to eagerly catch connection errors
            await r.ping()
            _redis = r
        except Exception as e:
            logger.warning(f"Redis unavailable: {e} — using local memory fallback")
            _redis_failed = True
            _redis = None
    return _redis


async def get_cache(key: str) -> str | None:
    """Check Redis cache (or local fallback) — return value or None (MISS)."""
    r = await get_redis()
    if r:
        try:
            val = await r.get(key)
            if val is not None:
                return val
        except Exception:
            pass
            
    # Fallback to local cache
    entry = _local_cache.get(key)
    if entry:
        if entry["expires"] > time.time():
            return entry["value"]
        else:
            del _local_cache[key]
    return None


async def set_cache(key: str, value: str, ttl: int = None) -> None:
    """Set Redis cache (or local fallback) with TTL."""
    r = await get_redis()
    if r:
        try:
            await r.setex(key, ttl or settings.CACHE_DEFAULT_TTL, value)
            return
        except Exception as e:
            logger.warning(f"Redis Cache set failed: {e}")
            
    # Fallback to local cache
    _local_cache[key] = {
        "value": value,
        "expires": time.time() + (ttl or settings.CACHE_DEFAULT_TTL)
    }
