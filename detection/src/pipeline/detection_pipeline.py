from __future__ import annotations

import os

from detection.src.pipeline.llm_classifier import LLMClassifier
from detection.src.pipeline.translate import Translator
from detection.src.retry.retry_handler import RetryHandler
from shared.models.crawl_event import CrawlEvent
from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
_logger = get_logger(__name__)


class DetectionPipeline:
    def __init__(
        self,
        translator: Translator,
        classifier: LLMClassifier,
        retry_handler: RetryHandler,
    ) -> None:
        self._translator = translator
        self._classifier = classifier
        self._retry_handler = retry_handler

    def process(self, message: str) -> None:
        event = CrawlEvent.from_json(message)
        translated = self._translator.translate_event(event)
        _logger.info(
            "translation completed — len=%d",
            len(translated),
            extra={"correlation_id": event.correlation_id, "service": _SERVICE_NAME},
        )

        classification = self._retry_handler.execute_with_retry(
            lambda: self._classifier.classify(translated),
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
