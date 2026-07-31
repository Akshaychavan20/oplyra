"""Redis-backed platform flags & user suspension — no schema changes."""
from __future__ import annotations

import json
from typing import Dict, List

FLAG_KEYS = {
    'maintenance_mode': False,
    'experimental_ai_studio': True,
    'experimental_mcp': True,
    'experimental_tool_marketplace': True,
    'signup_enabled': True,
    'billing_enforcement': False,
}

SUSPEND_KEY = 'oplyra:platform:suspended_users'
FLAGS_KEY = 'oplyra:platform:feature_flags'


def _redis():
    from app.infra.redis_client import get_redis
    return get_redis()


def get_flags() -> Dict[str, bool]:
    flags = dict(FLAG_KEYS)
    try:
        raw = _redis().get(FLAGS_KEY)
        if raw:
            data = json.loads(raw if isinstance(raw, str) else raw.decode('utf-8'))
            if isinstance(data, dict):
                for k, v in data.items():
                    flags[k] = bool(v)
    except Exception:
        pass
    return flags


def set_flag(key: str, enabled: bool) -> Dict[str, bool]:
    flags = get_flags()
    if key not in FLAG_KEYS and key not in flags:
        flags[key] = bool(enabled)
    else:
        flags[key] = bool(enabled)
    try:
        _redis().set(FLAGS_KEY, json.dumps(flags))
    except Exception:
        pass
    return flags


def list_suspended_user_ids() -> List[int]:
    try:
        raw = _redis().get(SUSPEND_KEY)
        if not raw:
            return []
        data = json.loads(raw if isinstance(raw, str) else raw.decode('utf-8'))
        return [int(x) for x in data]
    except Exception:
        return []


def is_user_suspended(user_id: int) -> bool:
    return int(user_id) in set(list_suspended_user_ids())


def suspend_user(user_id: int) -> None:
    ids = set(list_suspended_user_ids())
    ids.add(int(user_id))
    _redis().set(SUSPEND_KEY, json.dumps(sorted(ids)))


def activate_user(user_id: int) -> None:
    ids = set(list_suspended_user_ids())
    ids.discard(int(user_id))
    _redis().set(SUSPEND_KEY, json.dumps(sorted(ids)))
