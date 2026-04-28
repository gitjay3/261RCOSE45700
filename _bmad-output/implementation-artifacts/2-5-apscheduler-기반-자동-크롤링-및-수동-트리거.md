# Story 2.5: APScheduler 기반 자동 크롤링 및 수동 트리거

Status: review

> 🎯 **본 스토리 핵심:** Story 2.3~2.4에서 완성된 크롤러·전처리·S3 아카이브 파이프라인을 APScheduler로 자동화하고, Redis pub/sub `crawl:trigger` 채널로 수동 즉시 실행을 지원한다. 전처리를 통과한 `CrawlEvent`를 Redis DB0 `posts:queue`에 LPUSH하여 Detection Worker(Epic 3)의 소비 준비를 완료한다.
>
> **[전제 조건]** Story 2.4 `review` 상태. `Crawl4AICrawler`, `PostStorage`(`StorageResult` 반환), `DedupChecker`, `keyword_filter`, `language_detector`, `serializer.to_crawl_event()`, `shared/models/crawl_event.py`(s3 필드 포함)가 완성된 상태.

## Story

개발자로서,
크롤링이 1시간 주기로 자동 실행되고 Redis pub/sub으로 즉시 트리거할 수 있기를 원한다,
그래서 긴급 상황에서 담당자가 수동으로 즉시 크롤링을 시작할 수 있다.

## Acceptance Criteria

1. **Given** `CRAWL_INTERVAL_MINUTES` 환경변수가 설정된 환경에서 **When** `crawl_scheduler.py`가 시작되면 **Then** `AsyncIOScheduler`가 `CRAWL_INTERVAL_MINUTES` 주기(분 단위)로 `CrawlPipeline.run()`을 실행하고, `get_enabled_sites()`의 모든 활성화 사이트를 순회 크롤링한다 (FR1, FR28, NFR17). `CRAWL_INTERVAL_MINUTES`가 미설정 시 기본값 `60`을 사용한다.

2. **Given** `AsyncIOScheduler`에 Job이 등록될 때 **When** Job 설정이 적용되면 **Then** `max_instances=1`, `misfire_grace_time=60`이 명시 설정되어 이전 크롤링이 실행 중인 동안 새 주기가 트리거되어도 중복 실행이 방지된다 (ARCH-10).

3. **Given** `trigger_listener.py`가 실행 중일 때 **When** Redis `crawl:trigger` 채널에 메시지가 발행되면 **Then** `TriggerListener`가 메시지를 수신하고 `CrawlPipeline.run()`을 즉시 호출하며, 구조화 로그에 `"수동 트리거 수신"` 메시지와 `correlation_id`가 기록된다 (FR6).

4. **Given** `CrawlPipeline.run()`이 실행될 때 **When** 크롤링 → 전처리가 완료되면 **Then** 전처리(`dedup_checker` 비중복 + `keyword_filter` 통과)를 모두 통과한 게시글이 `CrawlEvent` JSON으로 직렬화되어 Redis DB0 `posts:queue`에 `LPUSH`된다. `CrawlEvent`의 `s3_text_path`와 `s3_image_paths`는 `PostStorage.save()`가 반환한 `StorageResult` 필드로 채워진다.

5. **Given** `CrawlScheduler` 프로세스가 재시작될 때 **When** `main.py`가 다시 실행되면 **Then** `AsyncIOScheduler`가 `CRAWL_INTERVAL_MINUTES` 주기로 다음 스케줄을 자동 재등록하고 다음 주기에 크롤링을 재개한다 (NFR10). 재시작 중에 누락된 주기(`misfire_grace_time=60` 초과)는 건너뛴다.

6. **Given** `crawler/tests/integration/test_crawl_pipeline.py`가 실행될 때 **When** `CrawlPipeline.run()`을 mock `Crawl4AICrawler`와 mock Redis 클라이언트로 실행하면 **Then** 다음을 검증한다:
   - 키워드 포함 게시글 → `redis.lpush("posts:queue", ...)` 호출 1회
   - 중복 게시글(`DedupChecker.is_duplicate()=True`) → `lpush` 미호출
   - 키워드 미포함 게시글 → `lpush` 미호출
   - `CrawlEvent.to_json()` 역직렬화 시 `from_json()`이 성공 (스키마 정합성)
   - 개별 게시글 크롤 실패 → 예외 로그 후 다음 게시글 진행 (파이프라인 미중단)
   - `s3_text_path`가 `StorageResult`에서 `CrawlEvent`로 전파됨

7. **Given** 통합 테스트가 완료될 때 **When** `cd crawler && ./.venv/bin/pytest tests/integration/ -v`를 실행하면 **Then** 신규 통합 테스트 ≥6건이 **모두 PASS**하며 실제 Redis, S3, 브라우저 호출이 0건이다. 기존 48건(Story 2.1~2.4) 회귀 없이 전체 ≥54건 PASS.

> **AC 출처:** epics.md L371-L387 (Story 2.5). AC 4(S3 경로 전파), AC 5(재시작 자동 재개 = `AsyncIOScheduler` 재등록), AC 6(통합 테스트 항목)은 Story 2.3/2.4 패턴과 architecture.md ARCH-10 기반으로 구체화.

