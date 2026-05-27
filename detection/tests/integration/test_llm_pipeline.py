"""LLMPipeline 통합 — LLMMock 기반, 외부 OpenAI 호출 0건 (Story 3-3)."""

from __future__ import annotations

from unittest.mock import MagicMock

import fakeredis
import pytest

from detection.src.consumer.queue_consumer import QueueConsumer
from detection.src.mocks.llm_mock import LLMMock
from detection.src.pipeline.detection_pipeline import DetectionPipeline
from detection.src.pipeline.llm_classifier import LLMClassifier
from detection.src.pipeline.tier_router import TierRouter
from detection.src.rate_limit.cost_cap import CostCap
from detection.src.retry.retry_handler import RetryExhaustedError, RetryHandler
from shared.config.redis_config import (
    REDIS_KEY_POSTS_DLQ,
    REDIS_KEY_POSTS_PROCESSING,
)
from shared.models.crawl_event import CrawlEvent


def _build_event(language: str = "ko", raw_text: str = "정상 게시글") -> CrawlEvent:
    return CrawlEvent(
        post_id=f"test_{language}_001",
        source_id="ptt_lineage",
        site_name="PTT Lineage",
        raw_text=raw_text,
        language=language,
        detected_at="2026-05-27T00:00:00Z",
        correlation_id=f"cid-{language}-001",
    )


@pytest.fixture(autouse=True)
def _env_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_DAILY_COST_CAP_USD", "0")  # cap 비활성 — sleep 회피
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("RETRY_BACKOFF_BASE_SEC", "0")  # 테스트 빠르게


@pytest.fixture
def mq_redis() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def rate_limit_redis() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


def _build_pipeline(
    llm_mode: str, mq_redis, rate_limit_redis, repository=None,
) -> tuple[DetectionPipeline, RetryHandler]:
    from detection.src.rate_limit.token_bucket import TokenBucket
    llm = LLMMock(mode=llm_mode)
    bucket = TokenBucket(rate_limit_redis, capacity=100, refill_per_sec=100)
    cost_cap = CostCap(rate_limit_redis)
    classifier = LLMClassifier(llm, bucket, model_version="openai:gpt-4o:2024-08-06")
    tier_router = TierRouter()
    retry_handler = RetryHandler(mq_redis)
    pipeline = DetectionPipeline(classifier, tier_router, cost_cap, retry_handler, repository=repository)
    return pipeline, retry_handler


def test_clean_path_acks_without_dlq(mq_redis, rate_limit_redis) -> None:
    event = _build_event()
    message = event.to_json()
    # 사전 적재 — 실제 큐 상태로 LREM 효과 검증.
    mq_redis.lpush(REDIS_KEY_POSTS_PROCESSING, message)

    pipeline, _ = _build_pipeline("clean", mq_redis, rate_limit_redis)

    # QueueConsumer를 직접 사용 — brpoplpush만 stub, 나머지는 real fakeredis로.
    mock_redis = MagicMock(spec=mq_redis)
    mock_redis.brpoplpush.return_value = message
    mock_redis.lrem.side_effect = lambda *args, **kwargs: mq_redis.lrem(*args, **kwargs)
    mock_redis.delete.side_effect = lambda *args, **kwargs: mq_redis.delete(*args, **kwargs)
    consumer = QueueConsumer(mock_redis, pipeline.process)

    result = consumer.run_once()

    assert result is True
    # 성공 ACK 검증 — LREM이 processing에서 메시지 제거.
    mock_redis.lrem.assert_any_call(REDIS_KEY_POSTS_PROCESSING, 1, message)
    assert mq_redis.llen(REDIS_KEY_POSTS_PROCESSING) == 0
    # DLQ로 가지 않았어야.
    assert mq_redis.llen(REDIS_KEY_POSTS_DLQ) == 0


def test_timeout_path_routes_to_dlq(mq_redis, rate_limit_redis) -> None:
    event = _build_event(language="zh-CN", raw_text="月外挂最新版本上传。免费")
    message = event.to_json()
    mq_redis.lpush(REDIS_KEY_POSTS_PROCESSING, message)

    pipeline, _ = _build_pipeline("timeout", mq_redis, rate_limit_redis)

    with pytest.raises(RetryExhaustedError):
        pipeline.process(message)

    # DLQ에 메시지가 LPUSH되었고 processing에서 LREM되었는지.
    assert mq_redis.llen(REDIS_KEY_POSTS_DLQ) == 1
    assert mq_redis.lrange(REDIS_KEY_POSTS_DLQ, 0, -1) == [message]
    assert mq_redis.llen(REDIS_KEY_POSTS_PROCESSING) == 0


def test_pipeline_calls_repository_save_on_success(mq_redis, rate_limit_redis) -> None:
    """repository 주입 시 분류 후 save가 정확한 인자로 호출되는지 (Story 3-4)."""
    event = _build_event()
    message = event.to_json()

    mock_repo = MagicMock()
    mock_repo.save.return_value = 42
    pipeline, _ = _build_pipeline("clean", mq_redis, rate_limit_redis, repository=mock_repo)

    pipeline.process(message)

    mock_repo.save.assert_called_once()
    kwargs = mock_repo.save.call_args.kwargs
    assert kwargs["event"].post_id == event.post_id
    assert kwargs["tier"] == "T4"  # clean mock은 type=기타 → T4
    assert kwargs["model_version"] == "openai:gpt-4o:2024-08-06"
    assert kwargs["response"].type == "기타"
