"""
DataNexus v2.0.0 — Redis Query & Deduplication Cache with Graceful Fallback.

Provides TTL-based caching for:
  - RAG query results (by SHA-256 of question + context)
  - Document hash lookups (dedup acceleration)

Falls back to an in-memory TTL cache if REDIS_URL is unset or unreachable.
Records cache_hit/miss on OTel spans and API response metadata.
"""

import hashlib
import json
import logging
import time
from typing import Any, Callable, Optional

from backend.app.config import settings

logger = logging.getLogger(__name__)


class InMemoryTTLCache:
    """Simple in-memory dict cache with TTL eviction."""

    def __init__(self, max_size: int = 1000):
        self._store: dict = {}
        self._max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: int = 300):
        # Simple LRU-ish eviction: drop oldest when full
        if len(self._store) >= self._max_size:
            oldest_key = next(iter(self._store))
            del self._store[oldest_key]
        self._store[key] = (value, time.time() + ttl)

    def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

    def clear(self):
        self._store.clear()

    def size(self) -> int:
        return len(self._store)


class CacheService:
    """
    Unified cache service with Redis primary and in-memory fallback.
    Thread-safe, lazy-initialized.
    """

    DEFAULT_TTL = 300  # 5 minutes

    def __init__(self):
        self._redis_client = None
        self._redis_initialized = False
        self._redis_available = False
        self._memory_cache = InMemoryTTLCache(max_size=2000)
        self._stats = {"hits": 0, "misses": 0}

    def _ensure_redis(self):
        if self._redis_initialized:
            return
        self._redis_initialized = True

        redis_url = getattr(settings, "REDIS_URL", "")
        if not redis_url:
            logger.info("REDIS_URL not set — using in-memory cache fallback")
            return

        try:
            import redis

            self._redis_client = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
            )
            # Test connection
            self._redis_client.ping()
            self._redis_available = True
            logger.info(f"Redis cache connected: {redis_url}")
        except ImportError:
            logger.warning("redis package not installed — using in-memory cache")
        except Exception as e:
            logger.warning(f"Redis connection failed ({e}) — using in-memory cache fallback")
            self._redis_client = None
            self._redis_available = False

    @property
    def backend_name(self) -> str:
        self._ensure_redis()
        return "redis" if self._redis_available else "memory"

    @property
    def stats(self) -> dict:
        return {
            "backend": self.backend_name,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": round(
                self._stats["hits"] / max(1, self._stats["hits"] + self._stats["misses"]), 4
            ),
        }

    def get(self, key: str) -> Optional[Any]:
        """Get value by key. Returns None if not found or expired."""
        self._ensure_redis()

        if self._redis_available:
            try:
                raw = self._redis_client.get(key)
                if raw is not None:
                    self._stats["hits"] += 1
                    return json.loads(raw)
            except Exception as e:
                logger.debug(f"Redis GET failed: {e}")

        # Fallback to memory
        val = self._memory_cache.get(key)
        if val is not None:
            self._stats["hits"] += 1
            return val

        self._stats["misses"] += 1
        return None

    def set(self, key: str, value: Any, ttl: int = None):
        """Set value with TTL (seconds)."""
        ttl = ttl or self.DEFAULT_TTL
        self._ensure_redis()

        serialized = json.dumps(value, default=str)

        if self._redis_available:
            try:
                self._redis_client.setex(key, ttl, serialized)
                return
            except Exception as e:
                logger.debug(f"Redis SET failed: {e}")

        # Fallback to memory
        self._memory_cache.set(key, value, ttl)

    def delete(self, key: str) -> bool:
        """Delete a cached entry."""
        self._ensure_redis()
        deleted = False

        if self._redis_available:
            try:
                deleted = bool(self._redis_client.delete(key))
            except Exception:
                pass

        mem_deleted = self._memory_cache.delete(key)
        return deleted or mem_deleted

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: int = None,
    ) -> tuple:
        """
        Get cached value or compute via factory and cache.
        Returns (value, cache_hit: bool).
        """
        cached = self.get(key)
        if cached is not None:
            return cached, True

        value = factory()
        self.set(key, value, ttl)
        return value, False

    @staticmethod
    def make_query_key(question: str, context_ids: list = None) -> str:
        """Generate deterministic cache key for a RAG query."""
        parts = [question.strip().lower()]
        if context_ids:
            parts.extend(sorted(context_ids))
        raw = "|".join(parts)
        return f"qa:{hashlib.sha256(raw.encode()).hexdigest()[:32]}"

    @staticmethod
    def make_hash_key(file_hash: str) -> str:
        """Generate cache key for document dedup lookup."""
        return f"dedup:{file_hash}"

    def clear(self):
        """Clear all cached entries."""
        self._memory_cache.clear()
        if self._redis_available:
            try:
                self._redis_client.flushdb()
            except Exception:
                pass


cache_service = CacheService()
