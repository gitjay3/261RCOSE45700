from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from detection.src.consumer.queue_consumer import QueueConsumer
from detection.src.mocks.varco_mock import VarcoMock
from detection.src.pipeline.detection_pipeline import DetectionPipeline
from detection.src.pipeline.llm_classifier import LLMClassifier
from detection.src.pipeline.translate import Translator
from detection.src.retry.retry_handler import RetryHandler
from shared.config.redis_config import (
    REDIS_KEY_POSTS_DLQ,
    REDIS_KEY_POSTS_PROCESSING,
)
from shared.models.crawl_event import CrawlEvent


def _make_message(language: str, post_id: str = "tieba_001") -> tuple[str, CrawlEvent]:
    event = CrawlEvent(
        post_id=post_id,
        source_id="tieba_freestyle",
        site_name="贴吧 (자유게시판)",
        raw_text="매크로 판매합니다" if language == "ko" else "我要卖外挂",
        language=language,
        detected_at="2026-04-29T10:00:00Z",
        correlation_id=f"cid-{post_id}",
    )
    return event.to_json(), event


def _build_pipeline(varco: VarcoMock, mock_redis: MagicMock) -> DetectionPipeline:
    bucket = MagicMock()  # 토큰 버킷은 unit 테스트가 검증 — 통합에서는 no-op
    translator = Translator(varco, bucket)
    classifier = LLMClassifier(varco, bucket)
    retry_handler = RetryHandler(mock_redis)
    return DetectionPipeline(translator, classifier, retry_handler)


def test_clean_korean_post_full_pipeline() -> None:
    mock_redis = MagicMock()
    message, event = _make_message("ko")
    mock_redis.brpoplpush.return_value = message

    varco = VarcoMock(mode="clean")
    pipeline = _build_pipeline(varco, mock_redis)
    consumer = QueueConsumer(mock_redis, pipeline.process)

    result = consumer.run_once()

    assert result is True
    # 정상 처리 → LREM 호출(QueueConsumer ack) + DLQ 미호출
    mock_redis.lrem.assert_called_once_with(REDIS_KEY_POSTS_PROCESSING, 1, message)
    mock_redis.lpush.assert_not_called()


def test_illegal_chinese_post_full_pipeline() -> None:
    mock_redis = MagicMock()
    message, event = _make_message("zh-CN", post_id="tieba_002")
    mock_redis.brpoplpush.return_value = message

    varco = VarcoMock(mode="illegal")
    pipeline = _build_pipeline(varco, mock_redis)
    consumer = QueueConsumer(mock_redis, pipeline.process)

    result = consumer.run_once()

    assert result is True
    mock_redis.lrem.assert_called_once_with(REDIS_KEY_POSTS_PROCESSING, 1, message)
    mock_redis.lpush.assert_not_called()  # DLQ 미호출


def test_timeout_path_moves_to_dlq() -> None:
    mock_redis = MagicMock()
    message, event = _make_message("ko", post_id="tieba_003")
    mock_redis.brpoplpush.return_value = message

    varco = VarcoMock(mode="timeout")
    pipeline = _build_pipeline(varco, mock_redis)
    consumer = QueueConsumer(mock_redis, pipeline.process)

    with patch("detection.src.retry.retry_handler.time.sleep"):
        result = consumer.run_once()

    assert result is True
    # retry_handler가 DLQ LPUSH + processing LREM 수행
    mock_redis.lpush.assert_called_once_with(REDIS_KEY_POSTS_DLQ, message)
    # LREM은 retry_handler가 1회 호출 — QueueConsumer는 RetryExhaustedError catch하므로 추가 호출 없음
    lrem_calls = [
        c for c in mock_redis.lrem.call_args_list
        if c.args == (REDIS_KEY_POSTS_PROCESSING, 1, message)
    ]
    assert len(lrem_calls) == 1
    # retry_key + processing_time_key DELETE (consumer cleanup은 RetryExhaustedError로 미실행)
    assert mock_redis.delete.call_count == 2


def test_timeout_fixture_loaded_by_varco_mock() -> None:
    """epics.md AC #3 — mock_response_timeout.json fixture 로드 검증."""
    varco = VarcoMock(mode="timeout")
    assert varco._data.get("error") == "timeout"  # type: ignore[attr-defined]
    assert varco._data.get("latency_ms") == 30000  # type: ignore[attr-defined]
    with pytest.raises(TimeoutError, match="VARCO API timeout"):
        varco.classify("anything")
