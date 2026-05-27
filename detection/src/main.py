from __future__ import annotations

import threading

from detection.src.config.redis_config import get_mq_client, get_rate_limit_client
from detection.src.consumer.queue_consumer import QueueConsumer
from detection.src.consumer.watchdog import Watchdog
from detection.src.pipeline.detection_pipeline import DetectionPipeline
from detection.src.pipeline.llm_classifier import LLMClassifier
from detection.src.pipeline.varco_client import VarcoHttpClient
from detection.src.rate_limit.token_bucket import TokenBucket
from detection.src.retry.retry_handler import RetryHandler
from shared.config.redis_config import REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY
from shared.structured_logger import get_logger

_logger = get_logger(__name__)


def main() -> None:
    # NOTE(Story 3-2 cleanup, 2026-05-27): VARCO Translation 단계 제거. Story 3-3에서
    # OpenAI 멀티모달 LLM 단일 호출로 VarcoHttpClient + LLMClassifier가 전면 대체될 예정.
    mq_client = get_mq_client()
    rate_limit_client = get_rate_limit_client()

    varco = VarcoHttpClient()
    classify_bucket = TokenBucket(
        rate_limit_client, key=REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY,
    )
    classifier = LLMClassifier(varco, classify_bucket)
    retry_handler = RetryHandler(mq_client)
    pipeline = DetectionPipeline(classifier, retry_handler)

    watchdog = Watchdog(mq_client)
    consumer = QueueConsumer(mq_client, pipeline.process, watchdog=watchdog)

    watchdog_thread = threading.Thread(target=watchdog.run_forever, daemon=True)
    watchdog_thread.start()

    consumer.run_forever()


if __name__ == "__main__":
    main()
