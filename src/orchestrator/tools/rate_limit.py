"""Fixed-window per-tool rate limiting backed by Redis (INCR + EXPIRE)."""
from __future__ import annotations

import time

from orchestrator.memory.redis_client import get_redis


def check_rate_limit(tool_name: str, limit_per_minute: int) -> tuple[bool, int]:
    """Returns (allowed, seconds_until_window_resets)."""
    r = get_redis()
    window = int(time.time() // 60)
    key = f"ratelimit:{tool_name}:{window}"

    count = r.incr(key)
    if count == 1:
        r.expire(key, 60)

    if count > limit_per_minute:
        ttl = r.ttl(key)
        return False, max(ttl, 0)
    return True, 0


class ToolRateLimitExceeded(RuntimeError):
    pass
