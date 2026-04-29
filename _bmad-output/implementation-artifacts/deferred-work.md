# Deferred Work

## Deferred from: code review of 2-4-s3-원본-아카이브-및-이미지-수집 (2026-04-29)

- **S3 key length >1024 byte 미체크** [crawler/src/s3_uploader.py:25,56] — 현재 사이트 post_id로는 비현실적. 외부 site 추가 시 재검토.
- **Surrogate `UnicodeEncodeError`** [crawler/src/s3_uploader.py:30, crawler/src/storage.py:76] — preprocessor에서 사전 정제 가정. Story 2.3 산출물 책임.
- **이미지 `read_bytes()` 전체 적재 → OOM** [crawler/src/s3_uploader.py:61] — image_filter score threshold로 작은 이미지만 통과. 운영 측정 후 `upload_file` (multipart) 도입 재검토.
- **동시 `save()` race (`src_path.read_bytes()` + `unlink`)** [crawler/src/storage.py:57-58] — 현재 sequential 파이프라인. Story 5+ 멀티 워커 구성 시 재검토.
- **`post.json` atomic-rename 부재** [crawler/src/storage.py:75-78] — Story 2.3 산출물 (사전 존재). tmp + rename(2) 패턴은 Epic 5 운영 강화 시.
- **이미지 filename 재시도 충돌 (`img_000` 덮어쓰기)** [crawler/src/crawl4ai_crawler.py:172] — `_download_images` 재호출 시 인덱스 재시작. Story 2.3 산출물.
- **`demo.py.get_post_urls`가 board마다 fresh browser 생성** [crawler/demo.py:41-46] — demo는 throwaway, 우선순위 낮음.
- **`site`/`date`/`post_id` 비ASCII/특수문자 → 잘못된 S3 키** [crawler/src/s3_uploader.py:25,56] — 현재 site_id 모두 ASCII alphanum. 신규 사이트 도입 시 정규식 검증.
- **테스트 `clear=True` 환경 전체 비움 → 회귀 검출력 약화** [crawler/tests/unit/test_s3_uploader.py:228-242] — 패치하지 않아도 현재 pass. 테스트 위생 개선 시 함께.
- **`AWS_REGION` whitespace 미정규화** [crawler/src/s3_uploader.py:18-20] — 운영 가이드로 흡수 가능.
- **BOM (`﻿`) 미stripping** [crawler/src/s3_uploader.py:30] — downstream S3 consumer 추가 시 재검토.

## Deferred from: code review of 2-5-apscheduler-기반-자동-크롤링-및-수동-트리거 (2026-04-29)

- **Sync `redis` client을 async event loop에서 사용** [crawler/src/scheduler/crawl_scheduler.py:162-163, crawler/src/queue/redis_publisher.py:11] — 매 LPUSH/sismember/sadd가 event loop을 block. 부하 측정 후 `redis.asyncio` 전면 전환 필요. architecture-level 변경.
- **`PostStorage.save` sync (boto3 포함)** [crawler/src/scheduler/crawl_scheduler.py:119-125] — S3 업로드가 async loop을 block. Story 2.4 작업. aioboto3 또는 `asyncio.to_thread` offload 검토.
- **APScheduler graceful shutdown 부재** [crawler/src/scheduler/crawl_scheduler.py:194-196] — `shutdown(wait=False)`이 in-flight 잡 orphan, SIGTERM 핸들링 없음. NFR10 24h 무중단 트랙(Epic 5).
- **APScheduler misfire 이벤트 미로깅** [crawler/src/scheduler/crawl_scheduler.py:174-184] — misfire 발생 시 가시성 zero. Story 5.1 Prometheus/Grafana와 함께 EVENT_JOB_MISSED listener 추가.
- **`AsyncWebCrawler` 매 board마다 instantiation — Chromium cold start** [crawler/src/scheduler/crawl_scheduler.py:33-36] — 성능 개선. board 단위 → site/run 단위 lifecycle로 전환 검토.
- **`CrawlEvent.detected_at` 시맨틱 모호 (실제는 "now")** [crawler/src/preprocessor/serializer.py] — downstream Detection Worker 영향 큼. Story 3.1+에서 fetched_at vs serialized_at 분리 결정.
- **`language_detector.detect` sync — 긴 텍스트 시 event loop block** [crawler/src/scheduler/crawl_scheduler.py:117] — sync redis defer와 동일 트랙. `asyncio.to_thread` 또는 별도 워커.

