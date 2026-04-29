from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from detection.src.mocks.varco_mock import RateLimitError
from detection.src.retry.retry_handler import (
    RetryExhaustedError,
    RetryHandler,
)
from shared.config.redis_config import (
    REDIS_KEY_POSTS_DLQ,
    REDIS_KEY_POSTS_PROCESSING,
)

_MESSAGE = '{"post_id":"tieba_001","correlation_id":"cid-001"}'
_POST_ID = "tieba_001"
_CID = "cid-001"


def test_first_attempt_success() -> None:
    mock_redis = MagicMock()
    handler = RetryHandler(mock_redis)
    func = MagicMock(return_value="ok")

    result = handler.execute_with_retry(
        func, message=_MESSAGE, post_id=_POST_ID, correlation_id=_CID,
    )

    assert result == "ok"
    assert func.call_count == 1
    mock_redis.lpush.assert_not_called()


def test_second_attempt_success_with_backoff() -> None:
    mock_redis = MagicMock()
    handler = RetryHandler(mock_redis)
    func = MagicMock(side_effect=[TimeoutError("first fail"), "ok"])

    with patch("detection.src.retry.retry_handler.time.sleep") as mock_sleep:
        result = handler.execute_with_retry(
            func, message=_MESSAGE, post_id=_POST_ID, correlation_id=_CID,
        )

    assert result == "ok"
    assert func.call_count == 2
    mock_sleep.assert_called_once_with(1.0)  # 1 * 2^0
    mock_redis.lpush.assert_not_called()


def test_retry_exhausted_moves_to_dlq() -> None:
    mock_redis = MagicMock()
    handler = RetryHandler(mock_redis)
    func = MagicMock(side_effect=TimeoutError("persistent"))

    with patch("detection.src.retry.retry_handler.time.sleep") as mock_sleep:
        with pytest.raises(RetryExhaustedError) as exc_info:
            handler.execute_with_retry(
                func, message=_MESSAGE, post_id=_POST_ID, correlation_id=_CID,
            )

    assert func.call_count == 4  # 원본 1 + 재시도 3
    assert mock_sleep.call_count == 3  # backoff 1s, 2s, 4s
    mock_sleep.assert_has_calls([call(1.0), call(2.0), call(4.0)])
    mock_redis.lpush.assert_called_once_with(REDIS_KEY_POSTS_DLQ, _MESSAGE)
    mock_redis.lrem.assert_called_once_with(REDIS_KEY_POSTS_PROCESSING, 1, _MESSAGE)
    # retry_key + processing_time_key 둘 다 DELETE
    assert mock_redis.delete.call_count == 2
    assert exc_info.value.post_id == _POST_ID
    assert exc_info.value.attempts == 4
    assert isinstance(exc_info.value.last_error, TimeoutError)


def test_non_retryable_value_error_propagates_immediately() -> None:
    mock_redis = MagicMock()
    handler = RetryHandler(mock_redis)
    func = MagicMock(side_effect=ValueError("bad schema"))

    with patch("detection.src.retry.retry_handler.time.sleep") as mock_sleep:
        with pytest.raises(ValueError, match="bad schema"):
            handler.execute_with_retry(
                func, message=_MESSAGE, post_id=_POST_ID, correlation_id=_CID,
            )

    assert func.call_count == 1
    mock_sleep.assert_not_called()
    mock_redis.lpush.assert_not_called()


def test_rate_limit_error_propagates_immediately() -> None:
    mock_redis = MagicMock()
    handler = RetryHandler(mock_redis)
    func = MagicMock(side_effect=RateLimitError(retry_after=30))

    with patch("detection.src.retry.retry_handler.time.sleep") as mock_sleep:
        with pytest.raises(RateLimitError):
            handler.execute_with_retry(
                func, message=_MESSAGE, post_id=_POST_ID, correlation_id=_CID,
            )

    assert func.call_count == 1
    mock_sleep.assert_not_called()
    mock_redis.lpush.assert_not_called()
