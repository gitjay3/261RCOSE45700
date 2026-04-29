from __future__ import annotations

import os

from shared.config.redis_config import REDIS_KEY_POSTS_QUEUE
from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "crawler")
_logger = get_logger(__name__)


class RedisPublisher:
    """Redis DB0 posts:queue 에 CrawlEvent JSON을 LPUSH."""

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    def enqueue(self, event_json: str, *, correlation_id: str) -> None:
        self._redis.lpush(REDIS_KEY_POSTS_QUEUE, event_json)
        _logger.info(
            "posts:queue LPUSH 완료",
            extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
        )
