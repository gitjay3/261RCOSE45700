from __future__ import annotations

from unittest.mock import MagicMock

import redis

from detection.src.consumer.queue_consumer import QueueConsumer
from detection.src.consumer.watchdog import Watchdog
from shared.config.redis_config import (
    REDIS_KEY_POSTS_CORRUPT,
    REDIS_KEY_POSTS_DLQ,
    REDIS_KEY_POSTS_PROCESSING,
    REDIS_KEY_POSTS_QUEUE,
)
from shared.models.crawl_event import CrawlEvent

_EVENT = CrawlEvent(
    post_id="inven_1234",
    source_id="inven_maple",
    site_name="인벤 (메이플스토리)",
    raw_text="매크로 판매합니다",
    language="ko",
    detected_at="2026-04-29T00:00:00Z",
    correlation_id="test-cid-001",
)
_MSG = _EVENT.to_json()


# ──────────────────────────────── QueueConsumer ──────────────────────────────


def test_consumer_acks_on_success():
    """정상 처리 → LREM 호출 (ack)"""
    mock_redis = MagicMock()
    mock_redis.brpoplpush.return_value = _MSG
    process_fn = MagicMock()

    consumer = QueueConsumer(mock_redis, process_fn)
    result = consumer.run_once()

    assert result is True
    process_fn.assert_called_once_with(_MSG)
    mock_redis.lrem.assert_called_once_with(REDIS_KEY_POSTS_PROCESSING, 1, _MSG)
    # 성공 처리 시 retry/processing_time 키 cleanup 검증
    mock_redis.delete.assert_any_call(f"posts:retry:{_EVENT.post_id}")
    mock_redis.delete.assert_any_call(f"posts:processing_time:{_EVENT.post_id}")


def test_consumer_does_not_ack_on_failure():
    """처리 실패 → LREM 미호출 (Watchdog이 복구)"""
    mock_redis = MagicMock()
    mock_redis.brpoplpush.return_value = _MSG

    def failing_process(msg):
        raise RuntimeError("처리 실패")

    consumer = QueueConsumer(mock_redis, failing_process)
    result = consumer.run_once()

    assert result is True
    mock_redis.lrem.assert_not_called()
    # 실패 시 retry/processing_time 키도 cleanup 안 함 (재시도 카운터 보존)
    mock_redis.delete.assert_not_called()


def test_consumer_returns_false_on_timeout():
    """brpoplpush timeout → False 반환"""
    mock_redis = MagicMock()
    mock_redis.brpoplpush.return_value = None

    consumer = QueueConsumer(mock_redis, MagicMock())
    result = consumer.run_once()

    assert result is False


def test_consumer_keeps_loop_on_redis_read_timeout():
    """Redis read timeout → 프로세스 종료 대신 False 반환"""
    mock_redis = MagicMock()
    mock_redis.brpoplpush.side_effect = redis.TimeoutError("Timeout reading from socket")
    process_fn = MagicMock()

    consumer = QueueConsumer(mock_redis, process_fn)
    result = consumer.run_once()

    assert result is False
    process_fn.assert_not_called()
    mock_redis.lrem.assert_not_called()


# ──────────────────────────────── Watchdog ───────────────────────────────────


def test_watchdog_reenqueues_stale_and_increments_retry():
    """stale 메시지 + retry < 3 → posts:queue 재투입 + retry INCR"""
    mock_redis = MagicMock()
    mock_redis.lrange.return_value = [_MSG]
    mock_redis.exists.return_value = 0   # 타임스탬프 키 만료 = stale
    mock_redis.get.return_value = "1"    # 현재 retry = 1 (< 3)

    watchdog = Watchdog(mock_redis)
    handled = watchdog.scan_once()

    assert handled == 1
    mock_redis.rpush.assert_called_once_with(REDIS_KEY_POSTS_QUEUE, _MSG)
    mock_redis.lrem.assert_called_once_with(REDIS_KEY_POSTS_PROCESSING, 1, _MSG)
    mock_redis.incr.assert_called_once()
    mock_redis.lpush.assert_not_called()  # DLQ 이동 없음


def test_watchdog_moves_to_dlq_at_max_retries():
    """retry == 3 → posts:dlq LPUSH + LREM"""
    mock_redis = MagicMock()
    mock_redis.lrange.return_value = [_MSG]
    mock_redis.exists.return_value = 0   # stale
    mock_redis.get.return_value = "3"    # retry == 3 → DLQ

    watchdog = Watchdog(mock_redis)
    handled = watchdog.scan_once()

    assert handled == 1
    mock_redis.lpush.assert_called_once_with(REDIS_KEY_POSTS_DLQ, _MSG)
    mock_redis.lrem.assert_called_once_with(REDIS_KEY_POSTS_PROCESSING, 1, _MSG)
    mock_redis.rpush.assert_not_called()  # 재투입 없음


def test_watchdog_skips_fresh_message():
    """타임스탬프 키 존재 (신선) → 아무 동작 없음"""
    mock_redis = MagicMock()
    mock_redis.lrange.return_value = [_MSG]
    mock_redis.exists.return_value = 1   # 키 존재 = 신선

    watchdog = Watchdog(mock_redis)
    handled = watchdog.scan_once()

    assert handled == 0
    mock_redis.rpush.assert_not_called()
    mock_redis.lpush.assert_not_called()


def test_retry_storm_full_lifecycle():
    """retry 0→1→2→3 → 4번째 stale 스캔에서 DLQ 격리. INCR 3회 + DLQ 시 retry 키 DELETE 검증."""
    mock_redis = MagicMock()
    mock_redis.exists.return_value = 0  # 항상 stale

    # 각 scan_once 호출마다 retry 카운트 증가 시뮬레이션 (0, 1, 2 → 재투입, 3 → DLQ)
    retry_counts = iter(["0", "1", "2", "3"])
    mock_redis.get.side_effect = lambda key: next(retry_counts)

    watchdog = Watchdog(mock_redis)

    # 1~3번: 재투입 (retry 0, 1, 2)
    for _ in range(3):
        mock_redis.lrange.return_value = [_MSG]
        watchdog.scan_once()

    # 라이프사이클 의도 강화: INCR이 3회 정확히 호출되었는지 (0→1, 1→2, 2→3)
    assert mock_redis.incr.call_count == 3

    # 4번: DLQ (retry == 3)
    mock_redis.lrange.return_value = [_MSG]
    handled = watchdog.scan_once()

    assert handled == 1
    mock_redis.lpush.assert_called_with(REDIS_KEY_POSTS_DLQ, _MSG)
    # DLQ 분기에서 retry 키가 정확히 1회 DELETE 되었는지 검증
    mock_redis.delete.assert_called_once_with(f"posts:retry:{_EVENT.post_id}")


def test_watchdog_quarantines_corrupt_message():
    """from_json 실패 메시지 → posts:corrupt LPUSH + posts:processing LREM"""
    mock_redis = MagicMock()
    corrupt_msg = "{not valid json"
    mock_redis.lrange.return_value = [corrupt_msg]

    watchdog = Watchdog(mock_redis)
    handled = watchdog.scan_once()

    assert handled == 1
    mock_redis.lpush.assert_called_once_with(REDIS_KEY_POSTS_CORRUPT, corrupt_msg)
    mock_redis.lrem.assert_called_once_with(REDIS_KEY_POSTS_PROCESSING, 1, corrupt_msg)
    # corrupt 분기는 retry/stale 검사하지 않음
    mock_redis.exists.assert_not_called()
    mock_redis.rpush.assert_not_called()
