"""In-process + Redis-backed operational metrics for observability."""
from __future__ import annotations

import threading
import time
from typing import Any, Dict

from app.infra.redis_client import get_redis

_lock = threading.Lock()
_local: Dict[str, float] = {}
_started = time.time()


def incr(name: str, amount: float = 1.0) -> None:
    key = f'oplyra:metric:{name}'
    with _lock:
        _local[name] = _local.get(name, 0.0) + amount
    try:
        client = get_redis()
        client.incr(key)
    except Exception:
        pass


def observe(name: str, value_ms: float) -> None:
    """Record a latency sample (keeps last + sum/count for avg)."""
    incr(f'{name}.count', 1)
    incr(f'{name}.sum_ms', value_ms)
    with _lock:
        _local[f'{name}.last_ms'] = value_ms


def snapshot() -> Dict[str, Any]:
    with _lock:
        local_copy = dict(_local)
    return {
        'uptime_seconds': int(time.time() - _started),
        'counters': local_copy,
        'ai_requests': local_copy.get('ai.requests', 0),
        'tool_runs': local_copy.get('tool.runs', 0),
        'knowledge_searches': local_copy.get('knowledge.searches', 0),
        'http_requests': local_copy.get('http.requests', 0),
        'http_errors': local_copy.get('http.errors', 0),
        'embedding_jobs': local_copy.get('jobs.embeddings', 0),
        'queue_enqueued': local_copy.get('jobs.enqueued', 0),
    }


def reset_metrics():
    with _lock:
        _local.clear()
