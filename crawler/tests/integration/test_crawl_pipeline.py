"""CrawlPipeline 통합 테스트.

외부 Redis / S3 / 브라우저 호출 없이 mock 으로 파이프라인 전체 흐름을 검증한다.
"""
from __future__ import annotations

import contextlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from crawler.src.crawl4ai_crawler import CrawlResult
from crawler.src.preprocessor.dedup_checker import DedupChecker
from crawler.src.queue.redis_publisher import RedisPublisher
from crawler.src.scheduler.crawl_scheduler import CrawlPipeline
from crawler.src.sites.registry import SITES
from crawler.src.storage import StorageResult
from shared.models.crawl_event import CrawlEvent

_KEYWORD_TEXT = "매크로 판매합니다 텔레그램 문의"
_TEST_URL = "https://www.inven.co.kr/board/maple/2298/123"
_TEST_URL2 = "https://www.inven.co.kr/board/maple/2298/456"


def _make_crawl_result(text: str = _KEYWORD_TEXT) -> CrawlResult:
    return CrawlResult(
        url=_TEST_URL,
        raw_markdown=text,
        fit_markdown=text,
        images=[],
        downloaded_images=[],
    )


@contextlib.contextmanager
def _isolated_sites():
    """단일 사이트(inven_maple)만 활성화한 상태로 패치 — site fanout 으로 인한 lpush 다중 호출 방지."""
    inven = SITES["inven_maple"]
    with patch(
        "crawler.src.scheduler.crawl_scheduler.get_enabled_sites",
        return_value={"inven_maple": inven},
    ):
        yield


def _make_pipeline(
    *,
    crawl_result: CrawlResult | None = None,
    is_duplicate: bool = False,
    s3_text_path: str = "",
) -> tuple[CrawlPipeline, MagicMock, MagicMock]:
    if crawl_result is None:
        crawl_result = _make_crawl_result()

    mock_crawler = AsyncMock()
    mock_crawler.fetch.return_value = crawl_result

    mock_redis_dedup = MagicMock()
    mock_redis_dedup.sismember.return_value = 1 if is_duplicate else 0
    mock_redis_dedup.sadd = MagicMock()

    mock_redis_mq = MagicMock()
    mock_redis_mq.lpush = MagicMock()

    mock_storage = MagicMock()
    mock_storage.save.return_value = StorageResult(
        local_path=Path("/tmp/test"),
        s3_text_path=s3_text_path,
        s3_image_paths=[],
    )

    pipeline = CrawlPipeline(
        crawler=mock_crawler,
        storage=mock_storage,
        dedup=DedupChecker(mock_redis_dedup),
        publisher=RedisPublisher(mock_redis_mq),
    )
    return pipeline, mock_redis_mq, mock_redis_dedup


async def test_pipeline_enqueues_post():
    """비중복·비빈 게시글은 posts:queue에 LPUSH된다."""
    pipeline, mock_mq, _ = _make_pipeline(crawl_result=_make_crawl_result(_KEYWORD_TEXT))

    with _isolated_sites(), patch(
        "crawler.src.scheduler.crawl_scheduler._fetch_post_urls",
        return_value=[_TEST_URL],
    ):
        stats = await pipeline.run()

    assert stats.enqueued == 1
    assert stats.attempted == 1
    assert stats.skipped_dedup == 0
    assert stats.skipped_empty == 0
    mock_mq.lpush.assert_called_once()
    assert mock_mq.lpush.call_args[0][0] == "posts:queue"


async def test_pipeline_skips_duplicate_post():
    """중복 게시글(dedup 히트)은 LPUSH 없이 건너뛴다."""
    pipeline, mock_mq, _ = _make_pipeline(
        crawl_result=_make_crawl_result(_KEYWORD_TEXT),
        is_duplicate=True,
    )

    with _isolated_sites(), patch(
        "crawler.src.scheduler.crawl_scheduler._fetch_post_urls",
        return_value=[_TEST_URL],
    ):
        stats = await pipeline.run()

    assert stats.enqueued == 0
    assert stats.skipped_dedup == 1
    mock_mq.lpush.assert_not_called()


