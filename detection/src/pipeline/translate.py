from __future__ import annotations

import os
import time

from detection.src.mocks.varco_mock import RateLimitError
from detection.src.rate_limit.token_bucket import TokenBucket
from shared.interfaces.varco import VarcoInterface
from shared.models.crawl_event import CrawlEvent
from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
_TRANSLATABLE_LANGS = frozenset({"zh-CN", "zh-TW"})
_logger = get_logger(__name__)


class Translator:
    def __init__(
        self,
        varco: VarcoInterface,
        token_bucket: TokenBucket,
    ) -> None:
        self._varco = varco
        self._bucket = token_bucket

    def translate_event(self, event: CrawlEvent) -> str:
        """language가 zh-CN/zh-TW이면 VARCO 호출, 그 외는 raw_text 그대로 반환."""
        if event.language not in _TRANSLATABLE_LANGS:
            _logger.info(
                "translation skipped — language=%s",
                event.language,
                extra={"correlation_id": event.correlation_id, "service": _SERVICE_NAME},
            )
            return event.raw_text

        self._bucket.acquire()
        try:
            return self._varco.translate(event.raw_text)
        except RateLimitError as exc:
            _logger.warning(
                "VARCO rate limit — retry_after=%ds",
                exc.retry_after,
                extra={"correlation_id": event.correlation_id, "service": _SERVICE_NAME},
            )
            time.sleep(exc.retry_after)
            return self._varco.translate(event.raw_text)
