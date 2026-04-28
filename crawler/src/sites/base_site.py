from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Final

from crawler.src.browser.stealth_browser import StealthBrowser
from crawler.src.proxy.proxy_provider import ProxyProvider
from shared.exceptions.base_exception import CrawlerException
from shared.structured_logger import get_logger

_logger = get_logger(__name__)
_SERVICE_NAME: Final[str] = os.environ.get("SERVICE_NAME", "crawler")


class ParseError(CrawlerException):
    """Raised when site-specific HTML parsing fails (architecture P10)."""


class RateLimitError(CrawlerException):
    """Raised when a site responds with a rate-limit / block page marker."""


@dataclass(frozen=True)
class PostListItem:
    post_id: str
    url: str
    title: str


@dataclass(frozen=True)
class ParseResult:
    post_id: str
    title: str
    body_text: str
    source_url: str
    image_urls: list[str] = field(default_factory=list)
    posted_at: str | None = None


class BaseSite(ABC):
    def __init__(
        self,
        *,
        browser: StealthBrowser | None = None,
        proxy_provider: ProxyProvider | None = None,
    ) -> None:
        self._browser = browser if browser is not None else StealthBrowser()
        self._proxy_provider = proxy_provider

    @abstractmethod
    def parse_list(self, html: str) -> list[PostListItem]:
        """Parse a board listing page into PostListItem entries.

        Raises ParseError if the listing structure cannot be recognized.
        """

    @abstractmethod
    def parse(self, html: str) -> ParseResult:
        """Parse a post detail page into a ParseResult.

        Must NEVER return None for failure (architecture P10) — raise ParseError or
        RateLimitError instead.
        """

    async def fetch_and_parse(
        self,
        url: str,
        *,
        correlation_id: str,
    ) -> ParseResult:
        extra = {"correlation_id": correlation_id, "service": _SERVICE_NAME}
        if self._proxy_provider is not None:
            proxy = self._proxy_provider.get_proxy(correlation_id=correlation_id)
            if proxy is not None:
                # TODO Story 2.5: pass proxy to StealthBrowser.new_context(proxy=...)
                _logger.debug(
                    f"fetch_and_parse.proxy_resolved_deferred url={url} server={proxy.server}",
                    extra=extra,
                )

        _logger.info(f"fetch_and_parse.start url={url}", extra=extra)
        html = await self._browser.fetch_html(url, correlation_id=correlation_id)
        try:
            result = self.parse(html)
        except CrawlerException as exc:
            if exc.correlation_id is None:
                exc.correlation_id = correlation_id
            raise
        _logger.info(
            f"fetch_and_parse.ok url={url} post_id={result.post_id} "
            f"images={len(result.image_urls)}",
            extra=extra,
        )
        return result
