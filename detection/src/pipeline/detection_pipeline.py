"""Detection Pipeline — Redis 메시지 1건 처리 흐름 (Story 3-3, 2026-05-27 PIVOT).

흐름:
  1. CrawlEvent 파싱
  2. CostCap.check_and_hold — 일일 비용 cap 도달 시 sleep
  3. LLMClassifier.classify (RetryHandler 감싸기) — OpenAI 멀티모달 단일 호출
  4. TierRouter.route — type → Tier 매핑
  5. CostCap.record — 누적 비용 갱신
  6. 구조화 로그 출력
  7. (Story 3-4) detection_repository.save — TODO

본 스토리에서는 RDS 저장 미수행. threshold 분기 미사용 (전수 저장 정책 — 부록 A-2).
"""

from __future__ import annotations

import os

from detection.src.pipeline.llm_classifier import LLMClassifier
from detection.src.pipeline.tier_router import TierRouter
from detection.src.rate_limit.cost_cap import CostCap
from detection.src.retry.retry_handler import RetryHandler
from shared.models.crawl_event import CrawlEvent
from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
_logger = get_logger(__name__)


class DetectionPipeline:
    def __init__(
        self,
        classifier: LLMClassifier,
        tier_router: TierRouter,
        cost_cap: CostCap,
        retry_handler: RetryHandler,
    ) -> None:
        self._classifier = classifier
        self._tier_router = tier_router
        self._cost_cap = cost_cap
        self._retry_handler = retry_handler

    def process(self, message: str) -> None:
        event = CrawlEvent.from_json(message)

        self._cost_cap.check_and_hold()

        images: list[str] = list(event.s3_image_paths or event.image_urls or [])

        response = self._retry_handler.execute_with_retry(
            lambda: self._classifier.classify(event.raw_text, images=images),
            message=message,
            post_id=event.post_id,
            correlation_id=event.correlation_id,
        )

        tier = self._tier_router.route(response.type)

        self._cost_cap.record(
            response.input_tokens,
            response.output_tokens,
            self._classifier.model_version.split(":", 2)[1] if ":" in self._classifier.model_version else "gpt-4o",
        )

        _logger.info(
            "classification — type=%s tier=%s conf=%.3f cost=$%.5f tokens(in/out)=%d/%d image_observed=%s",
            response.type, tier, response.confidence, response.cost_usd,
            response.input_tokens, response.output_tokens, response.image_observed,
            extra={
                "correlation_id": event.correlation_id,
                "service": _SERVICE_NAME,
                "post_id": event.post_id,
                "tier": tier,
                "model_version": self._classifier.model_version,
            },
        )
        # TODO(Story 3-4): detection_repository.save(event, response, tier, self._classifier.model_version)
