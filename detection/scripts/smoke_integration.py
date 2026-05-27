"""Story 3-3 AC #10 실사 통합 smoke — Docker/Redis 없이 1건 처리 흐름을 증명한다.

production 코드 경로를 그대로 사용하되 Redis만 fakeredis로 in-memory 치환.
실제 OpenAI 호출(`OPENAI_API_KEY` 필요)이 수행되어 LLMClient → Classifier →
TierRouter → CostCap → 구조화 로그까지 1건이 실제로 흐른다.

Usage:
    python detection/scripts/smoke_integration.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
except ImportError as exc:
    sys.exit(f"[FAIL] python-dotenv 미설치: {exc}")

ENV_PATH = PROJECT_ROOT / "infra" / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

api_key = os.environ.get("OPENAI_API_KEY", "")
if not api_key or api_key.startswith("sk-REPLACE"):
    sys.exit("[FAIL] OPENAI_API_KEY가 placeholder. infra/.env 갱신 필요.")

import fakeredis

from detection.src.consumer.queue_consumer import QueueConsumer
from detection.src.pipeline.detection_pipeline import DetectionPipeline
from detection.src.pipeline.llm_classifier import LLMClassifier
from detection.src.pipeline.llm_client import LLMClient
from detection.src.pipeline.tier_router import TierRouter
from detection.src.rate_limit.cost_cap import CostCap
from detection.src.rate_limit.token_bucket import TokenBucket
from detection.src.retry.retry_handler import RetryHandler
from shared.config.redis_config import (
    REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY,
    REDIS_KEY_POSTS_DLQ,
    REDIS_KEY_POSTS_PROCESSING,
    REDIS_KEY_POSTS_QUEUE,
)
from shared.models.crawl_event import CrawlEvent


def main() -> int:
    print(f"[INFO] model={os.environ.get('LLM_MODEL', 'gpt-4o')}")
    print(f"[INFO] key=...{api_key[-4:]} (length={len(api_key)})")

    # production wiring을 그대로 — Redis만 fakeredis로 치환.
    mq = fakeredis.FakeRedis(decode_responses=True)
    rate_limit = fakeredis.FakeRedis(decode_responses=True)

    llm = LLMClient()
    bucket = TokenBucket(rate_limit, key=REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY, capacity=10, refill_per_sec=10)
    cost_cap = CostCap(rate_limit)
    classifier = LLMClassifier(llm, bucket)
    tier_router = TierRouter()
    retry_handler = RetryHandler(mq)
    pipeline = DetectionPipeline(classifier, tier_router, cost_cap, retry_handler)

    consumer = QueueConsumer(mq, pipeline.process)

    # 1건 적재 — 명확히 T1 카테고리(핵)로 분류되어야 할 본문.
    event = CrawlEvent(
        post_id="smoke_3_3_001",
        source_id="smoke",
        site_name="Story 3-3 smoke",
        raw_text="리니지M 월핵 최신 버전 팝니다. 탐지 안 됨. 텔레그램 @smoke_test_001",
        language="ko",
        detected_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        correlation_id="smoke-cid-001",
    )
    mq.lpush(REDIS_KEY_POSTS_QUEUE, event.to_json())
    print(f"[INFO] 큐 적재 완료: posts:queue len={mq.llen(REDIS_KEY_POSTS_QUEUE)}")

    # 1건 소비 — 실 OpenAI 호출 발생.
    handled = consumer.run_once()
    print(f"[INFO] run_once returned: {handled}")

    print(f"\n=== 상태 ===")
    print(f"  posts:queue       : {mq.llen(REDIS_KEY_POSTS_QUEUE)} (0이어야 함)")
    print(f"  posts:processing  : {mq.llen(REDIS_KEY_POSTS_PROCESSING)} (0이어야 함)")
    print(f"  posts:dlq         : {mq.llen(REDIS_KEY_POSTS_DLQ)} (0이어야 함)")
    print(f"  llm:rate_limit    : 사용됨 (TokenBucket acquire 호출)")

    if mq.llen(REDIS_KEY_POSTS_DLQ) > 0:
        print("[FAIL] DLQ로 이동됨")
        return 1
    if mq.llen(REDIS_KEY_POSTS_PROCESSING) > 0:
        print("[FAIL] processing 잔류")
        return 1
    print("\n[DONE] Story 3-3 실사 통합 smoke 통과 — 1건이 큐 → LLM → ACK까지 흘렀습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
