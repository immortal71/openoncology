"""Redis caching helpers — Phase 7 scale & observability.

Provides a simple async cache layer around expensive external API calls and
compute-heavy operations to reduce latency and rate-limit exposure:

  - Per-gene cBioPortal frequency data     TTL = 24h
  - OncoKB annotation results              TTL = 7 days
  - ClinicalTrials.gov search results      TTL = 6h
  - Survival curve computations            TTL = 12h
  - Pathway annotations (static, long TTL) TTL = 7 days

Usage:
    from services.cache import cached_json, invalidate

    @cached_json("oncokb:{gene}:{alteration}", ttl=604800)
    async def get_oncokb_annotation(gene, alteration, **kwargs):
        ...

The cache degrades gracefully: if Redis is unavailable, functions execute
normally without caching and a warning is logged.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Lazy-initialised Redis client
_redis_client = None


def _get_redis():
    """Return a Redis async client, initialising it on first call."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis.asyncio as aioredis
        from config import settings
        redis_url = getattr(settings, "redis_url", "redis://localhost:6379/0")
        _redis_client = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        logger.info("[cache] Redis connected: %s", redis_url)
    except Exception as exc:
        logger.warning("[cache] Redis init failed — caching disabled: %s", exc)
        _redis_client = None
    return _redis_client


async def cache_get(key: str) -> Optional[Any]:
    """Return cached JSON value for key, or None if missing / Redis unavailable."""
    r = _get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        logger.debug("[cache] GET failed for %s: %s", key, exc)
        return None


async def cache_set(key: str, value: Any, ttl: int = 3600) -> bool:
    """Set a JSON-serialisable value in Redis with a TTL in seconds."""
    r = _get_redis()
    if r is None:
        return False
    try:
        await r.setex(key, ttl, json.dumps(value, default=str))
        return True
    except Exception as exc:
        logger.debug("[cache] SET failed for %s: %s", key, exc)
        return False


async def cache_delete(key: str) -> None:
    """Delete a key from the cache."""
    r = _get_redis()
    if r is None:
        return
    try:
        await r.delete(key)
    except Exception as exc:
        logger.debug("[cache] DEL failed for %s: %s", key, exc)


def make_key(prefix: str, *args, **kwargs) -> str:
    """Build a stable cache key from a prefix + args/kwargs."""
    payload = f"{args}:{sorted(kwargs.items())}"
    digest = hashlib.md5(payload.encode()).hexdigest()[:8]
    return f"{prefix}:{digest}"


def cached_json(key_template: str, ttl: int = 3600):
    """Decorator: cache the async function's return value as JSON in Redis.

    Key is built from key_template formatted with the function's kwargs.
    Falls back to direct call if Redis is unavailable.

    Example:
        @cached_json("oncokb:{gene}:{variant}", ttl=604800)
        async def get_oncokb(gene: str, variant: str, db=None):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                cache_key = key_template.format(**kwargs)
            except KeyError:
                # Fall back to hash-based key if template variables not in kwargs
                cache_key = make_key(key_template.split(":")[0], *args, **kwargs)

            # Try cache first
            cached = await cache_get(cache_key)
            if cached is not None:
                logger.debug("[cache] HIT %s", cache_key)
                return cached

            # Execute the function
            result = await func(*args, **kwargs)

            # Store result if non-None
            if result is not None:
                await cache_set(cache_key, result, ttl=ttl)
                logger.debug("[cache] MISS+SET %s (ttl=%ds)", cache_key, ttl)

            return result
        return wrapper
    return decorator


# ── Named TTL constants ────────────────────────────────────────────────────────

# External API TTLs (in seconds)
TTL_ONCOKB = 7 * 24 * 3600       # 7 days — OncoKB data is stable
TTL_CBIOPORTAL = 24 * 3600       # 24h   — frequency data is stable
TTL_CLINICAL_TRIALS = 6 * 3600   # 6h    — trial status changes regularly
TTL_SURVIVAL = 12 * 3600         # 12h   — computed from static cohort data
TTL_PATHWAY = 7 * 24 * 3600      # 7 days — pathway maps are static
TTL_HOTSPOT = 30 * 24 * 3600     # 30 days — Cancer Hotspots v2 is static
TTL_DRUG_RANKING = 1 * 3600      # 1h    — recomputed per submission


async def invalidate_gene_cache(gene: str) -> None:
    """Invalidate all cache keys for a gene (call after DB update)."""
    r = _get_redis()
    if r is None:
        return
    try:
        pattern = f"*{gene.upper()}*"
        keys = await r.keys(pattern)
        if keys:
            await r.delete(*keys)
            logger.info("[cache] Invalidated %d keys for gene %s", len(keys), gene)
    except Exception as exc:
        logger.debug("[cache] Invalidation failed for %s: %s", gene, exc)
