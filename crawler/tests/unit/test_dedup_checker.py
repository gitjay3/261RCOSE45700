from __future__ import annotations

import hashlib
from unittest.mock import MagicMock

from crawler.src.preprocessor.dedup_checker import DedupChecker

_CID = "test-dedup-001"
_DEDUP_KEY = "posts:dedup"


def _make_checker(sismember_return: int = 0) -> tuple[DedupChecker, MagicMock]:
    mock_redis = MagicMock()
    mock_redis.sismember.return_value = sismember_return
    return DedupChecker(mock_redis), mock_redis


class TestDedupChecker:
    def test_new_post_not_duplicate(self):
        checker, mock_redis = _make_checker(sismember_return=0)
        assert checker.is_duplicate("새 게시글 텍스트", correlation_id=_CID) is False

    def test_duplicate_after_mark_seen(self):
        checker, mock_redis = _make_checker(sismember_return=0)
        checker.mark_seen("텍스트", correlation_id=_CID)
        # mark_seen 후 sismember가 1을 반환하도록 설정
        mock_redis.sismember.return_value = 1
        assert checker.is_duplicate("텍스트", correlation_id=_CID) is True

    def test_hash_consistency(self):
        checker, _ = _make_checker()
        h1 = checker._hash("동일한 텍스트")
        h2 = checker._hash("동일한 텍스트")
        assert h1 == h2

    def test_empty_text_not_duplicate(self):
        checker, mock_redis = _make_checker()
        assert checker.is_duplicate("", correlation_id=_CID) is False
        mock_redis.sismember.assert_not_called()

    def test_whitespace_only_not_duplicate(self):
        checker, mock_redis = _make_checker()
        assert checker.is_duplicate("   ", correlation_id=_CID) is False
        mock_redis.sismember.assert_not_called()

    def test_is_duplicate_calls_sismember(self):
        checker, mock_redis = _make_checker(sismember_return=0)
        text = "게시글 내용"
        expected_hash = hashlib.sha256(text.encode()).hexdigest()
        checker.is_duplicate(text, correlation_id=_CID)
        mock_redis.sismember.assert_called_once_with(_DEDUP_KEY, expected_hash)

    def test_mark_seen_calls_sadd(self):
        checker, mock_redis = _make_checker()
        text = "텍스트"
        expected_hash = hashlib.sha256(text.encode()).hexdigest()
        checker.mark_seen(text, correlation_id=_CID)
        mock_redis.sadd.assert_called_once_with(_DEDUP_KEY, expected_hash)

    def test_mark_seen_empty_text_no_sadd(self):
        checker, mock_redis = _make_checker()
        checker.mark_seen("", correlation_id=_CID)
        mock_redis.sadd.assert_not_called()

    def test_existing_post_is_duplicate(self):
        checker, mock_redis = _make_checker(sismember_return=1)
        assert checker.is_duplicate("기존 게시글", correlation_id=_CID) is True