## Deferred from: code review of 1-2-공유-인터페이스-계약-및-구조화-로깅-수립 (2026-04-27)

- **requirements.txt -e ../shared 상대경로** — CI 환경/컨테이너에서 경로가 깨질 수 있음. Story 1.5 CI 구성 시 절대경로 또는 workspace 기반 방식으로 교체.
- **pyproject.toml where=[".."] 비표준 설정** — setuptools가 모노레포 루트를 스캔하는 비표준 구성. 실제 배포 환경에서 검증 필요.
- **CrawlEvent.raw_text 크기 제한 없음** — 대형 게시글이 Redis에 수 MB 메시지로 전송될 수 있음. 부하 테스트 시 메시지 크기 상한 정의 필요.
- **VarcoInterface 메서드 예외 계약 없음** — translate/classify의 실패 시 예외 타입 미정의. Story 3.2 VarcoInterface 구현 시 예외 계약 문서화.
- **Redis key 상수 네임스페이스 없음** — `"posts:queue"` 등 bare string이 환경 간 충돌 가능. Story 1.3 환경 설정 시 prefix 전략 결정.
- **get_logger 멀티스레드 경쟁 조건** — `if not logger.handlers:` 체크가 thread-safe하지 않아 핸들러 중복 추가 가능. 실운영 전 검토.
- **ClassificationResult.confidence 범위 검증 없음** — `[0.0, 1.0]` 외 값 수용. Story 3.3 VARCO 연동 시 API 응답 검증 추가.
- **TrackerBaseException str() 시 correlation_id 누락** — `str(exc)` 호출 시 message만 출력. 로그 사용 가이드에 `logger.error(str(e), extra={"correlation_id": e.correlation_id})` 패턴 문서화.

## Deferred from: code review of 2-2-proxyprovider-추상화-및-기본-크롤러-구현 (2026-04-28)

- **ParseResult.image_urls 가변 리스트** — `@dataclass(frozen=True)`임에도 `image_urls: list[str]` 필드는 내용 변경 가능. 현 MVP에서는 실질적 위험 없으나, Story 2.3+ 모델 안정화 시 `tuple[str, ...]`로 전환 검토.
- **parse_list 외부 도메인 document_srl 교차 오염** — `urljoin` 처리 후 외부 도메인 링크에 `?document_srl=N`이 포함된 경우 tailstar 게시글로 오분류 가능. Story 2.5 통합 테스트 시 실제 사이트 목록 페이지로 검증.
- **test_proxy_provider.py async_playwright 동기 MagicMock 취약성** — `monkeypatch.setattr("...async_playwright", lambda: MagicMock())`이 async context manager 계약을 위반. 현 NFR15 swap 검증 목적에는 충분하나, StealthBrowser 리팩토링 시 mock 구조 재검토 필요.

## Deferred from: code review of 2-3-콘텐츠-전처리-파이프라인-구현 (2026-04-28)

