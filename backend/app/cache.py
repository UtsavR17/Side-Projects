"""Cache-aside helper with Redis as the primary store.

Design rules (per master plan §6):
  * The API only ever READS from cache/DB — it never triggers scrapes or model runs.
  * Cache entries are written/invalidated by the background pipeline (cache warming)
    and opportunistically on a read miss (classic cache-aside), with a TTL so
    stale data self-heals even if a pipeline run is missed.
  * If Redis is unreachable (local dev without Docker), an in-process TTL dict
    takes over so the API still works — just without cross-process sharing.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

import redis

from app.config import settings

logger = logging.getLogger(__name__)


class _MemoryStore:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at and expires_at < time.time():
                del self._data[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        with self._lock:
            self._data[key] = (time.time() + ttl if ttl else 0, value)

    def delete(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._data.pop(key, None)

    def delete_prefix(self, prefix: str) -> int:
        with self._lock:
            victims = [k for k in self._data if k.startswith(prefix)]
            for key in victims:
                del self._data[key]
            return len(victims)


class Cache:
    def __init__(self) -> None:
        self._memory = _MemoryStore()
        self._redis: redis.Redis | None = None
        self._connect()

    def _connect(self) -> None:
        try:
            client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            client.ping()
            self._redis = client
            logger.info("Cache: connected to Redis at %s", settings.redis_url)
        except Exception as exc:  # noqa: BLE001 — degrade, don't crash
            self._redis = None
            logger.warning("Cache: Redis unavailable (%s); using in-process memory store", exc)

    @property
    def backend(self) -> str:
        return "redis" if self._redis is not None else "memory"

    def get_json(self, key: str) -> Any | None:
        if self._redis is None:
            return _loads(self._memory.get(key))
        try:
            raw = self._redis.get(key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cache get failed (%s); falling back to memory", exc)
            self._redis = None
            return _loads(self._memory.get(key))
        return _loads(raw)

    def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl = settings.cache_ttl_seconds if ttl is None else ttl
        payload = json.dumps(value, default=str)
        if self._redis is None:
            self._memory.set(key, payload, ttl)  # store the serialized form
            # memory store returns str; get_json must json.loads it too
            return
        try:
            self._redis.set(key, payload, ex=ttl)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cache set failed (%s); falling back to memory", exc)
            self._redis = None
            self._memory.set(key, payload, ttl)

    def delete(self, *keys: str) -> None:
        if not keys:
            return
        if self._redis is None:
            self._memory.delete(*keys)
            return
        try:
            self._redis.delete(*keys)
        except Exception:  # noqa: BLE001
            self._redis = None
            self._memory.delete(*keys)

    def delete_prefix(self, prefix: str) -> int:
        if self._redis is None:
            return self._memory.delete_prefix(prefix)
        try:
            count = 0
            for key in self._redis.scan_iter(match=f"{prefix}*"):
                self._redis.delete(key)
                count += 1
            return count
        except Exception:  # noqa: BLE001
            self._redis = None
            return self._memory.delete_prefix(prefix)

    # --- pub/sub channel for SSE "new prediction" events --------------------
    def publish(self, channel: str, message: dict) -> None:
        if self._redis is None:
            return  # in-process fallback can't cross process boundaries
        try:
            self._redis.publish(channel, json.dumps(message, default=str))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cache publish failed: %s", exc)

    def pubsub(self):
        if self._redis is None:
            return None
        try:
            return self._redis.pubsub()
        except Exception:  # noqa: BLE001
            return None


cache = Cache()


def _loads(raw: Any) -> Any | None:
    if raw is None:
        return None
    if isinstance(raw, (dict, list, int, float, bool)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def get_json_or_compute(key: str, compute, ttl: int | None = None):
    """Classic cache-aside read path used by every GET endpoint."""
    cached = cache.get_json(key)
    if cached is not None:
        return cached
    value = compute()
    if value is not None:
        cache.set_json(key, value, ttl)
    return value