## Tasks / Subtasks

- [x] **Task 1: requirements.txt 업데이트** (AC: #1, #2)
  - [x] 1.1 `crawler/requirements.txt`에 추가:
    ```
    APScheduler>=3.10.0,<4.0.0
    redis>=5.0.0
    ```
  - [x] 1.2 APScheduler 4.x는 API가 완전히 재작성되어 호환 불가 — 반드시 `<4.0.0` 버전 핀 유지.
  - [x] 1.3 `redis>=5.0.0`은 `redis.asyncio` 서브모듈을 내장 — 별도 `aioredis` 설치 불필요.

- [x] **Task 2: RedisPublisher 구현** (AC: #4)
  - [x] 2.1 `crawler/src/queue/__init__.py` 신규 (빈 파일)
  - [x] 2.2 `crawler/src/queue/redis_publisher.py` 신규:
    ```python
    import os
    from shared.config.redis_config import REDIS_KEY_POSTS_QUEUE
    from shared.structured_logger import get_logger

    _SERVICE_NAME = os.environ.get("SERVICE_NAME", "crawler")
    _logger = get_logger(__name__)

    class RedisPublisher:
        def __init__(self, redis_client) -> None:
            self._redis = redis_client

        def enqueue(self, event_json: str, *, correlation_id: str) -> None:
            self._redis.lpush(REDIS_KEY_POSTS_QUEUE, event_json)
            _logger.info(
                "posts:queue LPUSH 완료",
                extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
            )
    ```
  - [x] 2.3 `REDIS_KEY_POSTS_QUEUE = "posts:queue"` — `shared/config/redis_config.py`에서 임포트. 문자열 하드코딩 금지.

- [x] **Task 3: serializer.to_crawl_event() S3 파라미터 확장** (AC: #4)
  - [x] 3.1 `crawler/src/preprocessor/serializer.py` 수정:
    ```python
    def to_crawl_event(
        result: CrawlResult,
        *,
        site_id: str,
        site: SiteConfig,
        url: str,
        language: str,
        correlation_id: str,
        s3_text_path: str = "",          # Story 2.5 추가
        s3_image_paths: list[str] | None = None,  # Story 2.5 추가
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
    ```
  - [x] 3.2 새 파라미터는 keyword-only, 기본값 `""`/`None` — 기존 호출부(`demo.py` 등) 코드 수정 불필요.

- [x] **Task 4: TriggerListener 구현** (AC: #3)
  - [x] 4.1 `crawler/src/scheduler/__init__.py` 신규 (빈 파일)
  - [x] 4.2 `crawler/src/scheduler/trigger_listener.py` 신규:
    ```python
    import asyncio
    import os
    from collections.abc import Coroutine
    import redis.asyncio as aioredis
    from shared.correlation_id import generate
    from shared.structured_logger import get_logger

    _SERVICE_NAME = os.environ.get("SERVICE_NAME", "crawler")
    _logger = get_logger(__name__)
    _CHANNEL = "crawl:trigger"

    class TriggerListener:
        def __init__(self, redis_url: str, pipeline_fn) -> None:
            self._redis_url = redis_url
            self._run_pipeline = pipeline_fn  # async callable

        async def listen(self) -> None:
            client = aioredis.from_url(self._redis_url, db=0, decode_responses=True)
            async with client.pubsub() as pubsub:
                await pubsub.subscribe(_CHANNEL)
                _logger.info(
                    "crawl:trigger 채널 구독 시작",
                    extra={"correlation_id": "", "service": _SERVICE_NAME},
                )
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        cid = generate()
                        _logger.info(
                            "수동 트리거 수신 — 즉시 크롤링 시작",
                            extra={"correlation_id": cid, "service": _SERVICE_NAME},
                        )
                        await self._run_pipeline()
    ```
  - [x] 4.3 `redis.asyncio`는 `redis>=5.0.0`에 포함 — `import redis.asyncio as aioredis` 사용. `aioredis` 별도 패키지 설치 금지.

- [x] **Task 5: CrawlPipeline + CrawlScheduler 구현** (AC: #1, #2, #4, #5)
  - [x] 5.1 `crawler/src/scheduler/crawl_scheduler.py` 신규 — 구조:

    ```python
    """APScheduler 기반 크롤링 파이프라인 + 수동 트리거 진입점."""
    from __future__ import annotations

    import asyncio
    import logging
    import os
    import re
    from dataclasses import dataclass, field
    from pathlib import Path

    import redis
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    from crawl4ai.async_configs import CacheMode

    from crawler.src.crawl4ai_crawler import Crawl4AICrawler
    from crawler.src.preprocessor import keyword_filter, language_detector
    from crawler.src.preprocessor.dedup_checker import DedupChecker
    from crawler.src.preprocessor.serializer import to_crawl_event
    from crawler.src.queue.redis_publisher import RedisPublisher
    from crawler.src.scheduler.trigger_listener import TriggerListener
    from crawler.src.sites.registry import get_enabled_sites
    from crawler.src.storage import PostStorage
    from shared.config.redis_config import REDIS_DEDUP_DB, REDIS_MQ_DB
    from shared.correlation_id import generate
    from shared.structured_logger import get_logger

    _SERVICE_NAME = os.environ.get("SERVICE_NAME", "crawler")
    _logger = get_logger(__name__)
    _MAX_POSTS_PER_BOARD = int(os.environ.get("MAX_POSTS_PER_BOARD", "10"))


    async def _fetch_post_urls(board_url: str, pattern: str, limit: int) -> list[str]:
        """게시판 목록 페이지에서 게시글 URL 추출 (stealth 브라우저 + 링크 파싱)."""
        cfg = BrowserConfig(headless=True, enable_stealth=True, verbose=False)
        run = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, page_timeout=20_000)
        async with AsyncWebCrawler(config=cfg) as crawler:
            result = await crawler.arun(board_url, config=run)
        if not result.success:
            _logger.warning("게시판 목록 크롤 실패: %s", board_url,
                            extra={"correlation_id": "", "service": _SERVICE_NAME})
            return []
        all_links = (result.links.get("internal") or []) + (result.links.get("external") or [])
        seen: set[str] = set()
        post_urls: list[str] = []
        compiled = re.compile(pattern)
        for link in all_links:
            href = link.get("href", "").split("?")[0]
            if compiled.match(href) and href not in seen:
                seen.add(href)
                post_urls.append(href)
                if len(post_urls) >= limit:
                    break
        return post_urls


    @dataclass
    class PipelineStats:
        attempted: int = 0
        enqueued: int = 0
        skipped_dedup: int = 0
        skipped_keyword: int = 0
        failed: int = 0

        @property
        def success_rate(self) -> float:
            if self.attempted == 0:
                return 1.0
            return (self.attempted - self.failed) / self.attempted


    class CrawlPipeline:
        def __init__(
            self,
            crawler: Crawl4AICrawler,
            storage: PostStorage,
            dedup: DedupChecker,
            publisher: RedisPublisher,
        ) -> None:
            self._crawler = crawler
            self._storage = storage
            self._dedup = dedup
            self._publisher = publisher

        async def run(self) -> PipelineStats:
            stats = PipelineStats()
            sites = get_enabled_sites()
            _logger.info("파이프라인 시작: 활성 사이트 %d개", len(sites),
                         extra={"correlation_id": "", "service": _SERVICE_NAME})

            for site_id, site in sites.items():
                for board_url in site.board_urls:
                    post_urls = await _fetch_post_urls(
                        board_url, site.post_url_pattern, _MAX_POSTS_PER_BOARD
                    )
                    for post_url in post_urls:
                        stats.attempted += 1
                        cid = generate()
                        try:
                            result = await self._crawler.fetch(
                                post_url,
                                correlation_id=cid,
                                image_filter=site.image_filter,
                                css_selector=site.css_selector,
                            )
                            if self._dedup.is_duplicate(result.fit_markdown, correlation_id=cid):
                                stats.skipped_dedup += 1
                                continue
                            if not keyword_filter.passes(result.fit_markdown, correlation_id=cid):
                                stats.skipped_keyword += 1
                                continue
                            language = language_detector.detect(result.fit_markdown, correlation_id=cid)
                            post_id = site.post_id_extractor(post_url)
                            storage_result = self._storage.save(
                                site_id=site_id, post_id=post_id,
                                url=post_url, result=result, correlation_id=cid,
                            )
                            event = to_crawl_event(
                                result, site_id=site_id, site=site, url=post_url,
                                language=language, correlation_id=cid,
                                s3_text_path=storage_result.s3_text_path,
                                s3_image_paths=storage_result.s3_image_paths,
                            )
                            self._publisher.enqueue(event.to_json(), correlation_id=cid)
                            self._dedup.mark_seen(result.fit_markdown, correlation_id=cid)
                            stats.enqueued += 1
                        except Exception as exc:
                            stats.failed += 1
                            _logger.error(
                                "게시글 처리 실패: %s — %s", post_url, exc,
                                extra={"correlation_id": cid, "service": _SERVICE_NAME},
                            )

            _logger.info(
                "파이프라인 완료: 시도=%d 큐=%d 중복제외=%d 키워드제외=%d 실패=%d",
                stats.attempted, stats.enqueued, stats.skipped_dedup,
                stats.skipped_keyword, stats.failed,
                extra={"correlation_id": "", "service": _SERVICE_NAME},
            )
            return stats


    class CrawlScheduler:
        def __init__(self) -> None:
            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
            mq_client = redis.from_url(redis_url, db=REDIS_MQ_DB, decode_responses=True)
            dedup_client = redis.from_url(redis_url, db=REDIS_DEDUP_DB, decode_responses=True)

            self._pipeline = CrawlPipeline(
                crawler=Crawl4AICrawler(headless=True, output_dir="output/_tmp"),
                storage=PostStorage(),
                dedup=DedupChecker(dedup_client),
                publisher=RedisPublisher(mq_client),
            )
            self._trigger_listener = TriggerListener(redis_url, self._pipeline.run)
            self._scheduler = AsyncIOScheduler()

        def setup_schedule(self) -> None:
            interval = int(os.environ.get("CRAWL_INTERVAL_MINUTES", "60"))
            self._scheduler.add_job(
                self._pipeline.run,
                trigger="interval",
                minutes=interval,
                max_instances=1,
                misfire_grace_time=60,
                id="crawl_pipeline",
                replace_existing=True,
            )
            _logger.info("APScheduler 등록: %d분 주기", interval,
                         extra={"correlation_id": "", "service": _SERVICE_NAME})

        async def run_forever(self) -> None:
            self.setup_schedule()
            self._scheduler.start()
            try:
                await self._trigger_listener.listen()
            finally:
                self._scheduler.shutdown(wait=False)


    async def _async_main() -> None:
        scheduler = CrawlScheduler()
        await scheduler.run_forever()


    if __name__ == "__main__":
        asyncio.run(_async_main())
    ```

- [x] **Task 6: 통합 테스트 작성** (AC: #6, #7)
  - [x] 6.1 `crawler/tests/integration/__init__.py` 신규 (빈 파일)
  - [x] 6.2 `crawler/tests/integration/test_crawl_pipeline.py` 신규 (≥6건):
    ```
    - test_pipeline_enqueues_keyword_matched_post — 키워드 게시글 → lpush 호출
    - test_pipeline_skips_duplicate_post — dedup 히트 → lpush 미호출
    - test_pipeline_skips_no_keyword_post — 키워드 없음 → lpush 미호출
    - test_pipeline_individual_failure_continues — 단일 실패 → 다음 진행
    - test_pipeline_s3_paths_propagated_to_event — StorageResult.s3_text_path → CrawlEvent.s3_text_path
    - test_pipeline_event_json_roundtrip — to_json() → from_json() 성공
    ```
  - [x] 6.3 테스트 픽스처: `_fetch_post_urls`를 `patch("crawler.src.scheduler.crawl_scheduler._fetch_post_urls", return_value=[...])` 패턴으로 mock.
  - [x] 6.4 Redis 클라이언트 mock: `MagicMock()` 사용, `sismember` → `return_value = 0`(미중복), `lpush` 호출 여부로 검증.
  - [x] 6.5 `Crawl4AICrawler.fetch` mock: `AsyncMock()` — `asyncio_mode = auto` 환경에서 `AsyncMock` 사용.

- [x] **Task 7: 검증 및 마무리**
  - [x] 7.1 `cd crawler && ./.venv/bin/pip install -r requirements.txt`
  - [x] 7.2 `cd crawler && ./.venv/bin/pytest -v` → 기존 48건 + 신규 7건 = **55건 전부 PASS**, 실제 Redis/S3/브라우저 호출 0건
  - [x] 7.3 `sprint-status.yaml`의 `2-5-apscheduler-기반-자동-크롤링-및-수동-트리거: backlog → ready-for-dev` 갱신 (이미 완료)

## Dev Notes

### 본 스토리 범위 (Scope Boundary)

| 이번 스토리에서 한다 | 이번 스토리에서 **하지 않는다** |
|---|---|
| `crawl_scheduler.py` — `CrawlPipeline`, `CrawlScheduler` | PTT/Dcard SiteConfig 활성화 → Story 2.6 |
| `trigger_listener.py` — Redis pub/sub `crawl:trigger` | tieba/52pojie/NGA SiteConfig + 프록시 → Story 2.7 |
| `redis_publisher.py` — `posts:queue` LPUSH | Redis AOF 설정 → Story 1.3(docker-compose) |
| `serializer.py` — `s3_text_path`, `s3_image_paths` 파라미터 추가 | `posts:processing` Watchdog → Story 3.1 |
| `APScheduler>=3.10.0,<4.0.0`, `redis>=5.0.0` requirements | S3 버킷 생성·IAM Role → Story 5.3 |
| `tests/integration/test_crawl_pipeline.py` ≥6건 | E2E 파이프라인 테스트 → Story 5.4 |

### 현재 `crawler/` 구조 (Story 2.4 완료 기준)

```
crawler/
├── requirements.txt              # crawl4ai, httpx, langdetect, boto3 포함
├── pytest.ini                    # asyncio_mode = auto
├── demo.py                       # 수동 실행 파이프라인 (참조용)
└── src/
    ├── crawl4ai_crawler.py       # Crawl4AICrawler, CrawlResult
    ├── s3_uploader.py            # S3Uploader
    ├── storage.py                # PostStorage → StorageResult 반환
    ├── sites/registry.py         # SiteConfig, get_enabled_sites()
    └── preprocessor/
        ├── language_detector.py  # detect(text, *, correlation_id) → str
        ├── dedup_checker.py      # DedupChecker(redis_client)
        ├── keyword_filter.py     # passes(text, *, correlation_id) → bool
        └── serializer.py         # to_crawl_event() ← 이 스토리에서 s3 파라미터 추가
```

**이 스토리에서 추가될 구조:**

```
crawler/
├── requirements.txt              ← 수정 (APScheduler, redis 추가)
└── src/
    ├── scheduler/
    │   ├── __init__.py           ← 신규
    │   ├── crawl_scheduler.py    ← 신규 (CrawlPipeline, CrawlScheduler, _fetch_post_urls)
    │   └── trigger_listener.py   ← 신규 (TriggerListener)
    └── queue/
        ├── __init__.py           ← 신규
        └── redis_publisher.py    ← 신규 (RedisPublisher)

crawler/tests/
└── integration/
    ├── __init__.py               ← 신규
    └── test_crawl_pipeline.py    ← 신규 (≥6건)
```

**수정 파일:**
- `crawler/src/preprocessor/serializer.py` — `s3_text_path`, `s3_image_paths` 파라미터 추가

**비변경 파일:**
- `crawler/src/crawl4ai_crawler.py`, `storage.py`, `s3_uploader.py`
- `crawler/src/sites/registry.py`
- `crawler/src/preprocessor/{language_detector,dedup_checker,keyword_filter}.py`
- `shared/models/crawl_event.py` (Story 2.4에서 이미 s3 필드 추가 완료)

### APScheduler 버전 선택 근거

- **APScheduler 3.x** (`AsyncIOScheduler`) — asyncio 이벤트 루프와 통합, stable API
- **APScheduler 4.x** — 완전 재작성(API 호환 불가). 반드시 `<4.0.0` 버전 핀 필요.
- `AsyncIOScheduler`의 `add_job()` 파라미터: `trigger="interval"`, `minutes=N`, `max_instances=1`, `misfire_grace_time=60`

```python
# ✅ 올바른 패턴
from apscheduler.schedulers.asyncio import AsyncIOScheduler
scheduler = AsyncIOScheduler()
scheduler.add_job(
    async_fn,           # async def 함수 직접 전달 가능
    trigger="interval",
    minutes=interval,
    max_instances=1,    # ARCH-10: 중복 실행 방지
    misfire_grace_time=60,  # ARCH-10: 60초 초과 지연 시 건너뜀
    id="crawl_pipeline",
    replace_existing=True,  # 재시작 시 동일 ID 잡 교체
)
scheduler.start()  # non-blocking

# ❌ 금지: BackgroundScheduler + asyncio.run() 래핑
```

### Redis 연결 패턴

```python
import redis
from shared.config.redis_config import REDIS_MQ_DB, REDIS_DEDUP_DB

# 동기 Redis (DedupChecker, RedisPublisher용)
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
mq_client = redis.from_url(redis_url, db=REDIS_MQ_DB, decode_responses=True)
dedup_client = redis.from_url(redis_url, db=REDIS_DEDUP_DB, decode_responses=True)

# 비동기 Redis (TriggerListener pub/sub용)
import redis.asyncio as aioredis
async_client = aioredis.from_url(redis_url, db=0, decode_responses=True)
```

- `shared/config/redis_config.py`: `REDIS_MQ_DB=0`, `REDIS_DEDUP_DB=1`, `REDIS_KEY_POSTS_QUEUE="posts:queue"`
- `decode_responses=True` — 문자열 자동 디코딩, bytes 불필요
- **로컬 개발:** `REDIS_URL` 미설정 시 `"redis://localhost:6379"` 기본값

### `_fetch_post_urls()` 구현 패턴

`demo.py`의 `get_post_urls()` 함수를 `crawl_scheduler.py` 모듈 레벨 함수로 이식:

```python
async def _fetch_post_urls(board_url: str, pattern: str, limit: int) -> list[str]:
    cfg = BrowserConfig(headless=True, enable_stealth=True, verbose=False)
    run = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, page_timeout=20_000)
    async with AsyncWebCrawler(config=cfg) as crawler:
        result = await crawler.arun(board_url, config=run)
    if not result.success:
        return []
    all_links = (result.links.get("internal") or []) + (result.links.get("external") or [])
    seen: set[str] = set()
    post_urls: list[str] = []
    compiled = re.compile(pattern)
    for link in all_links:
        href = link.get("href", "").split("?")[0]
        if compiled.match(href) and href not in seen:
            seen.add(href)
            post_urls.append(href)
            if len(post_urls) >= limit:
                break
    return post_urls
```

- 모듈 레벨 함수 (`_fetch_post_urls`)로 정의 → 테스트에서 `patch("crawler.src.scheduler.crawl_scheduler._fetch_post_urls", ...)` 패칭 가능
- `Crawl4AICrawler`를 **사용하지 않음** — 게시판 목록 크롤은 링크 추출만 필요, 전체 crawl4ai 파이프라인 불필요

### 통합 테스트 패턴

```python
# crawler/tests/integration/test_crawl_pipeline.py
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crawler.src.preprocessor.dedup_checker import DedupChecker
from crawler.src.queue.redis_publisher import RedisPublisher
from crawler.src.scheduler.crawl_scheduler import CrawlPipeline
from crawler.src.storage import StorageResult
from crawler.src.crawl4ai_crawler import CrawlResult
from shared.models.crawl_event import CrawlEvent


def _make_pipeline(
    *,
    crawl_result: CrawlResult,
    is_duplicate: bool = False,
    s3_text_path: str = "",
) -> tuple[CrawlPipeline, MagicMock, MagicMock]:
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


_KEYWORD_TEXT = "매크로 판매합니다 텔레그램 문의"
_CLEAN_TEXT = "오늘 날씨 정말 좋네요"
_TEST_URL = "https://www.inven.co.kr/board/maple/2298/123"


async def test_pipeline_enqueues_keyword_matched_post():
    result = CrawlResult(url=_TEST_URL, raw_markdown=_KEYWORD_TEXT,
                         fit_markdown=_KEYWORD_TEXT, images=[], downloaded_images=[])
    pipeline, mock_mq, _ = _make_pipeline(crawl_result=result)

    with patch("crawler.src.scheduler.crawl_scheduler._fetch_post_urls",
               return_value=[_TEST_URL]):
        stats = await pipeline.run()

    assert stats.enqueued == 1
    assert stats.attempted == 1
    mock_mq.lpush.assert_called_once()


async def test_pipeline_skips_duplicate_post():
    result = CrawlResult(url=_TEST_URL, raw_markdown=_KEYWORD_TEXT,
                         fit_markdown=_KEYWORD_TEXT, images=[], downloaded_images=[])
    pipeline, mock_mq, _ = _make_pipeline(crawl_result=result, is_duplicate=True)

    with patch("crawler.src.scheduler.crawl_scheduler._fetch_post_urls",
               return_value=[_TEST_URL]):
        stats = await pipeline.run()

    assert stats.enqueued == 0
    assert stats.skipped_dedup == 1
    mock_mq.lpush.assert_not_called()


async def test_pipeline_skips_no_keyword_post():
    result = CrawlResult(url=_TEST_URL, raw_markdown=_CLEAN_TEXT,
                         fit_markdown=_CLEAN_TEXT, images=[], downloaded_images=[])
    pipeline, mock_mq, _ = _make_pipeline(crawl_result=result)

    with patch("crawler.src.scheduler.crawl_scheduler._fetch_post_urls",
               return_value=[_TEST_URL]):
        stats = await pipeline.run()

    assert stats.enqueued == 0
    assert stats.skipped_keyword == 1
    mock_mq.lpush.assert_not_called()


async def test_pipeline_individual_failure_continues():
    mock_crawler = AsyncMock()
    mock_crawler.fetch.side_effect = Exception("크롤 실패")
    mock_redis_mq = MagicMock()
    pipeline = CrawlPipeline(
        crawler=mock_crawler,
        storage=MagicMock(),
        dedup=DedupChecker(MagicMock(sismember=MagicMock(return_value=0))),
        publisher=RedisPublisher(mock_redis_mq),
    )
    with patch("crawler.src.scheduler.crawl_scheduler._fetch_post_urls",
               return_value=[_TEST_URL, _TEST_URL + "2"]):
        stats = await pipeline.run()

    assert stats.failed == 2
    assert stats.attempted == 2
    mock_redis_mq.lpush.assert_not_called()


async def test_pipeline_s3_paths_propagated_to_event():
    s3_path = "s3://my-bucket/raw/inven_maple/2026-04-28/123.md"
    result = CrawlResult(url=_TEST_URL, raw_markdown=_KEYWORD_TEXT,
                         fit_markdown=_KEYWORD_TEXT, images=[], downloaded_images=[])
    pipeline, mock_mq, _ = _make_pipeline(crawl_result=result, s3_text_path=s3_path)

    with patch("crawler.src.scheduler.crawl_scheduler._fetch_post_urls",
               return_value=[_TEST_URL]):
        await pipeline.run()

    call_args = mock_mq.lpush.call_args
    event_json = call_args[0][1]  # lpush("posts:queue", event_json)
    event = CrawlEvent.from_json(event_json)
    assert event.s3_text_path == s3_path


async def test_pipeline_event_json_roundtrip():
    result = CrawlResult(url=_TEST_URL, raw_markdown=_KEYWORD_TEXT,
                         fit_markdown=_KEYWORD_TEXT, images=[], downloaded_images=[])
    pipeline, mock_mq, _ = _make_pipeline(crawl_result=result)

    with patch("crawler.src.scheduler.crawl_scheduler._fetch_post_urls",
               return_value=[_TEST_URL]):
        stats = await pipeline.run()

    assert stats.enqueued == 1
    call_args = mock_mq.lpush.call_args
    event_json = call_args[0][1]
    event = CrawlEvent.from_json(event_json)  # from_json()이 성공해야 함
    assert event.site_name == "인벤 (메이플스토리)"
    assert event.language in {"ko", "zh-CN", "zh-TW"}
```

### `serializer.to_crawl_event()` 변경 전/후

```python
# 변경 전 (Story 2.3)
def to_crawl_event(result, *, site_id, site, url, language, correlation_id) -> CrawlEvent:
    ...
    return CrawlEvent(..., s3_text_path="", s3_image_paths=[])

# 변경 후 (Story 2.5)
def to_crawl_event(
    result, *, site_id, site, url, language, correlation_id,
    s3_text_path: str = "",            # 신규 (keyword-only, 기본값 유지로 기존 호출부 무영향)
    s3_image_paths: list[str] | None = None,  # 신규
) -> CrawlEvent:
    ...
    return CrawlEvent(..., s3_text_path=s3_text_path, s3_image_paths=s3_image_paths or [])
```

- `demo.py`와 `tests/unit/test_crawl4ai_crawler.py` 등 기존 `to_crawl_event()` 호출부는 **수정 불필요** (기본값 `""` 사용).

### Architecture Compliance Notes

- **architecture.md P6 (구조화 로그)** — 모든 로그에 `extra={"correlation_id": cid, "service": _SERVICE_NAME}` 포함. 파이프라인 시작/완료 로그 필수.
- **architecture.md Cross-Cutting #1 (Correlation ID)** — 게시글 단위로 `shared.correlation_id.generate()` 호출, 이후 모든 단계에 전파.
- **architecture.md Cross-Cutting #7 (APScheduler 중복 실행 방지, ARCH-10)** — `max_instances=1`, `misfire_grace_time=60` 필수.
- **architecture.md P2 (Redis 키 명명)** — `posts:queue`, `crawl:trigger` 패턴 준수. 상수는 `shared.config.redis_config`에서 임포트.
- **NFR10 (24시간 무중단)** — `AsyncIOScheduler`는 재시작 후 자동 재등록. 재시작 누락 주기는 `misfire_grace_time=60` 초과 시 건너뜀(의도적 설계).
- **NFR17 (CRAWL_INTERVAL_MINUTES 재배포 없이 변경)** — 환경변수 재로드는 프로세스 재시작만으로 적용. hot-reload 불필요.

### Anti-Patterns to Avoid

1. ❌ **`APScheduler>=4.0.0` 사용** — API 완전 재작성으로 `AsyncIOScheduler` 임포트 경로 변경됨. 반드시 `<4.0.0` 핀.
2. ❌ **`BackgroundScheduler` + `asyncio.run()` 래핑** — `Crawl4AICrawler.fetch()`는 async. sync 스케줄러에서 `asyncio.run()` 호출 시 이벤트 루프 충돌.
3. ❌ **`aioredis` 별도 패키지 설치** — `redis>=5.0.0`에 `redis.asyncio`가 내장. `pip install aioredis` 불필요.
4. ❌ **`_fetch_post_urls()` 없이 `Crawl4AICrawler.fetch()`로 게시판 목록 크롤** — `Crawl4AICrawler`는 전체 파이프라인(이미지 다운로드 포함), 게시판 목록에는 과도. `AsyncWebCrawler` 직접 사용으로 링크만 추출.
5. ❌ **`to_crawl_event()` 호출 후 `event.s3_text_path = ...` 직접 필드 할당** — `to_crawl_event()`에 파라미터 추가하여 팩토리 함수 내에서 처리.
6. ❌ **`dedup_checker.mark_seen()` 를 `LPUSH` 이전에 호출** — LPUSH 성공 확인 후 mark_seen 호출. LPUSH 실패 시 재크롤 가능해야 함.
7. ❌ **`CrawlPipeline.run()`이 첫 게시글 실패 시 예외 raise** — 개별 게시글 실패는 `try/except`로 catch, 다음 게시글 진행. 전체 파이프라인 중단 금지.
8. ❌ **`TriggerListener`에서 sync Redis pub/sub 사용** — `trigger_listener.py`는 async context. `redis.asyncio`의 `pubsub().listen()` 사용.
9. ❌ **`REDIS_URL` 하드코딩** — 반드시 `os.environ.get("REDIS_URL", "redis://localhost:6379")` 패턴. 로컬 기본값 허용.
10. ❌ **`PipelineStats.success_rate` 계산을 테스트 assertion으로 사용** — AC #7의 ≥95%/≥90%는 실제 사이트 대상 품질 게이트. 단위 테스트에서는 enqueued/skipped/failed 카운트로 검증.

### Implementation Notes

1. **`CrawlPipeline`의 `dedup` 체크 순서** — 크롤 완료 후 텍스트 해시 기반 dedup 체크. `fit_markdown`이 빈 경우 `DedupChecker.is_duplicate("")`가 `False` 반환(dedup_checker.py L22 참조).

2. **`AsyncIOScheduler.start()` non-blocking** — `start()` 후 블로킹이 없음. 메인 코루틴에서 `TriggerListener.listen()` (무한 루프)를 `await`하여 프로세스 유지.

3. **`crawl_scheduler.py` 임포트 경로** — `CrawlPipeline`, `_fetch_post_urls` 등이 `crawler.src.scheduler.crawl_scheduler` 경로에 있어야 통합 테스트의 `patch()` 경로가 일치.

4. **`asyncio_mode = auto` (pytest.ini)** — `@pytest.mark.asyncio` 데코레이터 없이 `async def test_*` 함수가 자동 실행됨. 별도 decorator 추가 불필요.

5. **`DedupChecker` 생성자** — `DedupChecker(redis_client)` — sync redis 클라이언트 전달. `dedup_client.sismember(key, value)` 반환값이 `0`(미중복) 또는 `1`(중복).

6. **`PostStorage` 기본 생성자** — `PostStorage()` (no args) → `base_dir="output/posts"` 기본값. `ENABLE_S3_UPLOAD` 환경변수로 S3 활성화 여부 결정 (Story 2.4 구현 완료).

7. **테스트에서 `lpush` call_args 접근** — `mock_mq.lpush.call_args[0]`은 positional args tuple. `lpush("posts:queue", event_json)`에서 `call_args[0][1]`이 `event_json`.

### Project Context Reference

- [architecture.md — scheduler/ 디렉토리 구조](/_bmad-output/planning-artifacts/architecture.md#L451-L455): `crawler/src/scheduler/crawl_scheduler.py`, `trigger_listener.py`
- [architecture.md — queue/ 디렉토리](/_bmad-output/planning-artifacts/architecture.md#L471-L473): `crawler/src/queue/redis_publisher.py`
- [architecture.md — ARCH-10 APScheduler 중복 실행 방지](/_bmad-output/planning-artifacts/architecture.md#L84)
- [architecture.md — Cross-Cutting #7](/_bmad-output/planning-artifacts/architecture.md#L74)
- [epics.md — Story 2.5 AC](/_bmad-output/planning-artifacts/epics.md#L371-L387)
- [Story 2.4 Dev Notes — S3 경로 전파 예정 언급](/_bmad-output/implementation-artifacts/2-4-s3-원본-아카이브-및-이미지-수집.md#L493)
- [shared/config/redis_config.py](shared/config/redis_config.py) — `REDIS_MQ_DB`, `REDIS_DEDUP_DB`, `REDIS_KEY_POSTS_QUEUE`
- [crawler/src/preprocessor/serializer.py](crawler/src/preprocessor/serializer.py) — 이 스토리에서 s3 파라미터 추가
- [crawler/demo.py](crawler/demo.py) — `get_post_urls()` 참조 구현 (`_fetch_post_urls` 이식 원본)

### References

- [APScheduler 3.x 공식 문서 — AsyncIOScheduler](https://apscheduler.readthedocs.io/en/3.x/modules/schedulers/asyncio.html)
- [redis-py asyncio guide](https://redis-py.readthedocs.io/en/stable/asyncio.html) — `redis.asyncio` sub-module (redis>=5.0.0)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- `crawler/src/queue/redis_publisher.py` 신규: `RedisPublisher.enqueue()` — `REDIS_KEY_POSTS_QUEUE` 상수로 `posts:queue`에 LPUSH. 구조화 로그 포함.
- `crawler/src/scheduler/trigger_listener.py` 신규: `TriggerListener.listen()` — `redis.asyncio` pub/sub `crawl:trigger` 채널 구독. 메시지 수신 시 correlation_id 생성 후 pipeline_fn() 즉시 호출.
- `crawler/src/scheduler/crawl_scheduler.py` 신규: `_fetch_post_urls()` (게시판 목록 링크 추출), `PipelineStats` dataclass, `CrawlPipeline.run()` (크롤→전처리→enqueue), `CrawlScheduler` (`AsyncIOScheduler` + `TriggerListener` 통합). `max_instances=1`, `misfire_grace_time=60` ARCH-10 준수.
- `crawler/src/preprocessor/serializer.py` 수정: `to_crawl_event()`에 `s3_text_path: str = ""`, `s3_image_paths: list[str] | None = None` keyword-only 파라미터 추가. 기존 호출부 수정 없이 호환.
- `crawler/requirements.txt` 수정: `APScheduler>=3.10.0,<4.0.0`, `redis>=5.0.0` 추가 및 설치 완료 (APScheduler 3.11.2).
- `crawler/tests/integration/test_crawl_pipeline.py` 신규: 7건 — 기존 48건 + 신규 7건 = **55건 전부 PASS**, 실제 Redis/S3/브라우저 호출 0건.

### File List

신규:
- `crawler/src/queue/__init__.py`
- `crawler/src/queue/redis_publisher.py`
- `crawler/src/scheduler/__init__.py`
- `crawler/src/scheduler/crawl_scheduler.py`
- `crawler/src/scheduler/trigger_listener.py`
- `crawler/tests/integration/__init__.py`
- `crawler/tests/integration/test_crawl_pipeline.py`

수정:
- `crawler/requirements.txt` (APScheduler, redis 추가)
- `crawler/src/preprocessor/serializer.py` (s3_text_path, s3_image_paths 파라미터 추가)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (2-5: ready-for-dev → in-progress → review)

비변경:
- `crawler/src/crawl4ai_crawler.py`
- `crawler/src/storage.py`
- `crawler/src/s3_uploader.py`
- `crawler/src/sites/registry.py`
- `crawler/src/preprocessor/language_detector.py`
- `crawler/src/preprocessor/dedup_checker.py`
- `crawler/src/preprocessor/keyword_filter.py`
- `shared/models/crawl_event.py`

## Change Log

| 날짜 | 변경 | 사유 |
|---|---|---|
| 2026-04-28 | Story 2.5 컨텍스트 작성 (`Status: ready-for-dev`) | bmad-create-story |
| 2026-04-28 | Story 2.5 구현 완료 (`Status: review`) — `crawl_scheduler.py` + `trigger_listener.py` + `redis_publisher.py` 신규, `serializer.py` s3 파라미터 추가, 55건 PASS | bmad-dev-story |
