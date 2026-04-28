from __future__ import annotations

import os
from collections.abc import Callable, Coroutine
from typing import Any

import redis.asyncio as aioredis

from shared.correlation_id import generate
from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "crawler")
_logger = get_logger(__name__)
_CHANNEL = "crawl:trigger"


class TriggerListener:
    """Redis pub/sub crawl:trigger 채널 구독 → 수동 크롤링 즉시 실행."""

    def __init__(
        self,
        redis_url: str,
        pipeline_fn: Callable[[], Coroutine[Any, Any, Any]],
    ) -> None:
        self._redis_url = redis_url
        self._run_pipeline = pipeline_fn

    async def listen(self) -> None:
        client = aioredis.from_url(self._redis_url, db=0, decode_responses=True)
        async with client.pubsub() as pubsub:
            await pubsub.subscribe(_CHANNEL)
            _logger.info(
                "crawl:trigger 채널 구독 시작",
                extra={"correlation_id": "", "service": _SERVICE_NAME},
            )
            async for message in pubsub.listen():
                if message["type"] == "message":
                    cid = generate()
                    _logger.info(
                        "수동 트리거 수신 — 즉시 크롤링 시작",
                        extra={"correlation_id": cid, "service": _SERVICE_NAME},
                    )
                    await self._run_pipeline()
