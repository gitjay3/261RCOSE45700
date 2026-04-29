# Story 2.2: ProxyProvider 추상화 및 기본 크롤러 구현

Status: done

> 🎯 **본 스토리 핵심:** Story 2.1 스파이크에서 채택된 `StealthBrowser`를 기반으로, **(1) ProxyProvider Protocol 정의 + ProxyBroker 기본 구현**, **(2) BaseSite 추상 + tailstar.py 첫 어댑터**, **(3) 사이트 다운/429/timeout 예외 처리와 단위 테스트**를 완성하여 Story 2.3(전처리)·2.6/2.7(다중 사이트 어댑터)이 의존할 수집 골격을 만든다.
>
> **변경 없는 사전 결정 (Story 2.1 §6):** epics.md SPIKE 2.1 / Story 2.2 AC는 **그대로 유지**. stealth 채택이 확정되어 본 스토리는 stealth 기준으로 진행.

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

개발자로서,
ProxyProvider 인터페이스와 첫 번째 사이트(`tailstar.net`) 크롤러가 구현되기를 원한다,
그래서 (a) MVP 단계에서는 프록시 없이도 핵심 크롤 로직을 개발·테스트할 수 있고, (b) Growth 단계에서 `ProxyBroker → NodeMaven`으로 교체할 때 `stealth_browser.py`/사이트 어댑터 코드 수정이 0줄이 된다 (NFR15).

## Acceptance Criteria

