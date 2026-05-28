from __future__ import annotations

import hashlib
import os

import redis

from shared.config.redis_config import REDIS_KEY_POSTS_DEDUP
from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "crawler")
_logger = get_logger(__name__)


class DedupChecker:
    """Redis 기반 중복 게시글 체크."""

    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def is_duplicate(self, text: str, *, correlation_id: str) -> bool:
        if not text or not text.strip():
            return False
        h = self._hash(text)
        result = bool(self._redis.sismember(REDIS_KEY_POSTS_DEDUP, h))
        _logger.debug(
            "중복 체크: hash=%s duplicate=%s", h, result,
            extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
        )
        return result

    def mark_seen(self, text: str, *, correlation_id: str) -> None:
        if not text or not text.strip():
            return
        h = self._hash(text)
        self._redis.sadd(REDIS_KEY_POSTS_DEDUP, h)
        _logger.debug(
            "중복 등록: hash=%s", h,
            extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
        )
