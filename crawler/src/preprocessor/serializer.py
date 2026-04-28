from __future__ import annotations

from datetime import datetime, timezone

from shared.models.crawl_event import CrawlEvent

from crawler.src.crawl4ai_crawler import CrawlResult
from crawler.src.sites.registry import SiteConfig


def to_crawl_event(
    result: CrawlResult,
    *,
    site_id: str,
    site: SiteConfig,
    url: str,
    language: str,
    correlation_id: str,
) -> CrawlEvent:
    post_id = site.post_id_extractor(url)
    return CrawlEvent(
        post_id=post_id,
        source_id=site_id,
        site_name=site.name,
        raw_text=result.markdown,
        image_urls=[img["src"] for img in result.images],
        language=language,
        detected_at=datetime.now(timezone.utc).isoformat(),
        correlation_id=correlation_id,
    )
