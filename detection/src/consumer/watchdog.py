from __future__ import annotations

import os
import time

import redis

from shared.config.redis_config import (
    REDIS_KEY_POSTS_CORRUPT,
    REDIS_KEY_POSTS_DLQ,
    REDIS_KEY_POSTS_PROCESSING,
    REDIS_KEY_POSTS_QUEUE,
)
from shared.models.crawl_event import CrawlEvent
from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
_STALE_SECONDS = int(os.environ.get("WATCHDOG_STALE_SECONDS", "300"))
_POLL_INTERVAL = int(os.environ.get("WATCHDOG_POLL_INTERVAL", "60"))
_MAX_RETRIES = 3
_logger = get_logger(__name__)


def retry_key(post_id: str) -> str:
    return f"posts:retry:{post_id}"


def processing_time_key(post_id: str) -> str:
    return f"posts:processing_time:{post_id}"


class Watchdog:
    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client

    def mark_processing(self, message: str) -> None:
        """Consumer가 BRPOPLPUSH 직후 호출 — 처리 시작 시각 기록."""
        try:
            event = CrawlEvent.from_json(message)
            self._redis.setex(
                processing_time_key(event.post_id),
                _STALE_SECONDS,
                "1",
            )
        except Exception:
            pass  # 타임스탬프 기록 실패는 stale 판정으로 처리

    def scan_once(self) -> int:
        """posts:processing 전체 스캔. 처리한 stale/corrupt 메시지 수 반환."""
        messages = self._redis.lrange(REDIS_KEY_POSTS_PROCESSING, 0, -1)
        handled = 0
        for message in messages:
            try:
                event = CrawlEvent.from_json(message)
                post_id = event.post_id
            except Exception as exc:
                # Poison message 격리 — posts:corrupt로 LPUSH + processing에서 LREM
                self._redis.lpush(REDIS_KEY_POSTS_CORRUPT, message)
                self._redis.lrem(REDIS_KEY_POSTS_PROCESSING, 1, message)
                _logger.error(
                    "Corrupt 메시지 격리 — from_json 실패: %s", exc,
                    extra={"correlation_id": "", "service": _SERVICE_NAME},
                )
                handled += 1
                continue

            is_stale = not self._redis.exists(processing_time_key(post_id))
            if not is_stale:
                continue

            retry_count = int(self._redis.get(retry_key(post_id)) or 0)
            if retry_count >= _MAX_RETRIES:
                self._redis.lpush(REDIS_KEY_POSTS_DLQ, message)
                self._redis.lrem(REDIS_KEY_POSTS_PROCESSING, 1, message)
                self._redis.delete(retry_key(post_id))
                _logger.error(
                    "DLQ 이동 — 최대 재시도 초과",
                    extra={
                        "post_id": post_id,
                        "correlation_id": event.correlation_id,
                        "service": _SERVICE_NAME,
                    },
                )
            else:
                self._redis.rpush(REDIS_KEY_POSTS_QUEUE, message)
                self._redis.lrem(REDIS_KEY_POSTS_PROCESSING, 1, message)
                self._redis.incr(retry_key(post_id))
                _logger.warning(
                    "Watchdog 재투입 — retry=%d post_id=%s",
                    retry_count + 1,
                    post_id,
                    extra={
                        "correlation_id": event.correlation_id,
                        "service": _SERVICE_NAME,
                    },
                )
            handled += 1
        return handled

    def run_forever(self) -> None:
        _logger.info(
            "Watchdog 시작 — stale_threshold=%ds, poll_interval=%ds",
            _STALE_SECONDS,
            _POLL_INTERVAL,
            extra={"correlation_id": "", "service": _SERVICE_NAME},
        )
        while True:
            time.sleep(_POLL_INTERVAL)
            self.scan_once()