async def test_pipeline_skips_empty_post():
    """fit_markdown 이 비어있는 게시글은 LPUSH 없이 건너뛴다 (큐 오염 방지)."""
    empty_result = CrawlResult(
        url=_TEST_URL, raw_markdown="", fit_markdown="   ",
        images=[], downloaded_images=[],
    )
    pipeline, mock_mq, _ = _make_pipeline(crawl_result=empty_result)

    with _isolated_sites(), patch(
        "crawler.src.scheduler.crawl_scheduler._fetch_post_urls",
        return_value=[_TEST_URL],
    ):
        stats = await pipeline.run()

    assert stats.enqueued == 0
    assert stats.skipped_empty == 1
    mock_mq.lpush.assert_not_called()


async def test_pipeline_individual_failure_continues():
    """개별 게시글 크롤 실패 시 예외 로그 후 다음 게시글로 진행한다."""
    mock_crawler = AsyncMock()
    mock_crawler.fetch.side_effect = Exception("크롤 실패")

    mock_redis_dedup = MagicMock()
    mock_redis_dedup.sismember.return_value = 0

    mock_redis_mq = MagicMock()

    pipeline = CrawlPipeline(
        crawler=mock_crawler,
        storage=MagicMock(),
        dedup=DedupChecker(mock_redis_dedup),
        publisher=RedisPublisher(mock_redis_mq),
    )

    with _isolated_sites(), patch(
        "crawler.src.scheduler.crawl_scheduler._fetch_post_urls",
        return_value=[_TEST_URL, _TEST_URL2],
    ):
        stats = await pipeline.run()

    assert stats.failed == 2
    assert stats.attempted == 2
    mock_redis_mq.lpush.assert_not_called()


async def test_pipeline_s3_paths_propagated_to_event():
    """PostStorage의 s3_text_path가 CrawlEvent에 전파된다."""
    s3_path = "s3://my-bucket/raw/inven_maple/2026-04-28/123.md"
    pipeline, mock_mq, _ = _make_pipeline(
        crawl_result=_make_crawl_result(_KEYWORD_TEXT),
        s3_text_path=s3_path,
    )

    with _isolated_sites(), patch(
        "crawler.src.scheduler.crawl_scheduler._fetch_post_urls",
        return_value=[_TEST_URL],
    ):
        await pipeline.run()

    mock_mq.lpush.assert_called_once()
    event_json = mock_mq.lpush.call_args[0][1]
    event = CrawlEvent.from_json(event_json)
    assert event.s3_text_path == s3_path


async def test_pipeline_event_json_roundtrip():
    """LPUSH된 CrawlEvent JSON이 from_json()으로 역직렬화된다 (스키마 정합성)."""
    pipeline, mock_mq, _ = _make_pipeline(crawl_result=_make_crawl_result(_KEYWORD_TEXT))

    with _isolated_sites(), patch(
        "crawler.src.scheduler.crawl_scheduler._fetch_post_urls",
        return_value=[_TEST_URL],
    ):
        stats = await pipeline.run()

    assert stats.enqueued == 1
    event_json = mock_mq.lpush.call_args[0][1]

    event = CrawlEvent.from_json(event_json)
    assert event.site_name == "인벤 (메이플스토리)"
    assert event.source_id == "inven_maple"
    assert event.language in {"ko", "zh-CN", "zh-TW"}
    assert isinstance(event.image_urls, list)
    assert event.s3_text_path == ""


async def test_pipeline_dedup_mark_seen_called_after_enqueue():
    """LPUSH 성공 후 dedup mark_seen(sadd)이 호출되며, 호출 순서를 보장한다 (Anti-Pattern #6)."""
    call_log: list[str] = []

    pipeline, mock_mq, mock_redis_dedup = _make_pipeline(
        crawl_result=_make_crawl_result(_KEYWORD_TEXT)
    )
    mock_mq.lpush.side_effect = lambda *a, **kw: call_log.append("lpush")
    mock_redis_dedup.sadd.side_effect = lambda *a, **kw: call_log.append("sadd")

    with _isolated_sites(), patch(
        "crawler.src.scheduler.crawl_scheduler._fetch_post_urls",
        return_value=[_TEST_URL],
    ):
        await pipeline.run()

    mock_mq.lpush.assert_called_once()
    mock_redis_dedup.sadd.assert_called_once()
    assert call_log == ["lpush", "sadd"], (
        f"Anti-Pattern #6: mark_seen 은 LPUSH 이후에 호출되어야 함. 실제 순서: {call_log}"
    )
