from __future__ import annotations

import threading

from detection.src.config.db_config import get_pool
from detection.src.config.redis_config import get_mq_client, get_rate_limit_client
from detection.src.consumer.queue_consumer import QueueConsumer
from detection.src.consumer.watchdog import Watchdog
from detection.src.pipeline.detection_pipeline import DetectionPipeline
from detection.src.pipeline.llm_classifier import LLMClassifier
from detection.src.pipeline.llm_client import LLMClient
from detection.src.pipeline.tier_router import TierRouter
from detection.src.rate_limit.cost_cap import CostCap
from detection.src.rate_limit.token_bucket import TokenBucket
from detection.src.repository.detection_repository import DetectionRepository
from detection.src.retry.retry_handler import RetryHandler
from shared.config.redis_config import REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY
from shared.structured_logger import get_logger

_logger = get_logger(__name__)


def main() -> None:
    mq_client = get_mq_client()
    rate_limit_client = get_rate_limit_client()
    db_pool = get_pool()

    llm_client = LLMClient()
    classify_bucket = TokenBucket(
        rate_limit_client, key=REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY,
    )
    cost_cap = CostCap(rate_limit_client)
    classifier = LLMClassifier(llm_client, classify_bucket)
    tier_router = TierRouter()
    retry_handler = RetryHandler(mq_client)
    repository = DetectionRepository(db_pool)
    pipeline = DetectionPipeline(
        classifier, tier_router, cost_cap, retry_handler, repository=repository,
    )

    watchdog = Watchdog(mq_client)
    consumer = QueueConsumer(mq_client, pipeline.process, watchdog=watchdog)

    watchdog_thread = threading.Thread(target=watchdog.run_forever, daemon=True)
    watchdog_thread.start()

    consumer.run_forever()


if __name__ == "__main__":
    main()
