"""TokenBucket — Redis Lua atomic acquire (Story 3-3 — varco → llm key rename)."""

from __future__ import annotations

from unittest.mock import patch

import fakeredis
import pytest

from detection.src.rate_limit.token_bucket import (
    RateLimitTimeoutError,
    TokenBucket,
)
from shared.config.redis_config import REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY


@pytest.fixture
def fake_redis() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


def test_first_acquire_initializes_bucket(fake_redis: fakeredis.FakeRedis) -> None:
    bucket = TokenBucket(fake_redis, capacity=5, refill_per_sec=1)
    bucket.acquire()
    tokens = float(fake_redis.hget(REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY, "tokens"))
    assert tokens == 4.0


def test_acquire_decrements_existing_bucket(fake_redis: fakeredis.FakeRedis) -> None:
    bucket = TokenBucket(fake_redis, capacity=2, refill_per_sec=0.001)
    bucket.acquire()
    bucket.acquire()
    tokens = float(fake_redis.hget(REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY, "tokens"))
    assert tokens < 1


def test_acquire_waits_for_refill(fake_redis: fakeredis.FakeRedis) -> None:
    bucket = TokenBucket(fake_redis, capacity=1, refill_per_sec=10)
    bucket.acquire()
    with patch("detection.src.rate_limit.token_bucket.time.sleep") as mock_sleep:
        bucket.acquire(timeout=1)
    mock_sleep.assert_called()


def test_acquire_raises_on_timeout(fake_redis: fakeredis.FakeRedis) -> None:
    bucket = TokenBucket(fake_redis, capacity=1, refill_per_sec=0.001)
    bucket.acquire()
    with pytest.raises(RateLimitTimeoutError):
        bucket.acquire(timeout=0.05)


def test_lua_script_is_atomic(fake_redis: fakeredis.FakeRedis) -> None:
    """동일 키에 capacity=1로 2회 연속 acquire 시 두 번째는 sleep 후 재시도."""
    bucket = TokenBucket(fake_redis, capacity=1, refill_per_sec=100)
    bucket.acquire()
    with patch("detection.src.rate_limit.token_bucket.time.sleep") as mock_sleep:
        bucket.acquire(timeout=1)
    assert mock_sleep.call_count >= 1
