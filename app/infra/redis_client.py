"""Shared Redis client factory (cache, rate limits, Celery broker)."""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_client: Any = None
_memory_store: dict = {}


class MemoryRedis:
    """Minimal in-process Redis stand-in for tests / missing Redis."""

    def get(self, key):
        item = _memory_store.get(key)
        if not item:
            return None
        value, expires_at = item
        import time
        if expires_at is not None and time.time() > expires_at:
            _memory_store.pop(key, None)
            return None
        return value if isinstance(value, bytes) else str(value).encode('utf-8')

    def set(self, key, value, ex=None, nx=False):
        import time
        if nx and key in _memory_store:
            return False
        expires = time.time() + ex if ex else None
        raw = value if isinstance(value, bytes) else str(value).encode('utf-8')
        _memory_store[key] = (raw, expires)
        return True

    def setex(self, key, time_seconds, value):
        return self.set(key, value, ex=time_seconds)

    def incr(self, key):
        cur = self.get(key)
        n = int(cur.decode('utf-8')) + 1 if cur else 1
        self.set(key, str(n))
        return n

    def expire(self, key, seconds):
        import time
        cur = self.get(key)
        if cur is None:
            return False
        _memory_store[key] = (cur, time.time() + seconds)
        return True

    def delete(self, *keys):
        for k in keys:
            _memory_store.pop(k, None)
        return len(keys)

    def ping(self):
        return True

    def llen(self, key):
        return 0

    def exists(self, key):
        return 1 if self.get(key) is not None else 0


def reset_redis_client():
    global _client
    _client = None
    _memory_store.clear()


def get_redis(url: Optional[str] = None, *, allow_memory: bool = True):
    """Return Redis client, or MemoryRedis when unavailable (dev/test)."""
    global _client
    if _client is not None:
        return _client

    redis_url = url or os.environ.get('REDIS_URL')
    try:
        from flask import current_app
        if not redis_url:
            redis_url = current_app.config.get('REDIS_URL') or current_app.config.get('CELERY_BROKER_URL')
        force_memory = current_app.config.get('REDIS_FORCE_MEMORY')
        if force_memory:
            _client = MemoryRedis()
            return _client
    except RuntimeError:
        pass

    if redis_url:
        try:
            import redis
            client = redis.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
            client.ping()
            _client = client
            return _client
        except Exception as exc:
            logger.warning('Redis unavailable (%s); falling back to memory store', type(exc).__name__)

    if allow_memory:
        _client = MemoryRedis()
        return _client
    return None


def cache_get(key: str) -> Optional[str]:
    client = get_redis()
    if not client:
        return None
    try:
        raw = client.get(f'oplyra:cache:{key}')
        return raw.decode('utf-8') if raw else None
    except Exception:
        return None


def cache_set(key: str, value: str, ttl_seconds: int = 300) -> bool:
    client = get_redis()
    if not client:
        return False
    try:
        client.setex(f'oplyra:cache:{key}', ttl_seconds, value)
        return True
    except Exception:
        return False
