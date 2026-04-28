from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import httpx
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.async_configs import CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from shared.exceptions.base_exception import CrawlerException
from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "crawler")
_logger = get_logger(__name__)


@dataclass
class CrawlResult:
    url: str
    raw_markdown: str
    fit_markdown: str
    images: list[dict] = field(default_factory=list)
    downloaded_images: list[Path] = field(default_factory=list)

    @property
    def markdown(self) -> str:
        return self.fit_markdown or self.raw_markdown


class Crawl4AICrawler:
    """crawl4ai 기반 크롤러 — 봇 탐지 우회 + 텍스트/이미지 추출."""

    def __init__(self, headless: bool = True, output_dir: str = "output/images") -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._browser_config = BrowserConfig(
            headless=headless,
            verbose=False,
            enable_stealth=True,
            ignore_https_errors=True,
        )

        self._base_run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            magic=True,
            page_timeout=30_000,
            mean_delay=1.5,
            max_range=1.0,
            remove_consent_popups=True,
            excluded_tags=["nav", "footer", "header"],
            markdown_generator=DefaultMarkdownGenerator(
                content_filter=PruningContentFilter(
                    threshold=0.5,
                    threshold_type="fixed",
                )
            ),
        )

    async def fetch(
        self,
        url: str,
        *,
        correlation_id: str,
        download_images: bool = True,
        output_dir: Path | str | None = None,
        css_selector: str | None = None,
        image_filter: Callable[[dict], bool] | None = None,
    ) -> CrawlResult:
        _logger.info(
            "크롤링 시작: %s", url,
            extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
        )

        run_config = self._base_run_config
        if css_selector:
            run_config = CrawlerRunConfig(
                cache_mode=self._base_run_config.cache_mode,
                magic=self._base_run_config.magic,
                page_timeout=self._base_run_config.page_timeout,
                mean_delay=self._base_run_config.mean_delay,
                max_range=self._base_run_config.max_range,
                remove_consent_popups=self._base_run_config.remove_consent_popups,
                excluded_tags=self._base_run_config.excluded_tags,
                markdown_generator=self._base_run_config.markdown_generator,
                css_selector=css_selector,
            )

        async with AsyncWebCrawler(config=self._browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)

        if not result.success:
            _logger.error(
                "크롤링 실패: %s — %s", url, result.error_message,
                extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
            )
            raise CrawlerException(
                f"크롤링 실패: {result.error_message or 'unknown error'}",
                correlation_id=correlation_id,
            )

        md = result.markdown
        if hasattr(md, "raw_markdown"):
            raw_md = md.raw_markdown or ""
            fit_md = md.fit_markdown or ""
        else:
            raw_md = str(md) if md else ""
            fit_md = ""

        all_images = (result.media or {}).get("images") or []

        candidates = [img for img in all_images if img.get("src", "").startswith("http")]

        if image_filter is not None:
            candidates = [img for img in candidates if image_filter(img)]

        save_dir = Path(output_dir) if output_dir else self._output_dir
        save_dir.mkdir(parents=True, exist_ok=True)

        downloaded: list[Path] = []
        if download_images and candidates:
            downloaded = await self._download_images(
                [img["src"] for img in candidates],
                referer=url,
                save_dir=save_dir,
                correlation_id=correlation_id,
            )

        _logger.info(
            "크롤링 완료: %s (이미지 %d개)", url, len(candidates),
            extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
        )

        return CrawlResult(
            url=url,
            raw_markdown=raw_md,
            fit_markdown=fit_md,
            images=candidates,
            downloaded_images=downloaded,
        )

    async def _download_images(
        self,
        urls: list[str],
        *,
        referer: str = "",
        save_dir: Path | None = None,
        correlation_id: str = "",
    ) -> list[Path]:
        saved: list[Path] = []
        parsed = urlparse(referer)
        referer_origin = f"{parsed.scheme}://{parsed.netloc}" if referer else ""

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": referer_origin,
        }
        dest_dir = save_dir if save_dir else self._output_dir
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            for i, url in enumerate(urls):
                try:
                    ext = Path(url.split("?")[0]).suffix or ".jpg"
                    dest = dest_dir / f"img_{i:03d}{ext}"
                    resp = await client.get(url)
                    resp.raise_for_status()
                    dest.write_bytes(resp.content)
                    saved.append(dest)
                except Exception as exc:
                    _logger.warning(
                        "이미지 다운로드 실패: %s — %s", url, exc,
                        extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
                    )
        return saved
