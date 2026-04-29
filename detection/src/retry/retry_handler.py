from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import TypeVar

import httpx
import redis

from detection.src.consumer.watchdog import processing_time_key, retry_key
from detection.src.mocks.varco_mock import RateLimitError
from shared.config.redis_config import (
    REDIS_KEY_POSTS_DLQ,
    REDIS_KEY_POSTS_PROCESSING,
)
from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
_MAX_ATTEMPTS = int(os.environ.get("RETRY_MAX_ATTEMPTS", "3"))
_BACKOFF_BASE = float(os.environ.get("RETRY_BACKOFF_BASE_SEC", "1"))
_logger = get_logger(__name__)

# 일시적 외부 오류만 화이트리스트로 재시도.
# RateLimitError(quota — 호출자 책임) / ValueError(영구 오류) / 코드 버그는 즉시 propagate.
_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    TimeoutError,
    ConnectionError,
    httpx.HTTPError,
)

T = TypeVar("T")


class RetryExhaustedError(Exception):
    """재시도 한도 초과 후 DLQ 이동 완료 시 raise — QueueConsumer가 catch."""

    def __init__(self, post_id: str, attempts: int, last_error: BaseException) -> None:
        self.post_id = post_id
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"retry exhausted after {attempts} attempts for post_id={post_id}: "
            f"{type(last_error).__name__}: {last_error}"
        )


class RetryHandler:
    """retryable 예외를 exponential backoff으로 재시도. 한도 초과 시 DLQ 이동."""

    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client

    def execute_with_retry(
        self,
        func: Callable[[], T],
        *,
        message: str,
        post_id: str,
        correlation_id: str,
    ) -> T:
        last_error: BaseException | None = None
        total_attempts = _MAX_ATTEMPTS + 1  # 원본 1 + 재시도 N

        for attempt in range(total_attempts):
            try:
                return func()
            except _RETRYABLE_EXCEPTIONS as exc:
                last_error = exc
                if attempt < total_attempts - 1:
                    backoff = _BACKOFF_BASE * (2 ** attempt)
                    _logger.warning(
                        "VARCO classify 재시도 — attempt=%d/%d, backoff=%.1fs, error=%s",
                        attempt + 1, total_attempts, backoff, type(exc).__name__,
                        extra={
                            "post_id": post_id,
                            "correlation_id": correlation_id,
                            "service": _SERVICE_NAME,
                        },
                    )
                    time.sleep(backoff)
            # RateLimitError / ValueError 등 비-retryable은 except 절에 안 잡힘 → 자동 propagate

        # 한도 초과 — DLQ 이동
        assert last_error is not None
        self._move_to_dlq(message, post_id, correlation_id, last_error, total_attempts)
        raise RetryExhaustedError(post_id, total_attempts, last_error)

    def _move_to_dlq(
        self,
        message: str,
        post_id: str,
        correlation_id: str,
        last_error: BaseException,
        attempts: int,
    ) -> None:
        self._redis.lpush(REDIS_KEY_POSTS_DLQ, message)
        self._redis.lrem(REDIS_KEY_POSTS_PROCESSING, 1, message)
        self._redis.delete(retry_key(post_id))
        self._redis.delete(processing_time_key(post_id))
        _logger.error(
            "DLQ 이동 — VARCO classify 재시도 한도 초과 (attempts=%d)",
            attempts,
            extra={
                "post_id": post_id,
                "correlation_id": correlation_id,
                "service": _SERVICE_NAME,
                "last_error_type": type(last_error).__name__,
            },
        )