- **TOCTOU race in DedupChecker** — `is_duplicate`+`mark_seen`이 비원자적(SISMEMBER 후 SADD). 단일 워커에서는 무해하나, 멀티 워커 확장 시 중복 이벤트 발행 가능. Story 2.5+ 멀티 워커 구성 시 Redis pipeline 또는 SETNX 패턴으로 원자화 필요.
- **이미지 다운로드 메모리 크기 제한 없음** — `resp.content` 전체 버퍼링으로 대용량 이미지 응답 시 OOM 가능. 운영 배포 전 `Content-Length` 가드 또는 스트리밍 다운로드로 전환 필요.
- **`_base_run_config` shared object** — `crawl4ai_crawler.py`에서 `CrawlerRunConfig` 인스턴스를 공유 참조로 사용. crawl4ai가 config 객체를 내부적으로 변경하는 경우 동시 크롤링 시 경합 가능. crawl4ai 업그레이드 시 확인.
- **conftest sys.path 조작** — `tests/conftest.py`에서 `sys.path.insert`로 임포트 해결. 패키지 미설치 환경에서 CI 실패 가능. Story 1.5 CI 구성 시 `pip install -e .` 또는 `pyproject.toml` packages 선언으로 교체.
- **이미지 다운로드 레이트 리밋 없음** — `_download_images`가 순차 루프로 HTTP 요청. 미래 병렬화 시 비제한 flood 위험. asyncio Semaphore 또는 레이트 리밋 추가 필요.
- **브라우저 기동 타임아웃 없음** — `AsyncWebCrawler.__aenter__` 진입 시 타임아웃 미설정. Chromium 기동 hang 시 무한 대기. 운영 전 asyncio.wait_for 래핑 검토.
- **dedup 텍스트 Unicode 정규화 없음** — 동일 게시글이 NFC/NFD 또는 trailing whitespace 차이로 다른 SHA-256 해시 생성. 실운영 중복률 측정 후 필요 시 `unicodedata.normalize('NFC', text.strip())` 추가.
- **disabled 사이트 이미지 필터 과도한 확장(nga, pojie)** — `_nga_image_filter`에서 `"img"` 3글자 substring 매칭, `_pojie_image_filter`에서 유사 문제. Story 2.7 사이트 활성화 시 서브도메인 앵커링으로 수정 필요.
- **PTT post_id extractor `.html` suffix 포함** — 기본 `post_id_extractor`가 PTT URL에서 `M.1681234567.A.123.html` 반환. Story 2.6 PTT 구현 시 전용 extractor 정의 필요.
- **빈 raw_text CrawlEvent 발행** — `CrawlResult.markdown`이 빈 문자열인 경우 `raw_text=""`인 이벤트가 발행됨. Story 2.5 파이프라인에서 빈 이벤트 필터링 또는 경고 로그 추가 검토.
- **`CrawlerRunConfig` 수동 필드 복사** — css_selector 사용 시 `CrawlerRunConfig` 8개 필드를 수동 복사. crawl4ai 신규 필드 추가 시 silently drop됨. 라이브러리 업그레이드 시 수동 확인 필요.

## Deferred from: code review of 2-1-cloudflare-우회-가능성-검증 (2026-04-27)

- **하드코딩된 `Chrome/124` User-Agent 봇 탐지 지문화** — `crawler/src/browser/stealth_browser.py:15`. 이번 스파이크의 의도적 선택이나, 시간이 지남에 따라 구버전 UA로 봇 탐지율 증가. playwright 버전 핀 갱신 시 함께 업데이트 필요. Story 2.2+ 추적.
- **`Stealth().use_async(async_playwright())` 내부 CM 진입/탈출 보장 여부** — `crawler/src/browser/stealth_browser.py:57`. playwright-stealth 2.x 라이브러리가 `async_playwright()` CM을 올바르게 진입/탈출하는지 소스 검증 필요. 통합 테스트에서 Chromium 프로세스 누수 모니터링.
- **`response=None` 시 불충분한 오류 메시지** — `crawler/src/browser/stealth_browser.py:91`. `"unexpected HTTP status None"` 메시지로는 "서버 응답 없음" 원인 파악 불가. Story 2.2 리파인 시 개선.
- **`crawler/__init__.py` 추가로 잠재적 패키지 임포트 경로 충돌** — `crawler/__init__.py`. 모노레포 구조에서 의도된 배치이나, 배포 환경에서 동명 PyPI 패키지와 충돌 가능성 검토 필요.

