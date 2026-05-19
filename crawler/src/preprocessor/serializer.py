from __future__ import annotations

from datetime import datetime, timezone

from crawler.src.crawl4ai_crawler import CrawlResult
from crawler.src.sites.registry import SiteConfig
from shared.models.crawl_event import CrawlEvent


def to_crawl_event(
    result: CrawlResult,
    *,
    site_id: str,
    site: SiteConfig,
    url: str,
    language: str,
    correlation_id: str,
    s3_text_path: str = "",
    s3_image_paths: list[str] | None = None,
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
        s3_text_path=s3_text_path,
        s3_image_paths=s3_image_paths or [],
    )
