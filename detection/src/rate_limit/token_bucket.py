from __future__ import annotations

import os
import time

import redis

from shared.config.redis_config import REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY
from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
_logger = get_logger(__name__)


class RateLimitTimeoutError(Exception):
    """`acquire(timeout)` 내에 토큰을 획득하지 못한 경우."""


# KEYS[1] = bucket key
# ARGV[1] = capacity, ARGV[2] = refill_per_sec, ARGV[3] = now (float seconds)
# 반환: 획득 성공 시 "0", 실패 시 다음 토큰 충전까지 남은 초(float, >0) 문자열
_LUA_ACQUIRE = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

if tokens == nil then
  tokens = capacity
  last_refill = now
else
  local elapsed = now - last_refill
  if elapsed > 0 then
    tokens = math.min(capacity, tokens + elapsed * refill)
    last_refill = now
  end
end

if tokens >= 1 then
  tokens = tokens - 1
  redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
  redis.call('EXPIRE', key, 3600)
  return '0'
else
  redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
  redis.call('EXPIRE', key, 3600)
  local wait = (1 - tokens) / refill
  return tostring(wait)
end
"""


class TokenBucket:
    def __init__(
        self,
        redis_client: redis.Redis,
        key: str = REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY,
        capacity: int | None = None,
        refill_per_sec: float | None = None,
    ) -> None:
        self._redis = redis_client
        self._key = key
        self._capacity = int(
            capacity if capacity is not None
            else os.environ.get("LLM_RATE_LIMIT_CAPACITY", "60")
        )
        self._refill = float(
            refill_per_sec if refill_per_sec is not None
            else os.environ.get("LLM_RATE_LIMIT_REFILL_PER_SEC", "1")
        )
        self._script = self._redis.register_script(_LUA_ACQUIRE)

    def acquire(self, timeout: float | None = None) -> None:
        """토큰 1개 차감. 부족 시 충전까지 sleep 후 재시도. timeout 초과 시 RateLimitTimeoutError."""
        if timeout is None:
            timeout = float(os.environ.get("LLM_RATE_LIMIT_MAX_WAIT_SEC", "120"))
        deadline = time.monotonic() + timeout
        while True:
            wait_str = self._script(
                keys=[self._key],
                args=[self._capacity, self._refill, time.time()],
            )
            wait = float(wait_str)
            if wait == 0:
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0 or wait > remaining:
                raise RateLimitTimeoutError(
                    f"token bucket timeout after {timeout}s (next refill in {wait:.2f}s)"
                )
            _logger.warning(
                "토큰 버킷 대기 — wait=%.2fs",
                wait,
                extra={"correlation_id": "", "service": _SERVICE_NAME},
            )
            time.sleep(wait)
