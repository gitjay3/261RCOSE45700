"""Story 3-4 실사 통합 smoke — 큐 → AI → DB까지 1건이 흐르는 것을 증명한다.

production 코드 경로 그대로 사용 (`detection/src/main.py`와 동일 wiring),
Redis만 fakeredis로 in-memory 치환. PostgreSQL은 실제 컨테이너(`infra/docker-compose.yml`
postgres) 사용. OpenAI는 실 호출.

Usage:
    docker compose -f infra/docker-compose.yml --env-file infra/.env up -d redis postgres
    python detection/scripts/smoke_integration_db.py
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
if not os.environ.get("DB_PASSWORD"):
    sys.exit("[FAIL] DB_PASSWORD 미설정. infra/.env 갱신 필요.")

import fakeredis

from detection.src.config.db_config import close_pool, get_pool
from detection.src.consumer.queue_consumer import QueueConsumer
from detection.src.pipeline.detection_pipeline import DetectionPipeline
from detection.src.pipeline.llm_classifier import LLMClassifier
from detection.src.pipeline.llm_client import LLMClient
from detection.src.pipeline.tier_router import TierRouter
from detection.src.rate_limit.cost_cap import CostCap
from detection.src.rate_limit.token_bucket import TokenBucket
from detection.src.repository.detection_repository import DetectionRepository
from detection.src.retry.retry_handler import RetryHandler
from shared.config.redis_config import (
    REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY,
    REDIS_KEY_POSTS_DLQ,
    REDIS_KEY_POSTS_PROCESSING,
    REDIS_KEY_POSTS_QUEUE,
)
from shared.models.crawl_event import CrawlEvent


def _run() -> int:
    print(f"[INFO] model={os.environ.get('LLM_MODEL', 'gpt-4o')}")
    print(f"[INFO] OpenAI key=...{api_key[-4:]} (length={len(api_key)})")
    print(f"[INFO] DB={os.environ.get('DB_HOST')}:{os.environ.get('DB_PORT', '5432')}/{os.environ.get('DB_NAME')}")

    # production wiring 그대로 — Redis만 fakeredis로.
    mq = fakeredis.FakeRedis(decode_responses=True)
    rate_limit = fakeredis.FakeRedis(decode_responses=True)
    db_pool = get_pool()

    llm = LLMClient()
    bucket = TokenBucket(rate_limit, key=REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY, capacity=10, refill_per_sec=10)
    cost_cap = CostCap(rate_limit)
    classifier = LLMClassifier(llm, bucket)
    tier_router = TierRouter()
    retry_handler = RetryHandler(mq)
    repository = DetectionRepository(db_pool)
    pipeline = DetectionPipeline(
        classifier, tier_router, cost_cap, retry_handler, repository=repository,
    )

    consumer = QueueConsumer(mq, pipeline.process)

    # 1건 적재 — T1 카테고리(핵)로 분류되어야 함.
    post_id = f"smoke_3_4_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    event = CrawlEvent(
        post_id=post_id,
        source_id="smoke_source",
        site_name="Story 3-4 smoke",
        raw_text="리니지M 월핵 최신 버전 팝니다. 탐지 안 됨. 텔레그램 @smoke_test_001",
        language="ko",
        detected_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        correlation_id=f"smoke-cid-{post_id}",
    )
    mq.lpush(REDIS_KEY_POSTS_QUEUE, event.to_json())
    print(f"[INFO] 큐 적재 완료: posts:queue len={mq.llen(REDIS_KEY_POSTS_QUEUE)}")

    # 1건 소비 — 실 OpenAI 호출 + 실 PG INSERT.
    handled = consumer.run_once()
    print(f"[INFO] run_once returned: {handled}")

    # DB 상태 확인.
    print(f"\n=== Redis ===")
    print(f"  posts:queue       : {mq.llen(REDIS_KEY_POSTS_QUEUE)} (0이어야 함)")
    print(f"  posts:processing  : {mq.llen(REDIS_KEY_POSTS_PROCESSING)} (0이어야 함)")
    print(f"  posts:dlq         : {mq.llen(REDIS_KEY_POSTS_DLQ)} (0이어야 함)")

    print(f"\n=== PostgreSQL ===")
    with db_pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT site_name FROM sources WHERE site_name=%s", (event.source_id,))
            source = cur.fetchone()
            print(f"  sources         : {source}")

            cur.execute("SELECT id, body, language FROM posts WHERE post_id_at_source=%s", (event.post_id,))
            post = cur.fetchone()
            print(f"  posts           : id={post[0]}, body={post[1][:40]}..., lang={post[2]}")

            cur.execute(
                """SELECT id, type, tier, confidence, is_illegal, cost_usd, model_version
                   FROM detections WHERE post_id=%s""",
                (post[0],),
            )
            det = cur.fetchone()
            print(f"  detections      : id={det[0]}")
            print(f"    - type        : {det[1]}")
            print(f"    - tier        : {det[2]}")
            print(f"    - confidence  : {float(det[3]):.3f}")
            print(f"    - is_illegal  : {det[4]}")
            print(f"    - cost_usd    : ${float(det[5]):.5f}")
            print(f"    - model       : {det[6]}")

    if mq.llen(REDIS_KEY_POSTS_DLQ) > 0:
        print("\n[FAIL] DLQ로 이동됨")
        return 1
    if mq.llen(REDIS_KEY_POSTS_PROCESSING) > 0:
        print("\n[FAIL] processing 잔류")
        return 1
    print("\n[DONE] Story 3-4 실사 통합 smoke 통과 — 1건이 큐 → OpenAI → PostgreSQL까지 흘렀습니다.")
    return 0


def main() -> int:
    try:
        return _run()
    finally:
        close_pool()  # finalizer 경고 회피


if __name__ == "__main__":
    sys.exit(main())