## Deferred from: code review (Epic 4 프론트엔드, 2026-04-28)

- **RecentAlertList "High confidence" 헤딩 미스매치** [components/tracker/RecentAlertList.tsx:21] — heading은 high-confidence를 암시하지만 query에 confidence 필터 없음. 제품 결정: 헤딩을 "Recent"로 변경 vs query에 minConfidence 추가. 백엔드 필터 지원 후 결정.
- **Hero correlation pill (unique·중복) mock 데이터** [pages/Dashboard/index.tsx Hero] — `count - floor(count*0.3)` / `floor(count*0.3)` 산술은 fabricated. 실제 backend grouping 필드 추가 후 재구현 또는 제거.
- **REVIEWED_FRACTION 0.25 mock 라벨링** [pages/Dashboard/index.tsx:13] — 진척도 25% 고정 mock. Stats API에 reviewed count 필드 추가 시 swap.
- **Today timestamp 자정 롤오버** [pages/Dashboard/index.tsx:31] — `new Date()` 렌더 시점 1회 계산. TanStack Query refetch 시 갱신되지만 60s 폴링 사이에 자정 넘으면 표시 잔류. dataUpdatedAt + ticking state로 교체 필요.
- **FreshnessIndicator/NewDetectionsBadge 제거 회귀** [layouts/Topbar.tsx, layouts/RootLayout.tsx] — 새 Topbar에 freshness 표시 + 수동 트리거 후 새 탐지 알림 없음. Hero 시스템 상태 줄에 dataUpdatedAt 연결 또는 컴포넌트 복원 결정 필요.
- **3-column 레이아웃 모바일 breakpoint 부재** [layouts/RootLayout.tsx:20] — sidebar 240px + rail 240px 고정으로 ~600px 미만에서 main 압착. desktop-only 전제 명시 또는 < lg 에서 rail 드로어화 필요.

## Deferred from: code review of 1-1-모노레포-구조-초기화-및-서브시스템-스캐폴딩 (2026-04-29)

- **`build/` 패턴 무앵커** [`.gitignore`:27] — `api/build/`가 의도이나 미래 서브시스템의 `build/` 디렉토리도 자동 무시 가능. Story 1.5 CI 추가 시 앵커 필요 여부 재검토.
- **`dist/` 패턴 무앵커** [`.gitignore`:23] — `dashboard/dist/`가 의도이나 다른 서브시스템에서 `dist/` 규칙 채택 시 충돌 가능. 배포 아티팩트 전략 확정 시 `/dashboard/dist/`로 앵커링.

## Deferred from: code review of 1-3-로컬-개발-환경-구성 (2026-04-29)

- **redis/postgres `healthcheck:` 블록 미정의** [infra/docker-compose.yml] — `up -d` 직후 컨테이너가 Listening 되기 전 의존 서비스 부팅 시 race. Story 1.4 Flyway 마이그레이션이 `service_healthy` condition을 요구하므로 그때 일괄 추가.
- **VARCO_API_KEY required-var 가드 부재** [infra/.env.example, infra/docker-compose.yml] — placeholder `your-varco-api-key-here`가 그대로 사용되면 런타임 401로 fail. crawler/detection 컨테이너 추가 시 해당 서비스 environment에 `${VARCO_API_KEY:?}` 부착.
- **postgres `/docker-entrypoint-initdb.d` 마운트 슬롯 미예약** [infra/docker-compose.yml] — Story 1.4에서 `pg_trgm`/`uuid-ossp` 등 extension 필요 시 Flyway baseline에 포함하거나 initdb 마운트 추가 결정 필요.

## Deferred from: code review of 3-1-redis-큐-소비자-및-watchdog-구현 (2026-04-29)

