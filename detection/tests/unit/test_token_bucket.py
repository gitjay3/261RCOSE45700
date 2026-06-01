"""TokenBucket — Redis Lua atomic acquire for LLM rate limiting."""

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
    """capacity=1: 토큰 소진 후 두 번째 acquire는 충전까지 sleep 후 재시도.

    리필을 실시간(time.time)이 아니라 sleep이 전진시키는 가상 시계로 구동해 결정화한다.
    (느린 CI에서 두 acquire 사이 실시간이 흘러 토큰이 미리 충전되며 sleep을 건너뛰던 플래키 제거.)
    """
    clock = {"t": 1000.0}

    def fake_sleep(seconds: float) -> None:
        # 대기분 + 여유를 더해 다음 시도에 확실히 1토큰 이상 충전 (float 경계/Zeno 회피)
        clock["t"] += max(seconds, 0.0) + 0.02

    bucket = TokenBucket(fake_redis, capacity=1, refill_per_sec=100)
    with patch("detection.src.rate_limit.token_bucket.time.time", lambda: clock["t"]):
        bucket.acquire()  # 유일 토큰 소진 (가상 시계 고정이라 리필 0)
        with patch(
            "detection.src.rate_limit.token_bucket.time.sleep",
            side_effect=fake_sleep,
        ) as mock_sleep:
            bucket.acquire(timeout=1)
    assert mock_sleep.call_count >= 1
