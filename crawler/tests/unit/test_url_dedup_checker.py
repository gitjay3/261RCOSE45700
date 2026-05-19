"""UrlDedupChecker: cross-run URL 중복 차단."""
from __future__ import annotations

import time
from unittest.mock import MagicMock

from crawler.src.preprocessor.url_dedup_checker import UrlDedupChecker


def _make() -> tuple[UrlDedupChecker, MagicMock]:
    mock = MagicMock()
    return UrlDedupChecker(mock), mock


class TestHasSeen:
    def test_unseen_url_returns_false(self):
        checker, mock = _make()
        mock.zscore.return_value = None
        assert checker.has_seen("https://example.com/p/1") is False
        mock.zscore.assert_called_once_with("posts:seen_urls", "https://example.com/p/1")

    def test_seen_url_returns_true(self):
        checker, mock = _make()
        mock.zscore.return_value = 1234567890.0
        assert checker.has_seen("https://example.com/p/1") is True

    def test_empty_url_returns_false_without_redis_call(self):
        checker, mock = _make()
        assert checker.has_seen("") is False
        mock.zscore.assert_not_called()


class TestMarkSeen:
    def test_mark_seen_uses_zadd_nx(self):
        checker, mock = _make()
        checker.mark_seen("https://example.com/p/1")
        # NX: 이미 있으면 score 변경 안 함 (재방문이 timestamp 갱신 안 하게).
        kwargs = mock.zadd.call_args.kwargs
        assert kwargs.get("nx") is True
        # 첫 인자: 키, 두번째: {url: timestamp} dict.
        args = mock.zadd.call_args.args
        assert args[0] == "posts:seen_urls"
        url_dict = args[1]
        assert "https://example.com/p/1" in url_dict
        # score 가 현재 timestamp 근처여야 한다.
        assert abs(url_dict["https://example.com/p/1"] - time.time()) < 5

    def test_mark_seen_empty_url_skips(self):
        checker, mock = _make()
        checker.mark_seen("")
        mock.zadd.assert_not_called()


class TestCleanup:
    def test_cleanup_removes_older_than_ttl(self):
        checker, mock = _make()
        mock.zremrangebyscore.return_value = 42
        removed = checker.cleanup_older_than(age_seconds=3600)
        assert removed == 42
        # cutoff = now - 3600 정도.
        args = mock.zremrangebyscore.call_args.args
        assert args[0] == "posts:seen_urls"
        assert args[1] == 0
        cutoff = args[2]
        assert abs(cutoff - (time.time() - 3600)) < 5

    def test_cleanup_uses_default_ttl(self):
        checker, mock = _make()
        mock.zremrangebyscore.return_value = 0
        checker.cleanup_older_than()
        # 기본 7d 사용.
        cutoff = mock.zremrangebyscore.call_args.args[2]
        expected = time.time() - 7 * 86400
        assert abs(cutoff - expected) < 5


class TestSize:
    def test_size_returns_zcard(self):
        checker, mock = _make()
        mock.zcard.return_value = 123
        assert checker.size() == 123
        mock.zcard.assert_called_once_with("posts:seen_urls")