- **Watchdog LREM/RPUSH 비원자성 (D1, decision-needed→defer)** [detection/src/consumer/watchdog.py:64-77] — race window는 ms 단위 + 단일 Watchdog MVP. Story 3.5 측정 후 발생률 기반 재결정.
- **같은 `post_id` 중복 메시지 LREM 오제거 가능성 (D3, decision-needed→defer)** [detection/src/consumer/queue_consumer.py:45, watchdog.py:65,76] — DedupChecker(SHA-256) + Story 3.4 DB UniqueConstraint 이중 안전망 존재. 단일 post_id 충돌 빈도 사실상 0.
- **`mark_processing` 침묵 실패** [detection/src/consumer/watchdog.py:35-45] — spec 명시 의도이나 정상 처리 중 메시지가 즉시 stale 판정되는 race window. spec 설계 유지.
- **`processing_time` TTL = stale 임계치 동일(300s)** [detection/src/consumer/watchdog.py:17] — VARCO 5분 초과 처리 시 stale 오판. Story 3.2 VARCO SLA 측정 후 TTL 분리 검토.
- **`run_forever` 예외 처리 부재** [detection/src/consumer/queue_consumer.py:64-65, watchdog.py:97-99] — Connection Error 시 프로세스 종료. Story 5.3 supervisor/restart 정책 확정 시 보완.
- **`brpoplpush` Redis 6.2+ deprecated** [detection/src/consumer/queue_consumer.py:32-36] — spec 명시 사용. 후속 라이브러리 업그레이드 시 `BLMOVE` 마이그레이션.
- **Watchdog 첫 스캔 60초 지연** [detection/src/consumer/watchdog.py:97-99] — 부팅 직후 잔존 stale 메시지 60초 방치. MVP 영향 미미.
- **다중 Watchdog 인스턴스 race 보호 부재** [detection/src/consumer/watchdog.py:62-77] — `get → incr` 비원자. spec 단일 Watchdog 가정. Epic 5 분산 락 검토.
- **환경변수 모듈 임포트 시점 캡처** [detection/src/consumer/queue_consumer.py:14-15, watchdog.py:16-19] — 통합 테스트 도입 시 함수형 전환.
- **`LRANGE 0 -1` 풀스캔** [detection/src/consumer/watchdog.py:49] — 운영 부하 발생 시 페이징/SCAN 도입.
- **단일 `redis.Redis` 메인/데몬 스레드 공유** [detection/src/main.py:22-29] — connection pool 명시 크기 미설정.
- **SIGTERM/SIGINT graceful shutdown 부재** [detection/src/main.py] — Story 5.3 시그널 핸들러 + drain 로직.
- **`_MAX_RETRIES` env 외부화 / off-by-one naming** [detection/src/consumer/watchdog.py:19] — 후속 개선.
- **`int(os.environ.get(...))` 검증 부재** [detection/src/consumer/queue_consumer.py:15, watchdog.py:17-18] — 운영 misconfig 가드 추가.
- **Watchdog `RPUSH` 재투입 우선순위 (poison priority inversion)** [detection/src/consumer/watchdog.py:75] — backoff 정책 도입 시 LPUSH 또는 별도 retry queue 검토.
- **`pytest.ini` 옵션 부재 / `process_fn` 시그니처 단순** — `addopts` 미정의, Story 3.2에서 비동기/컨텍스트 전달 필요 시 변경.

## Deferred from: code review of 1-5-github-actions-기본-ci-파이프라인-구성 (2026-04-29)

- **Branch Protection strict merge gate / AC #5** [docs/ci-setup.md:17] — Story 1.5의 4개 workflow는 `paths:` 필터가 있어 required check로 직접 등록하면 무관 경로 PR에서 skipped check가 pending으로 남을 수 있다. Strict PR merge blocking은 Story 5.2에서 항상 실행되는 `ci-aggregator.yml` 또는 동등한 required check 설계로 처리한다.
