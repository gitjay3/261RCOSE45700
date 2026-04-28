from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from crawler.src.browser.stealth_browser import StealthBrowser
from crawler.src.proxy.proxy_broker import ProxyBroker
from crawler.src.proxy.proxy_provider import ProxyConfig, ProxyProvider
from crawler.src.sites.tailstar import TailstarSite


def _build_browser_chain(*, html: str, status: int = 200):
    """Reproduces Story 2.1 test_browser pattern so we can swap StealthBrowser
    cleanly in NFR15 verification tests.
    """
    page = AsyncMock()
    page.content.return_value = html

    response = MagicMock()
    response.status = status
    page.goto = AsyncMock(return_value=response)

    context = AsyncMock()
    context.new_page = AsyncMock(return_value=page)

    browser = AsyncMock()
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock(return_value=None)

    pw = MagicMock()
    pw.chromium = MagicMock()
    pw.chromium.launch = AsyncMock(return_value=browser)

    @asynccontextmanager
    async def fake_use_async(_pw_arg):
        yield pw

    stealth_instance = MagicMock()
    stealth_instance.use_async = fake_use_async
    return stealth_instance


_FIXTURE_HTML = (
    "<html>"
    "<head>"
    '<meta property="og:title" content="테스트 게시글">'
    '<meta property="og:url" content="https://tailstar.net/index.php?mid=board_main&document_srl=42">'
    "</head>"
    "<body>"
    '<div class="document_xe_content">'
    "<p>본문입니다.</p>"
    "</div>"
    "</body>"
    "</html>"
)


class _FakeProxyProvider:
    """Inline fake that satisfies ProxyProvider Protocol without inheriting it.

    Verifies @runtime_checkable duck-typing recognition (NFR15 contract).
    """

    def __init__(self, *, returns: ProxyConfig | None = None) -> None:
        self._returns = returns
        self.calls: list[str] = []

    def get_proxy(self, *, correlation_id: str) -> ProxyConfig | None:
        self.calls.append(correlation_id)
        return self._returns


def test_proxy_config_is_frozen_dataclass():
    cfg = ProxyConfig(server="http://x:8080", username="u", password="p")
    assert cfg.server == "http://x:8080"
    assert cfg.username == "u"
    assert cfg.password == "p"
    with pytest.raises(Exception):
        cfg.server = "http://y:8080"  # frozen


def test_fake_provider_is_recognized_as_proxy_provider():
    assert isinstance(_FakeProxyProvider(), ProxyProvider)


def test_proxy_broker_returns_none_when_env_unset(monkeypatch):
    monkeypatch.delenv("PROXY_BROKER_HOST", raising=False)
    monkeypatch.delenv("PROXY_BROKER_USER", raising=False)
    monkeypatch.delenv("PROXY_BROKER_PASS", raising=False)
    broker = ProxyBroker()
    assert broker.get_proxy(correlation_id="t-no-env") is None


def test_proxy_broker_returns_config_when_env_set(monkeypatch):
    monkeypatch.setenv("PROXY_BROKER_HOST", "http://proxy.test:8000")
    monkeypatch.setenv("PROXY_BROKER_USER", "u1")
    monkeypatch.setenv("PROXY_BROKER_PASS", "p1")
    cfg = ProxyBroker().get_proxy(correlation_id="t-env")
    assert cfg is not None
    assert cfg.server == "http://proxy.test:8000"
    assert cfg.username == "u1"
    assert cfg.password == "p1"


def test_proxy_broker_is_recognized_as_proxy_provider():
    assert isinstance(ProxyBroker(), ProxyProvider)


@pytest.mark.asyncio
async def test_tailstar_works_identically_with_swapped_proxy_provider(monkeypatch):
    """NFR15: ProxyProvider 교체 시 TailstarSite/StealthBrowser 동작 불변.

    동일 입력에 대해 (a) proxy_provider=None, (b) FakeProxyProvider(반환=None),
    (c) ProxyBroker(env unset)이 모두 동일한 ParseResult를 반환해야 한다.
    """
    monkeypatch.delenv("PROXY_BROKER_HOST", raising=False)
    stealth_inst = _build_browser_chain(html=_FIXTURE_HTML, status=200)
    monkeypatch.setattr(
        "crawler.src.browser.stealth_browser.Stealth",
        lambda: stealth_inst,
    )
    monkeypatch.setattr(
        "crawler.src.browser.stealth_browser.async_playwright",
        lambda: MagicMock(),
    )

    fake = _FakeProxyProvider(returns=None)
    broker = ProxyBroker()

    results = []
    for provider in (None, fake, broker):
        site = TailstarSite(browser=StealthBrowser(), proxy_provider=provider)
        result = await site.fetch_and_parse(
            "https://tailstar.net/index.php?mid=board_main&document_srl=42",
            correlation_id="t-swap",
        )
        results.append(result)

    assert results[0] == results[1] == results[2]
    assert results[0].title == "테스트 게시글"
    assert results[0].post_id == "42"
    assert fake.calls == ["t-swap"]


@pytest.mark.asyncio
async def test_tailstar_propagates_correlation_id_through_proxy_provider(monkeypatch):
    monkeypatch.delenv("PROXY_BROKER_HOST", raising=False)
    stealth_inst = _build_browser_chain(html=_FIXTURE_HTML, status=200)
    monkeypatch.setattr(
        "crawler.src.browser.stealth_browser.Stealth",
        lambda: stealth_inst,
    )
    monkeypatch.setattr(
        "crawler.src.browser.stealth_browser.async_playwright",
        lambda: MagicMock(),
    )

    fake = _FakeProxyProvider(
        returns=ProxyConfig(server="http://p:1", username=None, password=None)
    )
    site = TailstarSite(browser=StealthBrowser(), proxy_provider=fake)
    await site.fetch_and_parse(
        "https://tailstar.net/index.php?mid=board_main&document_srl=42",
        correlation_id="t-corr-id",
    )
    assert fake.calls == ["t-corr-id"]
