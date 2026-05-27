from __future__ import annotations

import os

from detection.src.pipeline.llm_classifier import LLMClassifier
from detection.src.retry.retry_handler import RetryHandler
from shared.models.crawl_event import CrawlEvent
from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
_logger = get_logger(__name__)


class DetectionPipeline:
    def __init__(
        self,
        classifier: LLMClassifier,
        retry_handler: RetryHandler,
    ) -> None:
        self._classifier = classifier
        self._retry_handler = retry_handler

    def process(self, message: str) -> None:
        # TODO(Story 3-3): OpenAI 멀티모달 단일 호출 + Tier 라우팅으로 재작성.
        # 현재는 Story 3-2(VARCO Translation) cleanup 직후 interim 상태 — raw_text를
        # 그대로 classifier에 전달 (한국어는 정상 동작, 중국어는 Story 3-3에서 native 처리).
        event = CrawlEvent.from_json(message)

        classification = self._retry_handler.execute_with_retry(
            lambda: self._classifier.classify(event.raw_text),
            message=message,
            post_id=event.post_id,
            correlation_id=event.correlation_id,
        )
        _logger.info(
            "classification completed — is_illegal=%s type=%s confidence=%.3f",
            classification.is_illegal,
            classification.type,
            classification.confidence,
            extra={"correlation_id": event.correlation_id, "service": _SERVICE_NAME},
        )
        # TODO(Story 3.4): detection_repository.save(event, classification, self._classifier.model_version)
