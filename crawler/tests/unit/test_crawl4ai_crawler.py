from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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

    async def test_fetch_collects_all_http_images_regardless_of_score(self, tmp_path):
        images = [
            {"src": "https://example.com/high.jpg", "score": 5, "alt": ""},
            {"src": "https://example.com/low.jpg", "score": 1, "alt": ""},
            {"src": "https://example.com/no_score.jpg", "alt": ""},
        ]
        mock_result = _make_mock_result(images=images)
        patcher, _ = _patch_crawler(mock_result)
        try:
            crawler = Crawl4AICrawler(output_dir=str(tmp_path))
            result = await crawler.fetch(self._URL, correlation_id=self._CID, download_images=False)
            srcs = [img["src"] for img in result.images]
            assert "https://example.com/high.jpg" in srcs
            assert "https://example.com/low.jpg" in srcs
            assert "https://example.com/no_score.jpg" in srcs
        finally:
            patcher.stop()

    async def test_fetch_media_none_returns_empty_images(self, tmp_path):
        mock_result = _make_mock_result()
        mock_result.media = None
        patcher, _ = _patch_crawler(mock_result)
        try:
            crawler = Crawl4AICrawler(output_dir=str(tmp_path))
            result = await crawler.fetch(self._URL, correlation_id=self._CID, download_images=False)
            assert result.images == []
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


class TestCrawl4AICrawlerSiteOptions:
    """PTT/Dcard/Tieba 차단 해제용 사이트별 fetch 옵션 전파 검증."""

    _URL = "https://www.ptt.cc/bbs/C_Chat/M.123.html"
    _CID = "test-opts-001"

    async def test_fetch_passes_cookies_to_arun(self, tmp_path):
        mock_result = _make_mock_result()
        patcher, MockCrawler = _patch_crawler(mock_result)
        try:
            crawler = Crawl4AICrawler(output_dir=str(tmp_path))
            cookies = [{"name": "over18", "value": "1", "domain": ".ptt.cc", "path": "/"}]
            await crawler.fetch(
                self._URL,
                correlation_id=self._CID,
                download_images=False,
                cookies=cookies,
            )
            mock_instance = MockCrawler.return_value.__aenter__.return_value
            assert mock_instance.arun.call_args.kwargs.get("cookies") == cookies
        finally:
            patcher.stop()

    async def test_fetch_omits_cookies_kwarg_when_none(self, tmp_path):
        mock_result = _make_mock_result()
        patcher, MockCrawler = _patch_crawler(mock_result)
        try:
            crawler = Crawl4AICrawler(output_dir=str(tmp_path))
            await crawler.fetch(self._URL, correlation_id=self._CID, download_images=False)
            mock_instance = MockCrawler.return_value.__aenter__.return_value
            # cookies 미지정 시 arun(cookies=...) 키 자체가 없어야 한다 (crawl4ai 기본 동작 위임).
            assert "cookies" not in mock_instance.arun.call_args.kwargs
        finally:
            patcher.stop()

    async def test_fetch_passes_wait_for_into_run_config(self, tmp_path):
        mock_result = _make_mock_result()
        patcher, MockCrawler = _patch_crawler(mock_result)
        try:
            crawler = Crawl4AICrawler(output_dir=str(tmp_path))
            await crawler.fetch(
                self._URL,
                correlation_id=self._CID,
                download_images=False,
                wait_for="css:article",
            )
            mock_instance = MockCrawler.return_value.__aenter__.return_value
            run_config = mock_instance.arun.call_args.kwargs["config"]
            assert run_config.wait_for == "css:article"
        finally:
            patcher.stop()

    async def test_fetch_overrides_page_timeout(self, tmp_path):
        mock_result = _make_mock_result()
        patcher, MockCrawler = _patch_crawler(mock_result)
        try:
            crawler = Crawl4AICrawler(output_dir=str(tmp_path))
            await crawler.fetch(
                self._URL,
                correlation_id=self._CID,
                download_images=False,
                page_timeout=45_000,
            )
            mock_instance = MockCrawler.return_value.__aenter__.return_value
            run_config = mock_instance.arun.call_args.kwargs["config"]
            assert run_config.page_timeout == 45_000
        finally:
            patcher.stop()

    async def test_fetch_proxy_builds_per_call_browser_config(self, tmp_path):
        mock_result = _make_mock_result()
        patcher, MockCrawler = _patch_crawler(mock_result)
        try:
            crawler = Crawl4AICrawler(output_dir=str(tmp_path))
            proxy = {"server": "http://proxy.example.com:8080"}
            await crawler.fetch(
                self._URL,
                correlation_id=self._CID,
                download_images=False,
                proxy=proxy,
            )
            # AsyncWebCrawler 가 per-call 으로 다시 호출되며 새 BrowserConfig 가 주입됐는지.
            # crawl4ai 는 dict 를 ProxyConfig 객체로 감싸므로 server 속성을 통해 비교.
            ctor_kwargs = MockCrawler.call_args.kwargs
            browser_cfg = ctor_kwargs.get("config")
            assert browser_cfg is not None
            proxy_cfg = getattr(browser_cfg, "proxy_config", None)
            assert proxy_cfg is not None
            assert getattr(proxy_cfg, "server", None) == proxy["server"]
        finally:
            patcher.stop()
