"""크로스-run URL 중복 차단.

시간 단위로 크롤러가 돌 때 같은 게시글 URL 을 다시 fetch 하지 않도록 함.
text dedup(DedupChecker) 보다 한 단계 더 위에서 — fetch 자체를 막아 절약.

저장 구조 — Redis sorted set "posts:seen_urls"
    member: URL 문자열
    score:  최초 mark_seen() 시점의 unix timestamp (float)

TTL 운영은 cleanup_older_than() 을 주기적으로 호출해 N일 이상 묵은 멤버 제거.
"""

from __future__ import annotations

import os
import time

import redis

from shared.config.redis_config import REDIS_KEY_SEEN_URLS
from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "crawler")
_logger = get_logger(__name__)

_DEFAULT_TTL_SECONDS = 7 * 86400  # 7일


class UrlDedupChecker:
    """fetch 직전 has_seen() 호출, 성공 enqueue 후 mark_seen() 호출 패턴."""

    def __init__(
        self,
        redis_client: redis.Redis,
        *,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
        key: str = REDIS_KEY_SEEN_URLS,
    ) -> None:
        self._redis = redis_client
        self._ttl = ttl_seconds
        self._key = key

    def has_seen(self, url: str, *, correlation_id: str = "") -> bool:
        """이미 본 URL 인지 — ZSCORE O(log N)."""
        if not url:
            return False
        score = self._redis.zscore(self._key, url)
        seen = score is not None
        if seen:
            _logger.debug(
                "URL 중복 감지: %s", url,
                extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
            )
        return seen

    def mark_seen(self, url: str, *, correlation_id: str = "") -> None:
        """현재 timestamp 를 score 로 기록 (재방문 시 score 갱신은 하지 않음)."""
        if not url:
            return
        # NX 옵션: 이미 있으면 score 변경 안 함.
        self._redis.zadd(self._key, {url: time.time()}, nx=True)
        _logger.debug(
            "URL 등록: %s", url,
            extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
        )

    def cleanup_older_than(self, *, age_seconds: int | None = None) -> int:
        """N초 이상 묵은 멤버를 ZREMRANGEBYSCORE 로 일괄 삭제. 반환값=삭제 수."""
        age = age_seconds if age_seconds is not None else self._ttl
        cutoff = time.time() - age
        removed = self._redis.zremrangebyscore(self._key, 0, cutoff)
        if removed:
            _logger.info(
                "URL dedup 청소: %d 건 (>%d 초 묵음)", removed, age,
                extra={"correlation_id": "", "service": _SERVICE_NAME},
            )
        return int(removed)

    def size(self) -> int:
        """현재 보관 중인 URL 수 — 모니터링용."""
        return int(self._redis.zcard(self._key))
