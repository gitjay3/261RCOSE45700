from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from crawler.src.crawl4ai_crawler import Crawl4AICrawler, CrawlResult
from shared.exceptions.base_exception import CrawlerException


def _make_mock_result(
    success: bool = True,
    fit_md: str = "fit text",
    raw_md: str = "raw text",
    images: list[dict] | None = None,
    error_message: str = "크롤링 실패",
) -> MagicMock:
    r = MagicMock()
    r.success = success
    r.error_message = "" if success else error_message
    md = MagicMock()
    md.raw_markdown = raw_md
    md.fit_markdown = fit_md
    r.markdown = md
    r.media = {
        "images": images if images is not None else [
            {"src": "https://example.com/img.jpg", "score": 5, "alt": ""}
        ]
    }
    return r


def _patch_crawler(mock_result: MagicMock):
    """AsyncWebCrawler를 patch하는 컨텍스트 매니저 반환."""
    mock_instance = AsyncMock()
    mock_instance.arun = AsyncMock(return_value=mock_result)

    patcher = patch("crawler.src.crawl4ai_crawler.AsyncWebCrawler")
    MockCrawler = patcher.start()
    MockCrawler.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
    MockCrawler.return_value.__aexit__ = AsyncMock(return_value=None)
    return patcher, MockCrawler


class TestCrawl4AICrawlerFetch:
    _URL = "https://www.inven.co.kr/board/maple/2298/123"
    _CID = "test-cid-001"

    async def test_fetch_success_returns_crawl_result(self, tmp_path):
        mock_result = _make_mock_result()
        patcher, _ = _patch_crawler(mock_result)
        try:
            crawler = Crawl4AICrawler(output_dir=str(tmp_path))
            result = await crawler.fetch(self._URL, correlation_id=self._CID, download_images=False)
            assert result.fit_markdown == "fit text"
            assert result.raw_markdown == "raw text"
            assert len(result.images) == 1
            assert isinstance(result, CrawlResult)
        finally:
            patcher.stop()

    async def test_fetch_raises_crawler_exception_on_failure(self, tmp_path):
        mock_result = _make_mock_result(success=False)
        patcher, _ = _patch_crawler(mock_result)
        try:
            crawler = Crawl4AICrawler(output_dir=str(tmp_path))
            with pytest.raises(CrawlerException) as exc_info:
                await crawler.fetch(self._URL, correlation_id=self._CID, download_images=False)
            assert exc_info.value.correlation_id == self._CID
        finally:
            patcher.stop()

    async def test_fetch_falls_back_to_raw_markdown_when_fit_empty(self, tmp_path):
        mock_result = _make_mock_result(fit_md="", raw_md="raw fallback")
        patcher, _ = _patch_crawler(mock_result)
        try:
            crawler = Crawl4AICrawler(output_dir=str(tmp_path))
            result = await crawler.fetch(self._URL, correlation_id=self._CID, download_images=False)
            assert result.markdown == "raw fallback"
            assert result.fit_markdown == ""
        finally:
            patcher.stop()

    async def test_fetch_filters_images_by_score_threshold(self, tmp_path):
        images = [
            {"src": "https://example.com/high.jpg", "score": 5, "alt": ""},
            {"src": "https://example.com/low.jpg", "score": 1, "alt": ""},
            {"src": "https://example.com/exact.jpg", "score": 3, "alt": ""},
        ]
        mock_result = _make_mock_result(images=images)
        patcher, _ = _patch_crawler(mock_result)
        try:
            crawler = Crawl4AICrawler(output_dir=str(tmp_path))
            result = await crawler.fetch(self._URL, correlation_id=self._CID, download_images=False)
            srcs = [img["src"] for img in result.images]
            assert "https://example.com/high.jpg" in srcs
            assert "https://example.com/exact.jpg" in srcs
            assert "https://example.com/low.jpg" not in srcs
        finally:
            patcher.stop()

    async def test_fetch_applies_custom_image_filter(self, tmp_path):
        images = [
            {"src": "https://upload.inven.co.kr/img.jpg", "score": 5, "alt": ""},
            {"src": "https://other.com/img.jpg", "score": 5, "alt": ""},
        ]
        mock_result = _make_mock_result(images=images)
        patcher, _ = _patch_crawler(mock_result)
        try:
            crawler = Crawl4AICrawler(output_dir=str(tmp_path))
            result = await crawler.fetch(
                self._URL,
                correlation_id=self._CID,
                download_images=False,
                image_filter=lambda img: "inven" in img.get("src", ""),
            )
            assert len(result.images) == 1
            assert "inven" in result.images[0]["src"]
        finally:
            patcher.stop()

    async def test_fetch_skips_images_without_http_src(self, tmp_path):
        images = [
            {"src": "https://example.com/ok.jpg", "score": 5, "alt": ""},
            {"src": "", "score": 5, "alt": ""},
            {"score": 5, "alt": "no-src"},
        ]
        mock_result = _make_mock_result(images=images)
        patcher, _ = _patch_crawler(mock_result)
        try:
            crawler = Crawl4AICrawler(output_dir=str(tmp_path))
            result = await crawler.fetch(self._URL, correlation_id=self._CID, download_images=False)
            assert all(img.get("src", "").startswith("http") for img in result.images)
        finally:
            patcher.stop()

    async def test_fetch_with_css_selector_builds_separate_run_config(self, tmp_path):
        mock_result = _make_mock_result()
        patcher, MockCrawler = _patch_crawler(mock_result)
        try:
            crawler = Crawl4AICrawler(output_dir=str(tmp_path))
            await crawler.fetch(
                self._URL,
                correlation_id=self._CID,
                download_images=False,
                css_selector=".articleMain",
            )
            mock_instance = MockCrawler.return_value.__aenter__.return_value
            call_kwargs = mock_instance.arun.call_args
            run_config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
            assert run_config.css_selector == ".articleMain"
        finally:
            patcher.stop()

    async def test_fetch_no_download_returns_empty_downloaded_images(self, tmp_path):
        mock_result = _make_mock_result()
        patcher, _ = _patch_crawler(mock_result)
        try:
            crawler = Crawl4AICrawler(output_dir=str(tmp_path))
            result = await crawler.fetch(self._URL, correlation_id=self._CID, download_images=False)
            assert result.downloaded_images == []
        finally:
            patcher.stop()
