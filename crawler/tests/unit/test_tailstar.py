from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from crawler.src.browser.stealth_browser import BrowserError, StealthBrowser
from crawler.src.sites.base_site import RateLimitError
from crawler.src.sites.tailstar import TailstarSite


def _mock_browser_returning(html: str) -> AsyncMock:
    mock = AsyncMock(spec=StealthBrowser)
    mock.fetch_html = AsyncMock(return_value=html)
    return mock


def _mock_browser_raising(exc: BaseException) -> AsyncMock:
    mock = AsyncMock(spec=StealthBrowser)
    mock.fetch_html = AsyncMock(side_effect=exc)
    return mock


@pytest.mark.asyncio
async def test_fetch_and_parse_propagates_browser_error_on_5xx():
    """사이트 다운(HTTP 5xx) → StealthBrowser 가 BrowserError raise → 그대로 전파."""
    mock = _mock_browser_raising(
        BrowserError(
            "unexpected HTTP status 500 for https://tailstar.net/post/1",
            correlation_id="t-5xx",
        )
    )
    site = TailstarSite(browser=mock)
    with pytest.raises(BrowserError) as exc_info:
        await site.fetch_and_parse(
            "https://tailstar.net/index.php?mid=board_main&document_srl=1",
            correlation_id="t-5xx",
        )
    assert "500" in str(exc_info.value)
    assert exc_info.value.correlation_id == "t-5xx"


@pytest.mark.asyncio
async def test_fetch_and_parse_raises_rate_limit_error_on_block_marker():
    """사이트별 차단 페이지 마커 → RateLimitError. HTTP 429는 stealth_browser 에서 BrowserError로
    이미 처리되므로 본 테스트는 200 OK + 차단 본문 마커 케이스를 검증한다.
    """
    block_html = (
        "<html><head><title>접근 제한</title></head><body>"
        "<h1>잠시 후 다시 시도해 주세요</h1>"
        "</body></html>"
    )
    mock = _mock_browser_returning(block_html)
    site = TailstarSite(browser=mock)
    with pytest.raises(RateLimitError) as exc_info:
        await site.fetch_and_parse(
            "https://tailstar.net/index.php?mid=board_main&document_srl=1",
            correlation_id="t-429",
        )
    assert "rate-limit marker" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_and_parse_propagates_browser_error_on_timeout():
    """Playwright navigation timeout → StealthBrowser 가 BrowserError raise → 그대로 전파."""
    mock = _mock_browser_raising(
        BrowserError(
            "playwright navigation timed out after 30000ms for https://tailstar.net/post/1",
            correlation_id="t-timeout",
        )
    )
    site = TailstarSite(browser=mock)
    with pytest.raises(BrowserError) as exc_info:
        await site.fetch_and_parse(
            "https://tailstar.net/index.php?mid=board_main&document_srl=1",
            correlation_id="t-timeout",
        )
    assert "timed out" in str(exc_info.value)
    assert exc_info.value.correlation_id == "t-timeout"


@pytest.mark.asyncio
async def test_fetch_and_parse_propagates_browser_error_on_429_status():
    """HTTP 429 상태코드 → StealthBrowser가 BrowserError raise → 그대로 전파.

    설계 결정 (AC #5): HTTP 429 자체는 stealth_browser가 BrowserError("HTTP 429")로 변환.
    RateLimitError는 200 OK + 사이트별 차단 HTML 마커 케이스에서만 raise됨.
    """
    mock = _mock_browser_raising(
        BrowserError(
            "unexpected HTTP status 429 for https://tailstar.net/post/1",
            correlation_id="t-429-status",
        )
    )
    site = TailstarSite(browser=mock)
    with pytest.raises(BrowserError) as exc_info:
        await site.fetch_and_parse(
            "https://tailstar.net/index.php?mid=board_main&document_srl=1",
            correlation_id="t-429-status",
        )
    assert "429" in str(exc_info.value)
    assert exc_info.value.correlation_id == "t-429-status"


@pytest.mark.asyncio
async def test_fetch_and_parse_returns_parse_result_on_happy_path():
    """정상 응답 → ParseResult. browser fetch + site parse 통합 동작."""
    happy_html = (
        '<html><head>'
        '<meta property="og:title" content="정상 게시글">'
        '<meta property="og:url" content="https://tailstar.net/index.php?mid=b&document_srl=42">'
        '</head><body>'
        '<div class="document_xe_content"><p>본문 텍스트</p></div>'
        '</body></html>'
    )
    mock = _mock_browser_returning(happy_html)
    site = TailstarSite(browser=mock)
    result = await site.fetch_and_parse(
        "https://tailstar.net/index.php?mid=b&document_srl=42",
        correlation_id="t-ok",
    )
    assert result.title == "정상 게시글"
    assert result.post_id == "42"
    assert "본문 텍스트" in result.body_text
    mock.fetch_html.assert_awaited_once_with(
        "https://tailstar.net/index.php?mid=b&document_srl=42",
        correlation_id="t-ok",
    )