1. **Given** `crawler/src/proxy/proxy_provider.py`에 `ProxyProvider` Protocol(또는 ABC)이 정의된 상태에서, **When** `ProxyBroker` 구현체가 `ProxyProvider`를 상속하면, **Then** `ProxyBroker`를 미래 `NodeMaven` 구현체로 교체할 때 `crawler/src/browser/stealth_browser.py` 및 `crawler/src/sites/*.py`의 코드 수정이 불필요하다 (NFR15). 교체 비용 0을 증명하기 위해 `crawler/tests/unit/test_proxy_provider.py`에서 더미 `_FakeProxyProvider`로 `StealthBrowser`/`TailstarSite`가 동일하게 동작함을 검증한다.
2. **Given** `crawler/src/sites/base_site.py`가 작성될 때, **Then** `parse(html: str) -> ParseResult` 추상 메서드를 정의하며, 파싱 실패 시 `None` 반환 대신 `ParseError`(`shared.exceptions.base_exception.CrawlerException`의 서브클래스)를 raise한다 (architecture P10, Cross-Cutting #5). `ParseResult`는 `dataclass`로 `post_id`, `title`, `body_text`, `image_urls`, `posted_at`, `source_url` 필드를 갖는다.
3. **Given** `crawler/src/sites/tailstar.py`가 `BaseSite`를 상속할 때, **Then** `parse_list(html) -> list[PostListItem]`(목록 페이지의 게시글 메타: `post_id`, `url`, `title`)와 `parse(html) -> ParseResult`(상세 페이지의 본문)가 구현되어 `tailstar.net`의 실제 HTML 구조를 처리한다. 본문 추출은 `beautifulsoup4`(이미 `requirements.txt`에 선언) 사용.
4. **Given** `tests/fixtures/html/sample_illegal_post.html`이 본 스토리에서 신규 생성되어 tailstar.net 실제 게시글 HTML 구조(필요한 셀렉터 — 제목, 본문, 이미지)를 담을 때, **When** `crawler/.venv/bin/pytest crawler/tests/unit/test_html_parser.py`를 실행하면, **Then** `TailstarSite().parse(fixture_html)`가 기대 `ParseResult`(제목·본문 텍스트 일부 매칭, `image_urls` 0건 이상)을 반환하고, 잘못된 HTML(빈 문자열, 스켈레톤만 있는 HTML)에 대해서는 `ParseError`를 raise한다.
5. **Given** 사이트 다운(HTTP 5xx), rate limit(HTTP 429), navigation timeout 시나리오에서, **When** `TailstarSite().fetch_and_parse(url, correlation_id=...)`가 호출되면, **Then** 각각 `BrowserError`(stealth_browser가 raise) 또는 `RateLimitError`(`CrawlerException` 서브클래스)가 적절히 전파되며, `crawler/tests/unit/test_browser.py` 또는 신규 `crawler/tests/unit/test_tailstar.py`에 각 케이스(5xx / 429 / timeout) 단위 테스트가 1건씩(총 ≥ 3건) 존재한다. 외부 네트워크 의존 0 (mock 기반).
6. **Given** Story 2.1에서 채택된 `StealthBrowser`의 시그니처가 `fetch_html(url, *, correlation_id) -> str`로 고정된 상태에서, **When** `TailstarSite`가 `StealthBrowser`(또는 `BaseSite`가 의존성으로 받은 fetch 객체)를 호출하면, **Then** `StealthBrowser` **본체 코드는 수정되지 않는다**. 만약 `ProxyProvider`를 받기 위한 생성자 확장이 불가피하면 **추가 생성자 인자(기본값 `None`)** 형태로 backward compatible하게 변경하고, Story 2.1의 6개 단위 테스트(`crawler/tests/unit/test_browser.py`)가 그대로 통과해야 한다.
7. **Given** 본 스토리 완료 시점에, **When** `cd crawler && ./.venv/bin/pytest` 전체 실행하면, **Then** Story 2.1의 기존 6 테스트 + 본 스토리 신규 테스트(test_proxy_provider, test_html_parser, test_tailstar 합계)가 모두 PASS하며, 외부 네트워크 호출 0건이다.

> **AC 출처:** epics.md L306-L320 (Story 2.2). AC 6·7은 Story 2.1 학습("stealth_browser.py 본체 손대지 말 것" + "테스트 회귀 방지")에서 보강된 가드레일이며, 원본 epic AC의 NFR15·테스트 요건을 더 구체화한 것이다.

## Tasks / Subtasks

- [x] **Task 1: ProxyProvider 추상화 정의** (AC: #1)
  - [x] 1.1 `crawler/src/proxy/__init__.py` 신규 (재노출 — Task 1.4 통합)
  - [x] 1.2 `crawler/src/proxy/proxy_provider.py` 신규 — `typing.Protocol` + `@runtime_checkable` 채택. `ProxyConfig`는 `frozen=True dataclass`. `get_proxy(*, correlation_id) -> ProxyConfig | None` 1개 메서드.
  - [x] 1.3 `crawler/src/proxy/proxy_broker.py` 신규 — `class ProxyBroker`. 환경변수 미설정 시 `None` 반환. SDK 호출 미포함(Story 2.5/2.6 확장). nominal subclassing 없이 Protocol 충족 (NFR15 덕 타이핑 검증).
  - [x] 1.4 `crawler/src/proxy/__init__.py`에서 `ProxyProvider`, `ProxyConfig`, `ProxyBroker` 재노출 (`__all__` 명시).
  - [x] 1.5 `crawler/.env.example`에 `PROXY_BROKER_HOST/USER/PASS` 3개 추가, Story 1.3 placeholder 보존.

- [x] **Task 2: BaseSite + ParseResult + ParseError 정의** (AC: #2)
  - [x] 2.1 `crawler/src/sites/__init__.py` 신규 (재노출 — Task 3.2 통합)
  - [x] 2.2 `crawler/src/sites/base_site.py` 신규:
    - `@dataclass class ParseResult` — `post_id: str, title: str, body_text: str, image_urls: list[str], posted_at: str | None, source_url: str`
    - `@dataclass class PostListItem` — `post_id: str, url: str, title: str`
    - `class ParseError(CrawlerException)` — Story 1.2의 `CrawlerException` 상속, `correlation_id` 인자 그대로 전달. **AC 비호환 ❌**: `ParseError`를 `BrowserError`와 같은 모듈에 선언 금지(import 순환 + 책임 분리 명확).
    - `class RateLimitError(CrawlerException)` — HTTP 429 또는 사이트별 차단 응답 시 raise.
    - `class BaseSite(ABC)`:
      - 생성자: `def __init__(self, *, browser: StealthBrowser | None = None, proxy_provider: ProxyProvider | None = None)`. browser/proxy 미주입 시 기본값 생성(테스트에서 mock 주입 가능하도록 DI).
      - `@abstractmethod def parse(self, html: str) -> ParseResult` — `None` 반환 금지, 실패 시 `ParseError` raise (architecture.md P10).
      - `@abstractmethod def parse_list(self, html: str) -> list[PostListItem]`
      - `async def fetch_and_parse(self, url: str, *, correlation_id: str) -> ParseResult` — `browser.fetch_html()` 호출 후 `parse()`. `BrowserError`/`ParseError`는 그대로 전파(silent failure 방지).
  - [x] 2.3 `BaseSite` 직접 테스트 미작성, `TailstarSite` 통해 간접 검증(Task 4.2/4.3).

- [x] **Task 3: TailstarSite 구현** (AC: #3, #5, #6)
  - [x] 3.1 `crawler/src/sites/tailstar.py` 신규 — `class TailstarSite(BaseSite)`.
    - 클래스 변수: `BASE_URL = "https://tailstar.net"`, `LIST_PATH = "/index.php?mid=board_main"` (실제 경로는 spike 결과 또는 사이트 탐색으로 확정. spike에서 `/`만 검증되었으므로 본 스토리에서 게시판 URL을 1개 식별해 클래스 상수로 고정).
    - `parse_list(html)`: BeautifulSoup으로 게시글 목록 추출. 각 항목 → `PostListItem`. 실패(목록이 0건이고 사이트 다운 의심) 시 `ParseError`.
    - `parse(html)`: 게시글 상세 페이지 → `ParseResult`. `title`, `body_text`(광고/네비게이션 제거 여부는 Story 2.3 `html_parser.py`로 위임 — 본 스토리는 raw 추출만), `image_urls`(`<img>` 태그의 절대 URL).
    - **HTTP 429 감지**: `fetch_and_parse`를 오버라이드하지 말고, `parse()` 내부에서 응답 HTML이 사이트별 차단 페이지(예: tailstar의 "잠시 후 다시 시도" 같은 마커)를 감지하면 `RateLimitError` raise. 단순 HTTP status 429는 `StealthBrowser.fetch_html()`이 이미 `BrowserError`로 변환함(2.1 구현). 본 스토리는 그 위에 사이트별 마커 감지 추가만.
  - [x] 3.2 `crawler/src/sites/__init__.py`에서 `TailstarSite`, `BaseSite`, `ParseResult`, `PostListItem`, `ParseError`, `RateLimitError` 재노출.
  - [x] 3.3 `StealthBrowser` 본체 비변경 확정 — `git diff crawler/src/browser/stealth_browser.py` 결과 0줄. ProxyProvider는 `BaseSite` 생성자에서 받아 처리하므로 stealth_browser DI 변경 불필요.

- [x] **Task 4: 테스트 fixture 및 단위 테스트** (AC: #4, #5, #7)
  - [x] 4.1 `tests/fixtures/html/sample_illegal_post.html` 신규 — 합성 HTML 채택. spike에서 관찰된 셀렉터(meta[name=Generator][content*=XpressEngine], og:title/url/image, document_xe_content) 포함. 가공의 "매크로 판매" 게시글로 Story 2.3 키워드 필터 사전 자료도 겸함.
  - [x] 4.2 `crawler/tests/unit/test_html_parser.py` 신규 — fixture 읽어 `TailstarSite().parse(html)` 호출. 검증 8건(fixture 존재, 정상 파싱, parse_list 추출, 빈 HTML/제목 누락/본문 누락/parse_list 빈/네비 링크만 있음 케이스의 ParseError).
  - [x] 4.3 `crawler/tests/unit/test_tailstar.py` 신규 — 예외 시나리오 3건 + happy path:
    - **5xx**: `mock_browser.fetch_html` `AsyncMock(side_effect=BrowserError("HTTP 500", correlation_id="t-5xx"))` → `TailstarSite(browser=mock_browser).fetch_and_parse(...)`가 `BrowserError` raise.
    - **429 (사이트 차단 페이지 마커)**: 차단 페이지 HTML을 `mock_browser.fetch_html`이 반환하도록 mock → `parse()`가 `RateLimitError` raise.
    - **timeout**: `mock_browser.fetch_html` `AsyncMock(side_effect=BrowserError("playwright navigation timed out...", correlation_id="t-to"))` → `BrowserError` 전파.
    - 모든 예외 케이스에서 `correlation_id` 보존 검증 완료.
  - [x] 4.4 `crawler/tests/unit/test_proxy_provider.py` 신규 — Protocol 호환성 + NFR15 swap 검증 7건 (frozen dataclass, FakeProvider isinstance, env unset/set, ProxyBroker isinstance, swap 동치성, correlation_id 전파).
  - [x] 4.5 `cd crawler && ./.venv/bin/pytest -v` → **25 passed in 0.12s** (Story 2.1 기존 6 + test_html_parser 8 + test_tailstar 4 + test_proxy_provider 7).

- [x] **Task 5: 문서 및 코드 일관성 점검** (AC: #1, #2, #6)
  - [x] 5.1 `crawler/src/proxy/__init__.py`, `crawler/src/sites/__init__.py` 신규 (재노출 포함). `from crawler.src.sites.tailstar import TailstarSite` 임포트 정상 작동 (test_*.py 25 PASS로 검증).
  - [x] 5.2 `ParseError`, `RateLimitError` 모두 `CrawlerException` 상속, `correlation_id` 인자 부모 위임 (TrackerBaseException 시그니처 그대로 사용).
  - [x] 5.3 모든 신규 모듈(`proxy_broker.py`, `base_site.py`, `tailstar.py`)에 `_SERVICE_NAME` 상수 + `extra={"correlation_id": ..., "service": _SERVICE_NAME}` 패턴 적용.
  - [x] 5.4 새 third-party 의존성 0건. `requirements.txt`/`requirements-dev.txt`/`pytest.ini` 비변경.

- [x] **Task 6: 마무리 및 sprint-status 갱신**
  - [x] 6.1 dev 시작 시 `Status: ready-for-dev → in-progress` 갱신.
  - [x] 6.2 dev 완료 시 `Status: in-progress → review`, sprint-status.yaml `2-2: in-progress → review`.
  - [x] 6.3 Story 2.6/2.7가 동일 `BaseSite`+`ProxyProvider` 패턴 확장하도록 인터페이스 안정화 완료. 본 스토리는 epic AC 영향 없음.

### Review Findings

- [x] [Review][Patch] HTTP 429 → BrowserError 설계 수용 — `test_tailstar.py`에 `test_fetch_and_parse_propagates_browser_error_on_429_status` 추가 및 AC #5 해석 docstring 명시. [`crawler/tests/unit/test_tailstar.py`]
- [x] [Review][Patch] `hash()` 비결정적 fallback post_id — `hashlib.md5(title.encode()).hexdigest()[:8]`로 교체. PYTHONHASHSEED 영향 차단. [`crawler/src/sites/tailstar.py`]
- [x] [Review][Patch] ParseError/RateLimitError에 correlation_id 미전달 — `fetch_and_parse`에서 `CrawlerException` catch 후 `exc.correlation_id` 보강하여 재raise. [`crawler/src/sites/base_site.py`]
- [x] [Review][Patch] PROXY_BROKER_HOST 공백 문자 미처리 — `host = os.environ.get(..., "").strip() or None` 패턴으로 수정. [`crawler/src/proxy/proxy_broker.py`]
- [x] [Review][Patch] Proxy resolve 후 브라우저 미전달 — 로그 메시지를 `proxy_resolved_deferred`로 교체, `# TODO Story 2.5` 주석 추가. [`crawler/src/sites/base_site.py`]
- [x] [Review][Patch] 상대 og:url을 이미지 base로 사용 — `source_url.startswith("http")` 검증 후 BASE_URL 폴백 적용. [`crawler/src/sites/tailstar.py`]
- [x] [Review][Patch] `html.lower()` 루프 내 반복 재계산 — `html_lower = html.lower()` 사전 계산으로 최적화. [`crawler/src/sites/tailstar.py`]
- [x] [Review][Defer] ParseResult.image_urls 가변 리스트 (frozen=True임에도 내부 list 변경 가능) [`crawler/src/sites/base_site.py:38`] — deferred, 현 MVP 사용 패턴에서 실질적 위험 없음. Story 2.3+ 모델 안정화 시 tuple 전환 검토
- [x] [Review][Defer] parse_list 외부 도메인 document_srl 교차 오염 가능성 [`crawler/src/sites/tailstar.py:55-67`] — deferred, Story 2.5 통합 테스트 단계에서 실제 사이트 테스트로 확인
- [x] [Review][Defer] test_proxy_provider.py async_playwright 동기 MagicMock 취약성 [`crawler/tests/unit/test_proxy_provider.py:28`] — deferred, 현 NFR15 검증 목적에 충분. StealthBrowser 리팩토링 시 재검토

## Dev Notes

### 본 스토리 범위 (Scope Boundary — 가장 중요)

| 이번 스토리에서 한다 | 이번 스토리에서 **하지 않는다** |
|---|---|
| ProxyProvider Protocol + ProxyBroker 더미 구현 | ProxyBroker SDK 실제 연동 → Story 2.5/2.6 (실측 기반 NodeMaven 도입 시점) |
| BaseSite 추상화 + tailstar.py 1개 어댑터 | PTT/Dcard/tieba/52pojie/NGA 어댑터 → Story 2.6/2.7 |
| `parse()` raw HTML 추출 (제목/본문/이미지 URL) | 광고/네비게이션 제거, 언어 감지, dedup, 키워드 필터 → Story 2.3 |
| 5xx/429/timeout 예외 전파 단위 테스트 | APScheduler 통합, Redis publisher → Story 2.5 |
| `StealthBrowser` 재사용 (코드 비변경) | S3 업로드, 이미지 다운로드 → Story 2.4 |
| `tests/fixtures/html/sample_illegal_post.html` 신규 (합성) | Flyway 스키마, VARCO mock → Story 1.4 |

**왜 이 경계가 중요한가:** Story 2.2가 BaseSite·ProxyProvider 추상화의 기준을 정한다. 5개 사이트 어댑터를 같이 짜기 시작하면 (a) 추상화가 첫 사이트에 과적합되거나, (b) 너무 일반화되어 unused 메서드가 생긴다. **1 사이트 + 1 fixture로 추상화의 fit을 검증**한 뒤 Story 2.6/2.7에서 다른 사이트가 들어올 때 자연스럽게 일반화한다(YAGNI).

### Project Context

- **저장소 루트**: `tracker/` 역할 (실제로는 `20261R0136COSE45700/`).
- **Story 1.1**: 모노레포 스캐폴딩. `crawler/.venv` 생성, `crawler/__init__.py` (Story 2.1에서 보강), `crawler/src/__init__.py` 존재.
- **Story 1.2**: `shared/` 완성. `from shared.exceptions.base_exception import CrawlerException`, `from shared.structured_logger import get_logger` 동작 검증 완료.
- **Story 2.1 (직전)**: `crawler/src/browser/stealth_browser.py` (StealthBrowser), `crawler/src/browser/__init__.py`, `crawler/tests/unit/test_browser.py` (6 tests passed), `docs/cloudflare-spike-result.md` 완성. **stealth 채택 확정 → 본 스토리는 stealth 기준으로 진행**.
- **본 스토리의 Day 1 의존성**: 위 모두 충족됨. `crawler/.venv/bin/pytest` 실행 가능 상태.
- **`tests/fixtures/html/`**: `.gitkeep`만 존재. 본 스토리에서 첫 fixture 추가.
- **`crawler/.env.example`**: 1줄 placeholder. Story 1.3 정식 작성 예정이지만, 본 스토리 동작에 필요한 PROXY 키 3개 추가는 허용 (회귀 위험 0).
- **sprint-status.yaml 현황**: epic-2: in-progress, 2-1: done, 2-2: backlog → ready-for-dev (본 스토리 생성 시).

### Technical Stack Decisions

| 항목 | 결정 | 근거 |
|---|---|---|
| ProxyProvider 추상화 형태 | `typing.Protocol` + `@runtime_checkable` | (a) 덕 타이핑으로 미래 NodeMaven SDK가 nominal subclassing 없이 자동 호환. (b) 단위 테스트에서 `_FakeProxyProvider`가 별도 상속 없이 인식. (c) ABC 대비 가벼움. **단점**: 런타임 isinstance 체크가 메서드 존재 여부만 봄(시그니처 불일치 미탐) → 본 스토리는 단순 `get_proxy()` 1개라 충분. |
| HTML 파서 | `beautifulsoup4` (이미 `requirements.txt`) | architecture.md L113 명시. lxml 백엔드 미강제(설치 시점에 결정). |
| ParseResult 형태 | `@dataclass` (Pydantic 미사용) | crawler 내부 전용 모델은 dataclass로 충분. Pydantic은 `shared/models/crawl_event.py`(Redis 메시지 스키마)에서만 검토 필요. 본 스토리는 in-process 전달이라 dataclass가 가벼움. |
| 예외 위치 | `crawler/src/sites/base_site.py`에 `ParseError`, `RateLimitError` 정의 | architecture.md L596-597 `shared/exceptions/base_exception.py`에는 `CrawlerException` base만. 사이트 파싱 도메인 예외는 도메인 모듈에 둬야 import 순환 방지. |
| 테스트 mock 라이브러리 | `unittest.mock.AsyncMock` + `MagicMock` (Story 2.1과 동일) | `respx`/`pytest-httpx` 도입은 본 스토리 범위 외(`StealthBrowser`가 이미 mock됨). |
| `tests/fixtures/html/sample_illegal_post.html` | **합성 HTML** (라이브 캡처 ❌) | (a) 사이트 변경 시 fixture가 깨지지 않게 격리. (b) 저작권/PII 회피. (c) spike에서 관찰된 셀렉터(`<title>`, `meta[name=Generator]`)만 포함하면 충분. 라이브 검증은 Story 2.5 통합 테스트에서 별도로. |
| `BaseSite.fetch_and_parse` async | async 유지 | `StealthBrowser.fetch_html`이 async (Story 2.1). 동기로 감싸면 event loop 중첩 위험. APScheduler(2.5)에서는 `asyncio.run` 또는 `AsyncIOExecutor` 필요. |

### Architecture Compliance Notes

- **architecture.md P10 (Python 예외 처리, L385-394)** — `parse()`/`parse_list()`/`fetch_and_parse()` 모두 실패 시 `None` 반환 금지. `ParseError`/`BrowserError`/`RateLimitError` 중 하나로 raise. 본 스토리의 가장 중요한 가드레일. Story 2.1의 `BrowserError(CrawlerException)` 패턴을 그대로 확장.
- **architecture.md P6 (구조화 로그 표준 스키마, L322-335)** — 모든 fetch/parse 시도 로그에 `correlation_id`, `service` 포함. `service`는 `_SERVICE_NAME = os.environ.get("SERVICE_NAME", "crawler")` 모듈 상수.
- **architecture.md NFR15 (L424, ProxyProvider 추상화)** — ProxyBroker → NodeMaven 교체 시 `crawler/src/browser/stealth_browser.py` 및 `crawler/src/sites/*.py` 코드 수정 0줄. 본 스토리 AC #1·#6의 핵심 가드. **검증 방법**: `_FakeProxyProvider`로 swap 시 `TailstarSite` 동작 동일성 단위 테스트.
- **architecture.md Cross-Cutting #5 (L70, Silent Failure 방지)** — Cloudflare 차단 시 빈 HTML이 파이프라인을 통과하지 않도록 `BrowserError` raise (Story 2.1에서 이미 처리). 본 스토리는 그 위에 사이트별 차단 페이지(rate limit) 마커 감지를 추가하여 두 번째 silent failure 경로 차단.
- **architecture.md L461-463 (proxy/ 디렉토리)** — `proxy_provider.py` (Protocol), `proxy_broker.py` (구현). `proxy_node_maven.py`는 본 스토리 범위 외 (Growth 단계).
- **architecture.md L453-457 (sites/ 디렉토리)** — `base_site.py`, `tailstar.py`만 본 스토리. `ptt.py`, `tieba.py` 등은 Story 2.6/2.7.
- **architecture.md L70 + L80 (프록시 추상화 NFR15)** — 중국 사이트 크롤링 성공률 SLA 정의는 Story 2.7 범위. 본 스토리는 인터페이스만 안정화.

### Library / Framework Requirements

| 라이브러리 | 버전 | 출처 | 본 스토리 사용 |
|---|---|---|---|
| Python | 3.11+ | architecture.md L148 | 런타임 |
| playwright | `==1.58.0` | architecture.md L112 (핀) | StealthBrowser 재사용 (직접 import 금지, `crawler.src.browser.stealth_browser`로 간접 사용) |
| playwright-stealth | `==2.0.3` | crawler/requirements.txt | 동일 (간접) |
| beautifulsoup4 | (제약 없음) | crawler/requirements.txt | HTML 파싱 |
| pytest | `==9.0.3` | crawler/requirements-dev.txt | 단위 테스트 |
| pytest-asyncio | `==1.3.0` | crawler/requirements-dev.txt, `asyncio_mode = strict` | async 테스트 |
| shared | `-e ../shared` (deferred 이슈 있음) | crawler/requirements.txt | `CrawlerException`, `get_logger` |

**의존성 추가 금지** — 본 스토리는 새 third-party 의존성 0건. `lxml` 등 BeautifulSoup 백엔드 명시도 본 스토리 범위 외.

### File Structure Requirements

```
crawler/
├── requirements.txt             ← 변경 없음 (이미 beautifulsoup4 선언)
├── .env.example                 ← 수정 (PROXY_BROKER_HOST/USER/PASS 3개 추가)
└── src/
    ├── proxy/                   ← 신규 디렉토리 (Task 1)
    │   ├── __init__.py          ← 신규 (재노출)
    │   ├── proxy_provider.py    ← 신규 (Protocol + ProxyConfig dataclass)
    │   └── proxy_broker.py      ← 신규 (기본 구현, env 미설정 시 None)
    └── sites/                   ← 신규 디렉토리 (Task 2)
        ├── __init__.py          ← 신규 (재노출)
        ├── base_site.py         ← 신규 (BaseSite ABC + ParseResult/PostListItem dataclass + ParseError/RateLimitError 예외)
        └── tailstar.py          ← 신규 (TailstarSite)

crawler/tests/unit/
├── test_browser.py              ← 변경 없음 (Story 2.1, 6 tests 회귀 방지)
├── test_proxy_provider.py       ← 신규 (Task 4.4)
├── test_html_parser.py          ← 신규 (Task 4.2, fixture 기반)
└── test_tailstar.py             ← 신규 (Task 4.3, 5xx/429/timeout 3 cases)

tests/fixtures/html/
└── sample_illegal_post.html     ← 신규 (합성 HTML, Task 4.1)
```

**비변경 파일 (회귀 방지 가드):**
- `crawler/src/browser/stealth_browser.py` — AC #6. 변경 0줄. 만약 ProxyProvider DI 위해 변경 불가피 시 **생성자에 `proxy_provider=None` 추가만** 허용.
- `crawler/src/browser/__init__.py` — 재노출 그대로.
- `crawler/tests/unit/test_browser.py` — 6 tests 그대로 통과해야 함.
- `crawler/requirements.txt`, `crawler/requirements-dev.txt`, `crawler/pytest.ini` — 변경 없음.
- `shared/` 전체 — 변경 없음 (Story 1.2 deferred 항목은 별도 PR).

### Testing Requirements

- **외부 네트워크 의존 0** (Story 2.1 패턴 동일). `tailstar.net`에 실제 요청 금지. fixture HTML로만 검증.
- **테스트 임포트 경로**: `from crawler.src.sites.tailstar import TailstarSite` (Story 2.1 `from crawler.src.browser.stealth_browser import StealthBrowser` 패턴과 동일). `crawler/__init__.py`, `crawler/src/__init__.py`, 신규 `crawler/src/sites/__init__.py`, `crawler/src/proxy/__init__.py` 모두 존재해야 임포트 동작.
- **fixture 로드 패턴**:
  ```python
  from pathlib import Path
  FIXTURE_DIR = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "html"
  # crawler/tests/unit/test_html_parser.py → ../../../tests/fixtures/html/
  # = repo_root/tests/fixtures/html/sample_illegal_post.html
  ```
  모노레포 루트 기준 상대 경로. `pytest.ini`의 `testpaths = tests` (crawler/tests 한정)와 무관.
- **AsyncMock 패턴 (Story 2.1 test_browser.py 참고)**:
  ```python
  from unittest.mock import AsyncMock
  from crawler.src.browser.stealth_browser import BrowserError, StealthBrowser
  from crawler.src.sites.tailstar import TailstarSite

  @pytest.mark.asyncio
  async def test_tailstar_propagates_browser_error_on_5xx():
      mock_browser = AsyncMock(spec=StealthBrowser)
      mock_browser.fetch_html.side_effect = BrowserError(
          "unexpected HTTP status 500 for https://tailstar.net/...",
          correlation_id="t-5xx",
      )
      site = TailstarSite(browser=mock_browser)
      with pytest.raises(BrowserError) as exc_info:
          await site.fetch_and_parse("https://tailstar.net/post/1", correlation_id="t-5xx")
      assert exc_info.value.correlation_id == "t-5xx"
  ```
- **Protocol isinstance 검증 패턴**:
  ```python
  from typing import runtime_checkable
  from crawler.src.proxy.proxy_provider import ProxyProvider, ProxyConfig

  class _FakeProxy:
      def get_proxy(self, *, correlation_id: str) -> ProxyConfig | None:
          return ProxyConfig(server="http://fake:8080", username=None, password=None)

  def test_fake_proxy_is_recognized_as_proxy_provider():
      assert isinstance(_FakeProxy(), ProxyProvider)  # @runtime_checkable
  ```
- **회귀 방지**: `cd crawler && ./.venv/bin/pytest -v` → Story 2.1의 6 tests + 신규 ≥7 tests = 총 ≥13 PASS.

### Previous Story Intelligence (Story 2.1)

본 스토리는 Story 2.1의 산출물에 직접 의존하므로 학습 항목을 중점 반영:

1. **`crawler/__init__.py` 누락 보강 패턴** (Story 2.1 Completion Notes) — 본 스토리도 신규 패키지(`sites/`, `proxy/`) `__init__.py`를 명시적으로 추가. 누락 시 `from crawler.src.sites...` 임포트 실패.
2. **`StealthBrowser.fetch_html(url, *, correlation_id) -> str` 시그니처 고정** — keyword-only `correlation_id` 인자. 본 스토리 `BaseSite.fetch_and_parse`도 동일 패턴(`*, correlation_id`).
3. **`BrowserError(CrawlerException)` 예외 패턴** — `correlation_id` 인자 보존. 본 스토리 `ParseError`, `RateLimitError`도 같은 패턴 강제.
4. **`_SERVICE_NAME = os.environ.get("SERVICE_NAME", "crawler")` 모듈 상수** — 모든 로그 `extra`에 포함. 본 스토리 신규 모듈 모두 동일.
5. **`empty HTML도 BrowserError raise`** — Story 2.1 코드 리뷰에서 추가된 silent failure 방지. `parse()`도 동일 원칙: 빈/스켈레톤 HTML → `ParseError`.
6. **headed 모드 측정은 사람이 함** — 단위 테스트는 mock만. 본 스토리도 동일.
7. **playwright-stealth 2.x API**: `Stealth().use_async()` async context manager. 본 스토리는 직접 호출하지 않으므로 무관.
8. **`pytest-asyncio==1.3.0`, `asyncio_mode = strict`** — 모든 async 테스트에 `@pytest.mark.asyncio` 명시 필요.
9. **`-e ../shared` 상대경로 deferred** — 본 스토리도 영향 없음. 별도 PR.
10. **Story 2.1 deferred — `response=None` 시 오류 메시지 불충분** (deferred-work.md L18) — 본 스토리에서 `StealthBrowser` 메시지 개선은 **하지 않는다**. AC #6 위반(stealth_browser.py 비변경) 방지. 만약 `parse()`에서 동일 문제(빈 HTML → 메시지 부족) 발견 시 `ParseError`에 충분한 컨텍스트(URL, HTML 앞 100자) 포함.

### Anti-Patterns to Avoid (이번 스토리 특화)

1. ❌ **`StealthBrowser` 본체 코드 수정** — AC #6. ProxyProvider DI를 위한 생성자 인자 추가만 허용(기본값 `None`). 메서드 시그니처/로직 변경 금지. Story 2.1의 6 tests가 회귀하면 즉시 알람.
2. ❌ **`parse()` 실패 시 `None`/빈 dict 반환** — architecture P10. `ParseError` raise 강제. 빈 HTML도 raise.
3. ❌ **`crawler/src/sites/base_site.py`에 `ProxyConfig`, `ProxyProvider` 정의** — 책임 분리 위반. proxy 도메인은 `crawler/src/proxy/`에만.
4. ❌ **PTT/Dcard/tieba 어댑터 작성** — Story 2.6/2.7 범위. 본 스토리는 `tailstar.py` 1개. **단**, `BaseSite` 추상 메서드가 PTT의 세션 인증, Dcard의 JS 렌더링까지 미리 포괄하려 하면 over-abstraction 트랩. 추상화는 첫 사이트 fit만 검증, 일반화는 2.6/2.7에서.
5. ❌ **`html_parser.py`(전처리) 작성** — Story 2.3 범위. 본 스토리 `parse()`는 raw 추출만(제목/본문 텍스트/이미지 URL). 광고 제거, 언어 감지, dedup, 키워드 필터는 Story 2.3.
6. ❌ **APScheduler 통합, Redis publisher 작성** — Story 2.5. 본 스토리는 `fetch_and_parse(url, *, correlation_id)` 1회 호출 가능한 상태까지만.
7. ❌ **S3 업로드, 이미지 다운로드** — Story 2.4. 본 스토리 `parse()`는 `image_urls`(URL 리스트)만 추출, 다운로드/업로드 없음.
8. ❌ **단위 테스트에서 실제 `tailstar.net` 호출** — Story 2.1과 동일. CI에서 IP 차단 + flaky.
9. ❌ **`ProxyBroker`에 실제 SDK 호출 코드** — Story 2.5/2.6에서 실측 기반 도입. 본 스토리는 인터페이스가 안정적임만 증명. 환경변수 미설정 시 `None` 반환으로 충분.
10. ❌ **`tests/fixtures/html/sample_illegal_post.html`을 라이브 캡처로 만들기** — 사이트 변경 시 fixture가 깨짐. 합성 HTML로 셀렉터만 정확히 흉내.
11. ❌ **`Pydantic` 도입** — `dataclass`로 충분. 새 의존성 0건이 본 스토리 가드.
12. ❌ **`-e ../shared` 상대경로 fix 시도** — Story 2.1 deferred. 본 스토리 범위 외.
13. ❌ **`shared/exceptions/base_exception.py`에 `ParseError` 추가** — `CrawlerException`은 base만. 도메인 예외는 각 도메인 모듈(`crawler/src/sites/base_site.py`)에.
14. ❌ **`async def parse(html)`** — 파싱은 동기. async는 fetch만. parse async화는 IO가 0인 작업에 event loop 오버헤드만 추가.

### Latest Tech Information (2026-04 기준)

- **`typing.Protocol` + `@runtime_checkable`** (PEP 544, Python 3.8+, 본 프로젝트 3.11+) — 메서드 존재만 체크하고 시그니처 불일치는 미탐. 단순 인터페이스(메서드 1개)에 적합. 복잡한 인터페이스는 ABC 권장.
- **`beautifulsoup4`** — `lxml` 백엔드 미설치 시 Python 표준 `html.parser` 사용(약간 느림, 하지만 본 스토리 1 fixture에서는 무관). lxml 추가 시 `pip install beautifulsoup4 lxml` 필요하나 본 스토리 범위 외.
- **`pytest-asyncio==1.3.0`** — `asyncio_mode = strict` (Story 2.1에서 설정) 하에서 `@pytest.mark.asyncio` 데코레이터 필수. `auto` 모드와 다름.
- **`unittest.mock.AsyncMock(spec=StealthBrowser)`** — `spec` 인자로 메서드 시그니처를 강제하여 잘못된 mock 호출(없는 메서드 등)을 조기 발견. 본 스토리 권장 패턴.
- **XpressEngine 게시판 구조** — tailstar.net이 사용. spike에서 `meta[name=Generator][content*=XpressEngine]` 확인. XE는 `<div class="document-info">` 등 셀렉터를 사용. 단, 본 스토리는 합성 fixture 사용이므로 정확한 XE 셀렉터 불요.

### Project Structure Notes

```
20261R0136COSE45700/
├── crawler/
│   ├── src/
│   │   ├── __init__.py             ← 변경 없음
│   │   ├── browser/                ← Story 2.1 (변경 없음)
│   │   │   ├── __init__.py
│   │   │   └── stealth_browser.py  ← AC #6 비변경 가드
│   │   ├── proxy/                  ← 본 스토리 신규 (Task 1)
│   │   │   ├── __init__.py
│   │   │   ├── proxy_provider.py
│   │   │   └── proxy_broker.py
│   │   └── sites/                  ← 본 스토리 신규 (Task 2-3)
│   │       ├── __init__.py
│   │       ├── base_site.py
│   │       └── tailstar.py
│   ├── tests/unit/
│   │   ├── __init__.py             ← 변경 없음
│   │   ├── test_browser.py         ← 변경 없음 (회귀 가드)
│   │   ├── test_proxy_provider.py  ← 신규
│   │   ├── test_html_parser.py     ← 신규
│   │   └── test_tailstar.py        ← 신규
│   ├── requirements.txt            ← 변경 없음
│   ├── requirements-dev.txt        ← 변경 없음
│   ├── pytest.ini                  ← 변경 없음
│   └── .env.example                ← 수정 (PROXY 3개 추가)
└── tests/
    └── fixtures/
        └── html/
            ├── .gitkeep            ← 변경 없음
            └── sample_illegal_post.html  ← 신규 (합성)
```

**충돌 가능성:**
- `crawler/src/proxy/__init__.py`와 `crawler/src/sites/__init__.py`가 새 패키지로 인식되도록 빈 파일이라도 명시 추가. 누락 시 `pytest`가 `from crawler.src.sites.tailstar import ...` 임포트 실패.
- `tests/fixtures/html/`는 모노레포 루트 기준. `crawler/tests/`와 다른 위치. 테스트 코드의 fixture 경로 계산 시 `Path(__file__).parent.parent.parent.parent`로 4단계 상위 (확인 필요 — `.../crawler/tests/unit/test_x.py`에서 4단계 위가 repo root).
- **변경 충돌 없음** — Story 1.3(.env.example 정식 작성), Story 1.4(fixture 추가)와 같은 파일을 건드리지만, 본 스토리는 추가만 하고 후속 스토리가 보강하는 방향 → 머지 충돌 위험 낮음.

### References

- [Epic 2 Story 2.2 AC](/_bmad-output/planning-artifacts/epics.md#L306-L320) — Source of Truth
- [Architecture: NFR15 ProxyProvider 추상화](/_bmad-output/planning-artifacts/architecture.md#L80) — 교체 비용 격리
- [Architecture: P10 Python 예외 처리](/_bmad-output/planning-artifacts/architecture.md#L385-L394) — `parse()` `None` 반환 금지
- [Architecture: P6 구조화 로그 표준 스키마](/_bmad-output/planning-artifacts/architecture.md#L322-L335)
- [Architecture: Cross-Cutting #5 Silent Failure 방지](/_bmad-output/planning-artifacts/architecture.md#L70)
- [Architecture: 디렉토리 구조 — crawler/src/sites/, proxy/](/_bmad-output/planning-artifacts/architecture.md#L453-L463)
- [PRD: FR1-FR6 콘텐츠 수집](/_bmad-output/planning-artifacts/prd.md#L347-L356)
- [PRD: NFR15 ProxyProvider 교체 비용](/_bmad-output/planning-artifacts/prd.md#L424)
- [Story 2.1 Dev Notes — StealthBrowser 시그니처](/_bmad-output/implementation-artifacts/2-1-cloudflare-우회-가능성-검증.md#L106-L113)
- [Story 2.1 Anti-Patterns — fetch_html 변경 금지](/_bmad-output/implementation-artifacts/2-1-cloudflare-우회-가능성-검증.md#L156-L168)
- [Cloudflare Spike Result §6 — Story 2.2 AC 변경 없음](/docs/cloudflare-spike-result.md#L132-L141)
- [Story 1.2 Dev Notes — shared/ 임포트 검증](/_bmad-output/implementation-artifacts/1-2-공유-인터페이스-계약-및-구조화-로깅-수립.md)
- [Deferred Work — Story 2.1 후속 항목](/_bmad-output/implementation-artifacts/deferred-work.md#L14-L19)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

- `cd crawler && ./.venv/bin/pytest -v` 결과: **25 passed in 0.12s**
  - `tests/unit/test_browser.py`: 6 passed (Story 2.1 기존, 회귀 0)
  - `tests/unit/test_html_parser.py`: 8 passed (fixture 기반 파싱 + 4종 ParseError 케이스)
  - `tests/unit/test_proxy_provider.py`: 7 passed (Protocol/Broker/NFR15 swap)
  - `tests/unit/test_tailstar.py`: 4 passed (5xx/429/timeout/happy)
- `git diff crawler/src/browser/stealth_browser.py` → 0 lines (AC #6 가드 통과)
- `git diff crawler/requirements.txt crawler/requirements-dev.txt crawler/pytest.ini shared/` → 0 lines (의존성/공유 모듈 변경 없음)

### Completion Notes List

- **ProxyProvider 형태 결정**: `typing.Protocol` + `@runtime_checkable` 채택. `_FakeProxyProvider`가 nominal subclassing 없이 `isinstance(..., ProxyProvider)`로 인식되는 것까지 단위 테스트로 못박음 → NodeMaven SDK 어댑터 작성 시 적응 비용 0.
- **ProxyConfig는 frozen dataclass**: 불변 객체로 mutation 방지. 프록시 회전 시에는 새 ProxyConfig 인스턴스를 반환하도록 강제됨.
- **`StealthBrowser` 본체 비변경 (AC #6)**: ProxyProvider DI는 `BaseSite` 생성자에서만 받음. stealth_browser.py 코드 수정 0줄, Story 2.1의 6 단위 테스트 그대로 PASS. 추후 ProxyConfig를 Playwright launch options에 주입하는 작업은 Story 2.5/2.6에서 stealth_browser 확장으로 처리 예정.
- **`_extract_post_id` 휴리스틱 강화**: 초기 구현이 `/about` 같은 알파벳 segment도 post_id로 인식하던 것을 `document_srl` 쿼리 또는 순수 숫자 path만 인정하도록 수정. parse_list가 네비게이션 링크를 게시글로 오분류하는 silent failure 경로 차단.
- **`tests/fixtures/html/sample_illegal_post.html`은 합성**: 라이브 캡처 회피로 fixture 안정성 확보. 동시에 가공의 "매크로 판매" 게시글 텍스트(매크로/핵/텔레그램/외주 키워드 포함)로 작성 → Story 2.3 `keyword_filter.py` 작업 시 정탐 fixture로 재활용 가능.
- **`_RATE_LIMIT_MARKERS` 다중 패턴**: 한국어 사이트의 다양한 차단 문구("잠시 후 다시 시도", "잠시후 다시 시도", "차단되었습니다", "접근이 차단" 등)를 사전 등록. Story 2.6/2.7 다른 한국 사이트 추가 시 같은 패턴이 작동할 가능성이 높음.
- **`async def fetch_and_parse`만 async, parse는 sync**: IO 0인 파싱 작업을 async로 만들면 event loop 오버헤드만 증가. APScheduler(Story 2.5) 통합 시 `asyncio.run` 또는 `AsyncIOExecutor` 패턴으로 호출.
- **새 third-party 의존성 0건**: `beautifulsoup4`는 Story 1.1 시점부터 선언. `lxml` 백엔드 미강제(html.parser 사용) — Story 2.6/2.7에서 파싱 성능 이슈 발견 시 그때 도입 검토.
- **deferred-work.md 미갱신**: 본 스토리에서 새로 deferred로 미루는 항목 없음. 기존 Story 2.1 deferred 4건은 모두 본 스토리에서 영향받지 않음(stealth_browser 비변경).
- **Story 2.6/2.7 확장 가이드**: PTT/Dcard/tieba 어댑터는 동일 `BaseSite` 상속 + 사이트별 셀렉터 오버라이드만으로 구현. PTT의 `.ptt.cc` 쿠키 인증은 `BaseSite.fetch_and_parse`를 오버라이드하지 말고 별도 `_authenticate()` 헬퍼 → `StealthBrowser` context에 cookie 주입 형태로 확장 권장.

### File List

신규:
- `crawler/src/proxy/__init__.py`
- `crawler/src/proxy/proxy_provider.py`
- `crawler/src/proxy/proxy_broker.py`
- `crawler/src/sites/__init__.py`
- `crawler/src/sites/base_site.py`
- `crawler/src/sites/tailstar.py`
- `crawler/tests/unit/test_proxy_provider.py`
- `crawler/tests/unit/test_html_parser.py`
- `crawler/tests/unit/test_tailstar.py`
- `tests/fixtures/html/sample_illegal_post.html`

수정:
- `crawler/.env.example` (PROXY_BROKER_HOST/USER/PASS 3개 키 추가)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (`2-2`: `backlog → ready-for-dev → in-progress → review`)
- `_bmad-output/implementation-artifacts/2-2-proxyprovider-추상화-및-기본-크롤러-구현.md` (본 파일 — Tasks/Subtasks 체크, Status, Dev Agent Record, File List, Change Log)

비변경 (회귀 가드):
- `crawler/src/browser/stealth_browser.py` — AC #6 (Story 2.1 6 tests 회귀 0)
- `crawler/src/browser/__init__.py`
- `crawler/tests/unit/test_browser.py`
- `crawler/requirements.txt`, `crawler/requirements-dev.txt`, `crawler/pytest.ini`
- `shared/` 전체

## Change Log

| 날짜 | 변경 | 사유 |
|---|---|---|
| 2026-04-28 | Story 2.2 컨텍스트 작성 (`Status: ready-for-dev`) | bmad-create-story |
| 2026-04-28 | Tasks 1-5 구현 — ProxyProvider Protocol + ProxyBroker, BaseSite ABC + ParseError/RateLimitError, TailstarSite, fixture HTML, 19개 신규 단위 테스트 | bmad-dev-story |
| 2026-04-28 | `_extract_post_id` 휴리스틱 강화 — 알파벳 segment를 post_id로 오분류하던 silent failure 차단 | self-review |
| 2026-04-28 | 회귀 검증 완료 (`pytest -v` → 25 passed). Status: in-progress → review | bmad-dev-story |
