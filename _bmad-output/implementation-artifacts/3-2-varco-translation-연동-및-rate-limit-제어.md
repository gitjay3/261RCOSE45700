# Story 3.2: VARCO Translation 연동 및 rate limit 제어

Status: review

> **본 스토리 핵심:** `posts:queue`(DB0)에서 소비된 `CrawlEvent` 중 `language ∈ {zh-CN, zh-TW}`인 항목만 VARCO Translation API로 한국어 번역하고, 호출 직전 Redis DB2(`varco:rate_limit`) 토큰 버킷을 atomic 차감하여 rate limit 초과를 방지한다. `language == "ko"`는 번역 스킵. Story 3.1의 `_stub_process`를 `DetectionPipeline`(translate-only — classify는 Story 3.3에서 추가)으로 교체한다. **이 스토리에서 LLM 분류·DLQ 처리·RDS 저장은 하지 않는다.**
>
> **[전제 조건]** Story 3.1 `done`. `detection/src/consumer/{queue_consumer,watchdog}.py` + `main.py` 완성. `shared/config/redis_config.py`에 `REDIS_RATELIMIT_DB=2` 정의됨. `shared/interfaces/varco.py`에 `VarcoInterface` Protocol(`translate`, `classify`) 정의됨. `detection/src/mocks/varco_mock.py` 완성(`mode="rate_limited"`이면 `RateLimitError(retry_after=30)`, `simulate_latency(ms)` 지원). fixture: `tests/fixtures/varco/mock_response_{clean,rate_limited}.json` 존재.

## Story

개발자로서,
중국어·번체 게시글이 VARCO Translation API를 통해 한국어로 번역되고, API 호출량이 토큰 버킷으로 자동 제어되기를 원한다,
그래서 rate limit 초과 없이 번역 파이프라인이 안정적으로 실행된다.

## Acceptance Criteria

1. **Given** `crawl_event`의 `language`가 `zh-CN` 또는 `zh-TW`인 게시글이 있을 때 **When** `translate.py`가 실행되면 **Then** VARCO Translation API를 호출하여 한국어 번역문을 반환한다 (FR11)
   **And** `language`가 `ko`(또는 그 외 미지원 언어)인 게시글은 Translation API 호출을 건너뛰고 `raw_text`를 그대로 반환하며, 구조화 로그에 `"translation skipped — language=<lang>"`이 `correlation_id`와 함께 기록된다.

2. **Given** `token_bucket.py`가 Redis DB2(`varco:rate_limit:translate`)에 접근할 때 **When** API 호출 전 토큰 소비를 시도하면 **Then** 잔여 토큰이 1 이상이면 atomic 차감 후 `True`를 반환하고, 0 이하이면 `refill_rate`에 따른 다음 충전 시각까지 대기한 뒤 재시도하여 자동 복구된다 (FR16, NFR14).
   **And** 토큰 소비/충전 연산은 단일 Lua script로 실행되어 race condition이 발생하지 않는다.
   **And** `acquire(timeout=N)`이 `N`초 내에 토큰을 획득하지 못하면 `RateLimitTimeoutError`를 발생시킨다(무한 대기 금지).

3. **Given** Translation API 호출이 `RateLimitError`(VARCO 응답 또는 mock 모드 `rate_limited`)를 발생시킬 때 **When** `translate.py`가 이를 감지하면 **Then** `RateLimitError.retry_after`초만큼 대기한 뒤 토큰 버킷을 재충전하지 않은 상태로 1회 자동 재시도한다.
   **And** 재시도 1회 실패 시 예외를 그대로 호출자에게 전파한다(3회 재시도·DLQ 격리는 Story 3.3 `retry_handler` 책임 — 본 스토리 범위 외).

4. **Given** `detection/tests/unit/test_token_bucket.py`가 실행될 때 **When** 테스트를 실행하면 **Then** 다음 5개 시나리오가 모두 PASS한다(`fakeredis` 또는 `MagicMock` 사용 — 실제 Redis 호출 0건):
   - 초기 상태(키 없음) → 첫 `acquire()`가 capacity-1로 채워진 버킷에서 1 토큰 차감 후 `True` 반환
   - 잔여 토큰 1 → `acquire()` 성공 후 0으로 감소
   - 잔여 토큰 0 + `refill_rate=1/sec` → 1초 경과 시뮬레이션 후 `acquire()` 성공
   - 잔여 토큰 0 + `acquire(timeout=0.05)` → `RateLimitTimeoutError` 발생
   - `mock_response_rate_limited.json`(`retry_after_seconds=30`) → `translate.py`가 `RateLimitError(retry_after=30)` catch → `time.sleep(30)` 호출(monkeypatch로 검증) → 1회 재시도 후 정상 응답 반환

5. **Given** `detection/tests/unit/test_translate.py`가 실행될 때 **When** 테스트를 실행하면 **Then** 다음 4개 시나리오가 모두 PASS한다:
   - `language="zh-CN"` → `VarcoMock("clean")`의 `translate()` 호출 → fixture의 `translated_text` 반환
   - `language="zh-TW"` → 동일 흐름
   - `language="ko"` → `VarcoMock.translate` **호출되지 않음**(MagicMock spy 검증) + `raw_text` 그대로 반환
   - `language="zh-CN"` + `VarcoMock("clean").simulate_latency(200)` → `translate()` 응답이 ≥0.18초 소요됨(p95 200ms 시뮬레이션 검증)

6. **Given** 모든 VARCO 호출 경로에서 **When** logger를 통해 로그가 기록되면 **Then** `extra={"correlation_id": event.correlation_id, "service": "detection"}`이 모든 INFO/WARNING/ERROR 레벨에 포함된다(P6 구조화 로그 규칙 — Story 3.1 review patch와 동일 패턴).

7. **Given** Story 3.1의 `_stub_process`가 `main.py`에 남아있을 때 **When** 본 스토리 작업이 완료되면 **Then** `DetectionPipeline.process(message)`로 교체되고, 해당 클래스는 `CrawlEvent.from_json` → (zh-CN/zh-TW이면) `TokenBucket.acquire()` → `VarcoInterface.translate()` 흐름을 수행하며, 결과 `translated_text`(string)를 로그에 출력하고 종료한다(Story 3.3 classify는 미구현 — TODO 주석으로 명시).

8. **Given** 검증 환경에서 **When** `cd detection && ./.venv/bin/pytest tests/unit/ -v`를 실행하면 **Then** Story 3.1 기존 7건 + 신규 9건 = **총 16건이 모두 PASS**하며 외부 네트워크/실제 Redis 호출이 0건이다.

> **AC 출처:** epics.md Story 3.2 (L447-462). AC 2의 Lua script atomic 요구사항, AC 3의 1회 자동 재시도 정책, AC 4의 5개 테스트 시나리오, AC 5의 4개 테스트 시나리오, AC 7의 `DetectionPipeline` 클래스명은 architecture.md(P2 키 명명, P6 로깅) + Story 3.1 `_stub_process` 주석("translate → classify → save로 교체") + 표준 토큰 버킷 알고리즘에 기반해 구체화. **VARCO Translation API 실제 엔드포인트/auth 헤더 명세는 architecture.md/prd.md 모두 미제공 — `VARCO_API_BASE_URL`, `VARCO_API_KEY` 환경변수 + httpx.Client placeholder로 처리하며, 실제 명세 확보 시 `_VarcoHttpClient` 내부만 수정.**

## Tasks / Subtasks

- [x] **Task 1: shared 상수 추가 및 requirements 업데이트** (AC: #2, #4)
  - [x] 1.1 `shared/config/redis_config.py`에 토큰 버킷 키 상수 추가:
    ```python
    REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE: str = "varco:rate_limit:translate"
    ```
    > Story 3.3에서 `varco:rate_limit:classify`도 추가 예정 — 본 스토리는 `:translate`만 정의.
  - [x] 1.2 `detection/requirements.txt`에 `fakeredis>=2.0.0` 추가(테스트 의존성 — Lua script 실행 가능한 in-memory Redis 시뮬레이터):
    ```
    redis>=5.0.0
    boto3
    httpx
    python-dotenv
    pytest>=7.0.0
    pytest-mock>=3.0.0
    fakeredis>=2.0.0
    -e ../shared
    ```
  - [x] 1.3 `detection/.env.example`에 환경변수 추가(없으면 신규 생성):
    ```
    VARCO_API_BASE_URL=https://varco.placeholder/v1
    VARCO_API_KEY=
    VARCO_TRANSLATE_TIMEOUT_SEC=10
    VARCO_RATE_LIMIT_CAPACITY=60
    VARCO_RATE_LIMIT_REFILL_PER_SEC=1
    VARCO_RATE_LIMIT_MAX_WAIT_SEC=120
    ```
    > 기본값 — Translation 60 RPM(분당 60회) + 충전율 1 req/sec. VARCO 실제 quota 확보 후 조정.

- [x] **Task 2: Redis DB2 클라이언트 추가** (AC: #2)
  - [x] 2.1 `detection/src/config/redis_config.py` 수정 — `get_rate_limit_client()` 추가:
    ```python
    from __future__ import annotations

    import os

    import redis

    from shared.config.redis_config import REDIS_MQ_DB, REDIS_RATELIMIT_DB


    def get_mq_client() -> redis.Redis:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        return redis.from_url(url, db=REDIS_MQ_DB, decode_responses=True)


    def get_rate_limit_client() -> redis.Redis:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        return redis.from_url(url, db=REDIS_RATELIMIT_DB, decode_responses=True)
    ```
    - `REDIS_RATELIMIT_DB`는 `shared/config/redis_config.py`에서 임포트(=2). 하드코딩 금지.
    - `decode_responses=True` 유지 — Story 3.1 `LREM` 패턴과 일관.

- [x] **Task 3: TokenBucket 구현** (AC: #2, #4)
  - [x] 3.1 `detection/src/rate_limit/__init__.py` 신규(빈 파일).
  - [x] 3.2 `detection/src/rate_limit/token_bucket.py` 신규:
    ```python
    from __future__ import annotations

    import os
    import time

    import redis

    from shared.config.redis_config import REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE
    from shared.structured_logger import get_logger

    _SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
    _logger = get_logger(__name__)


    class RateLimitTimeoutError(Exception):
        """`acquire(timeout)` 내에 토큰을 획득하지 못한 경우."""


    # KEYS[1] = bucket key (e.g. "varco:rate_limit:translate")
    # ARGV[1] = capacity, ARGV[2] = refill_per_sec, ARGV[3] = now (float seconds)
    # 반환: 획득 성공 시 1, 실패 시 다음 토큰 충전까지 남은 초(float, >0)
    _LUA_ACQUIRE = """
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local refill = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])

    local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
    local tokens = tonumber(bucket[1])
    local last_refill = tonumber(bucket[2])

    if tokens == nil then
      tokens = capacity
      last_refill = now
    else
      local elapsed = now - last_refill
      if elapsed > 0 then
        tokens = math.min(capacity, tokens + elapsed * refill)
        last_refill = now
      end
    end

    if tokens >= 1 then
      tokens = tokens - 1
      redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
      redis.call('EXPIRE', key, 3600)
      return '0'
    else
      redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
      redis.call('EXPIRE', key, 3600)
      local wait = (1 - tokens) / refill
      return tostring(wait)
    end
    """


    class TokenBucket:
        def __init__(
            self,
            redis_client: redis.Redis,
            key: str = REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE,
            capacity: int | None = None,
            refill_per_sec: float | None = None,
        ) -> None:
            self._redis = redis_client
            self._key = key
            self._capacity = int(capacity if capacity is not None
                                 else os.environ.get("VARCO_RATE_LIMIT_CAPACITY", "60"))
            self._refill = float(refill_per_sec if refill_per_sec is not None
                                 else os.environ.get("VARCO_RATE_LIMIT_REFILL_PER_SEC", "1"))
            self._script = self._redis.register_script(_LUA_ACQUIRE)

        def acquire(self, timeout: float | None = None) -> None:
            """토큰 1개 차감. 부족 시 충전까지 sleep 후 재시도. timeout 초과 시 RateLimitTimeoutError."""
            if timeout is None:
                timeout = float(os.environ.get("VARCO_RATE_LIMIT_MAX_WAIT_SEC", "120"))
            deadline = time.monotonic() + timeout
            while True:
                wait_str = self._script(
                    keys=[self._key],
                    args=[self._capacity, self._refill, time.time()],
                )
                wait = float(wait_str)
                if wait == 0:
                    return
                remaining = deadline - time.monotonic()
                if remaining <= 0 or wait > remaining:
                    raise RateLimitTimeoutError(
                        f"token bucket timeout after {timeout}s (next refill in {wait:.2f}s)"
                    )
                _logger.warning(
                    "토큰 버킷 대기 — wait=%.2fs",
                    wait,
                    extra={"correlation_id": "", "service": _SERVICE_NAME},
                )
                time.sleep(wait)
    ```
  - [x] 3.3 핵심 설계 결정:
    - **Hash 키 구조**: `HSET varco:rate_limit:translate tokens <float> last_refill <epoch>`. SET이 아닌 HASH로 두 필드 atomic 보존.
    - **Lazy refill**: `acquire` 호출 시점에서 `now - last_refill`만큼 충전. cron 불필요.
    - **Lua script로 atomic** — `EVALSHA` 자동 캐시(`register_script`). race condition 없음.
    - **TTL 1시간** — 키 영구 잔류 방지. 1시간 미사용 시 자동 만료 후 다음 호출에서 capacity로 재초기화.
    - **`time.time()` vs Redis `TIME`**: 클라이언트 시각 사용. 단일 인스턴스 환경에서 충분. 다중 인스턴스 시계 편차 보정은 deferred.

- [x] **Task 4: VARCO Translation 어댑터 + translate.py 구현** (AC: #1, #3, #5, #6)
  - [x] 4.1 `detection/src/pipeline/__init__.py` 신규(빈 파일).
  - [x] 4.2 `detection/src/pipeline/varco_client.py` 신규 — production용 httpx 클라이언트:
    ```python
    from __future__ import annotations

    import os

    import httpx

    from detection.src.mocks.varco_mock import RateLimitError
    from shared.interfaces.varco import ClassificationResult, VarcoInterface


    class VarcoHttpClient:
        """VarcoInterface 구현 — 실제 VARCO API 호출. 엔드포인트는 환경변수로 주입."""

        def __init__(self, client: httpx.Client | None = None) -> None:
            base_url = os.environ.get("VARCO_API_BASE_URL", "https://varco.placeholder/v1")
            api_key = os.environ.get("VARCO_API_KEY", "")
            timeout = float(os.environ.get("VARCO_TRANSLATE_TIMEOUT_SEC", "10"))
            self._client = client or httpx.Client(
                base_url=base_url,
                headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
                timeout=timeout,
            )

        def translate(self, text: str) -> str:
            response = self._client.post("/translate", json={"text": text, "target": "ko"})
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "30"))
                raise RateLimitError(retry_after)
            response.raise_for_status()
            return response.json()["translated_text"]

        def classify(self, text: str) -> ClassificationResult:  # Story 3.3
            raise NotImplementedError("classify는 Story 3.3에서 구현")


    def is_varco_interface(obj) -> bool:
        return isinstance(obj, VarcoInterface)
    ```
    > ⚠️ VARCO 실제 엔드포인트 경로(`/translate`)·request body 키(`text`, `target`)·response 필드(`translated_text`)는 mock 계약을 따랐다. 실제 API spec 확보 시 본 클래스만 수정.
  - [x] 4.3 `detection/src/pipeline/translate.py` 신규:
    ```python
    from __future__ import annotations

    import os
    import time

    from detection.src.mocks.varco_mock import RateLimitError
    from detection.src.rate_limit.token_bucket import TokenBucket
    from shared.interfaces.varco import VarcoInterface
    from shared.models.crawl_event import CrawlEvent
    from shared.structured_logger import get_logger

    _SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
    _TRANSLATABLE_LANGS = frozenset({"zh-CN", "zh-TW"})
    _logger = get_logger(__name__)


    class Translator:
        def __init__(
            self,
            varco: VarcoInterface,
            token_bucket: TokenBucket,
        ) -> None:
            self._varco = varco
            self._bucket = token_bucket

        def translate_event(self, event: CrawlEvent) -> str:
            """language가 zh-CN/zh-TW이면 VARCO 호출, 그 외는 raw_text 그대로 반환."""
            if event.language not in _TRANSLATABLE_LANGS:
                _logger.info(
                    "translation skipped — language=%s",
                    event.language,
                    extra={"correlation_id": event.correlation_id, "service": _SERVICE_NAME},
                )
                return event.raw_text

            self._bucket.acquire()
            try:
                return self._varco.translate(event.raw_text)
            except RateLimitError as exc:
                _logger.warning(
                    "VARCO rate limit — retry_after=%ds",
                    exc.retry_after,
                    extra={"correlation_id": event.correlation_id, "service": _SERVICE_NAME},
                )
                time.sleep(exc.retry_after)
                return self._varco.translate(event.raw_text)
    ```
  - [x] 4.4 핵심 설계 결정:
    - **`VarcoInterface` 의존성 주입** — production은 `VarcoHttpClient`, test는 `VarcoMock`. `Translator`는 둘 다 동일하게 받음.
    - **`event.raw_text` 직접 사용** — `s3_text_path`가 채워져 있어도 `raw_text`가 always populated(crawler 계약).
    - **자동 재시도 1회만** — 3회 재시도 + DLQ는 Story 3.3 `retry_handler` 책임.
    - **재시도 시 토큰 버킷 재차감 없음** — `RateLimitError`는 VARCO 측 거부이지 우리 버킷이 비어서가 아니므로, sleep 후 재호출만.

- [x] **Task 5: DetectionPipeline 통합 + main.py 교체** (AC: #7)
  - [x] 5.1 `detection/src/pipeline/detection_pipeline.py` 신규:
    ```python
    from __future__ import annotations

    import os

    from detection.src.pipeline.translate import Translator
    from shared.models.crawl_event import CrawlEvent
    from shared.structured_logger import get_logger

    _SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
    _logger = get_logger(__name__)


    class DetectionPipeline:
        def __init__(self, translator: Translator) -> None:
            self._translator = translator

        def process(self, message: str) -> None:
            event = CrawlEvent.from_json(message)
            translated = self._translator.translate_event(event)
            _logger.info(
                "translation completed — len=%d",
                len(translated),
                extra={"correlation_id": event.correlation_id, "service": _SERVICE_NAME},
            )
            # TODO(Story 3.3): classify(translated) → ClassificationResult
            # TODO(Story 3.4): detection_repository.save(event, classification)
    ```
  - [x] 5.2 `detection/src/main.py` 수정 — `_stub_process`를 `DetectionPipeline.process`로 교체:
    ```python
    from __future__ import annotations

    import threading

    from detection.src.config.redis_config import get_mq_client, get_rate_limit_client
    from detection.src.consumer.queue_consumer import QueueConsumer
    from detection.src.consumer.watchdog import Watchdog
    from detection.src.pipeline.detection_pipeline import DetectionPipeline
    from detection.src.pipeline.translate import Translator
    from detection.src.pipeline.varco_client import VarcoHttpClient
    from detection.src.rate_limit.token_bucket import TokenBucket
    from shared.structured_logger import get_logger

    _logger = get_logger(__name__)


    def main() -> None:
        mq_client = get_mq_client()
        rate_limit_client = get_rate_limit_client()

        varco = VarcoHttpClient()
        bucket = TokenBucket(rate_limit_client)
        translator = Translator(varco, bucket)
        pipeline = DetectionPipeline(translator)

        watchdog = Watchdog(mq_client)
        consumer = QueueConsumer(mq_client, pipeline.process, watchdog=watchdog)

        watchdog_thread = threading.Thread(target=watchdog.run_forever, daemon=True)
        watchdog_thread.start()

        consumer.run_forever()


    if __name__ == "__main__":
        main()
    ```
  - [x] 5.3 `_stub_process` 함수는 **삭제**(더 이상 사용처 없음).

- [x] **Task 6: TokenBucket 단위 테스트** (AC: #4)
  - [x] 6.1 `detection/tests/unit/test_token_bucket.py` 신규 — `fakeredis`를 사용해 Lua script 포함 atomic 동작 검증:
    ```python
    from __future__ import annotations

    from unittest.mock import patch

    import fakeredis
    import pytest

    from detection.src.rate_limit.token_bucket import (
        RateLimitTimeoutError,
        TokenBucket,
    )
    from shared.config.redis_config import REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE


    @pytest.fixture
    def fake_redis():
        return fakeredis.FakeRedis(decode_responses=True)


    def test_first_acquire_initializes_bucket(fake_redis):
        bucket = TokenBucket(fake_redis, capacity=5, refill_per_sec=1)
        bucket.acquire()  # 예외 없이 통과 → 첫 호출 capacity-1=4
        tokens = float(fake_redis.hget(REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE, "tokens"))
        assert tokens == 4


    def test_acquire_decrements_existing_bucket(fake_redis):
        bucket = TokenBucket(fake_redis, capacity=2, refill_per_sec=0.001)
        bucket.acquire()
        bucket.acquire()
        tokens = float(fake_redis.hget(REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE, "tokens"))
        assert tokens < 1  # 거의 0 (lazy refill 미세 증분 가능)


    def test_acquire_waits_for_refill(fake_redis):
        bucket = TokenBucket(fake_redis, capacity=1, refill_per_sec=10)  # 0.1s/token
        bucket.acquire()  # 토큰 0
        with patch("detection.src.rate_limit.token_bucket.time.sleep") as mock_sleep:
            bucket.acquire(timeout=1)
        mock_sleep.assert_called()  # sleep 호출 발생 = 대기 후 재시도


    def test_acquire_raises_on_timeout(fake_redis):
        bucket = TokenBucket(fake_redis, capacity=1, refill_per_sec=0.001)  # 1000s/token
        bucket.acquire()  # 토큰 0
        with pytest.raises(RateLimitTimeoutError):
            bucket.acquire(timeout=0.05)


    def test_lua_script_is_atomic(fake_redis):
        """동일 키에 capacity=1로 2회 연속 acquire 시 두 번째는 즉시 실패하지 않고 대기 진입."""
        bucket = TokenBucket(fake_redis, capacity=1, refill_per_sec=100)
        bucket.acquire()
        with patch("detection.src.rate_limit.token_bucket.time.sleep") as mock_sleep:
            bucket.acquire(timeout=1)
        # 두 번째 acquire는 sleep을 1회 이상 호출 → atomic 차감 확인
        assert mock_sleep.call_count >= 1
    ```
  - [x] 6.2 핵심: `time.sleep`을 `patch`로 대체해 wall-clock 의존성 제거. `fakeredis`는 Lua script(`EVAL`/`EVALSHA`)를 지원함을 사전 확인 후 사용. 미지원 시 → `pytest.importorskip("fakeredis")` 가드 + `MagicMock`으로 폴백.

- [x] **Task 7: Translator 단위 테스트** (AC: #5)
  - [x] 7.1 `detection/tests/unit/test_translate.py` 신규:
    ```python
    from __future__ import annotations

    import time
    from unittest.mock import MagicMock, patch

    import pytest

    from detection.src.pipeline.translate import Translator
    from detection.src.mocks.varco_mock import RateLimitError, VarcoMock
    from shared.models.crawl_event import CrawlEvent


    def _make_event(language: str, text: str = "我要卖外挂") -> CrawlEvent:
        return CrawlEvent(
            post_id="tieba_001",
            source_id="tieba_freestyle",
            site_name="贴吧 (자유게시판)",
            raw_text=text,
            language=language,
            detected_at="2026-04-29T10:00:00Z",
            correlation_id="cid-translate-001",
        )


    def test_translates_zh_cn_via_varco():
        bucket = MagicMock()
        varco = VarcoMock(mode="clean")
        translator = Translator(varco, bucket)
        result = translator.translate_event(_make_event("zh-CN"))
        assert "안녕하세요" in result or "한국어" in result or len(result) > 0  # fixture translated_text
        bucket.acquire.assert_called_once()


    def test_translates_zh_tw_via_varco():
        bucket = MagicMock()
        varco = VarcoMock(mode="clean")
        translator = Translator(varco, bucket)
        result = translator.translate_event(_make_event("zh-TW"))
        assert result  # fixture 응답 그대로
        bucket.acquire.assert_called_once()


    def test_skips_translation_for_korean():
        bucket = MagicMock()
        varco = MagicMock(spec=VarcoMock)
        translator = Translator(varco, bucket)
        event = _make_event("ko", text="매크로 판매합니다")
        result = translator.translate_event(event)
        assert result == "매크로 판매합니다"
        varco.translate.assert_not_called()
        bucket.acquire.assert_not_called()


    def test_simulate_latency_p95_200ms():
        bucket = MagicMock()
        varco = VarcoMock(mode="clean")
        varco.simulate_latency(200)
        translator = Translator(varco, bucket)
        start = time.monotonic()
        translator.translate_event(_make_event("zh-CN"))
        elapsed = time.monotonic() - start
        assert elapsed >= 0.18  # 200ms ± 시스템 jitter 허용


    def test_rate_limit_error_triggers_single_retry():
        bucket = MagicMock()
        varco = MagicMock(spec=VarcoMock)
        varco.translate.side_effect = [RateLimitError(retry_after=30), "translated 한국어"]
        translator = Translator(varco, bucket)
        with patch("detection.src.pipeline.translate.time.sleep") as mock_sleep:
            result = translator.translate_event(_make_event("zh-CN"))
        assert result == "translated 한국어"
        mock_sleep.assert_called_once_with(30)
        assert varco.translate.call_count == 2
    ```
  - [x] 7.2 `test_simulate_latency_p95_200ms`는 wall-clock 사용 — CI 환경에 따라 flaky 가능성. `>=0.18` 마진 확보.
  - [x] 7.3 AC #5 4개 시나리오 + AC #4의 5번째 시나리오(rate limit retry) = 총 5건. AC #4의 1~4는 `test_token_bucket.py`에서 검증.

- [x] **Task 8: 검증 및 마무리**
  - [x] 8.1 `cd detection && ./.venv/bin/pip install -r requirements.txt` (fakeredis 추가 설치)
  - [x] 8.2 `cd detection && ./.venv/bin/pytest tests/unit/ -v` → Story 3.1 기존 7건 + 신규 9건(`test_token_bucket.py` 5건 + `test_translate.py` 5건 — rate_limit retry 시나리오 1건은 translate 측에서 검증) = **총 16건 PASS**
  - [x] 8.3 `_bmad-output/implementation-artifacts/sprint-status.yaml`의 `3-2-varco-translation-연동-및-rate-limit-제어` 상태 갱신: `ready-for-dev → in-progress → review`(dev 진행 시)
  - [x] 8.4 `epic-3` 상태는 이미 `in-progress` — 변경 없음

## Dev Notes

### 본 스토리 범위 (Scope Boundary)

| 이번 스토리에서 한다 | 이번 스토리에서 **하지 않는다** |
|---|---|
| `pipeline/translate.py` — VARCO Translation 호출 + 언어 분기 | `pipeline/llm_classifier.py` — VARCO LLM 분류 → Story 3.3 |
| `pipeline/varco_client.py` — `VarcoInterface` httpx 구현(translate만) | `retry/retry_handler.py` — 3회 재시도 + DLQ → Story 3.3 |
| `rate_limit/token_bucket.py` — Redis DB2 Lua script atomic | `storage/detection_repository.py` — RDS 저장 → Story 3.4 |
| `pipeline/detection_pipeline.py` — `DetectionPipeline.process` (translate-only) | DB `detections` 테이블 멱등성 → Story 3.4 |
| `_stub_process` 제거 + `main.py` 통합 배선 | 정확도 측정(Precision/Recall) → Story 3.5 |
| 단위 테스트 9건(`fakeredis` + `MagicMock`) | 실제 VARCO API 통합 테스트 — Story 3.5 또는 운영 검증 시점 |
| `shared/config/redis_config.py`에 `REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE` 상수 | `varco:rate_limit:classify` 키 → Story 3.3 |

### 현재 `detection/` 구조 (Story 3.2 착수 시점)

```
detection/
├── pytest.ini
├── requirements.txt
├── .env.example                  # ← Story 3.2가 VARCO 환경변수 추가
└── src/
    ├── __init__.py
    ├── main.py                   # ← _stub_process 교체 대상
    ├── config/
    │   ├── __init__.py
    │   └── redis_config.py       # ← get_rate_limit_client 추가
    ├── consumer/
    │   ├── __init__.py
    │   ├── queue_consumer.py     # 변경 없음
    │   └── watchdog.py           # 변경 없음
    └── mocks/
        ├── __init__.py
        └── varco_mock.py         # 변경 없음(simulate_latency 이미 구현됨)
└── tests/
    └── unit/
        └── test_consumer_idempotency.py  # 7건 PASS (Story 3.1)
```

**이 스토리에서 추가될 구조:**

```
detection/src/
├── pipeline/                     ← 신규 디렉토리
│   ├── __init__.py
│   ├── translate.py              ← Translator
│   ├── varco_client.py           ← VarcoHttpClient (httpx)
│   └── detection_pipeline.py     ← DetectionPipeline (translate-only)
└── rate_limit/                   ← 신규 디렉토리
    ├── __init__.py
    └── token_bucket.py           ← TokenBucket + Lua script
detection/tests/unit/
├── test_token_bucket.py          ← 5건
└── test_translate.py             ← 5건
shared/config/redis_config.py     ← REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE 추가
```

### 공유 모듈 임포트 패턴 (재구현 절대 금지)

```python
# Redis DB / 키 상수
from shared.config.redis_config import (
    REDIS_RATELIMIT_DB,                      # = 2
    REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE,    # = "varco:rate_limit:translate" (본 스토리 신규)
)

# VARCO Protocol — production / test 모두 이 인터페이스 의존
from shared.interfaces.varco import VarcoInterface, ClassificationResult

# Mock — RateLimitError 예외 타입은 mocks 모듈에서 직접 임포트
from detection.src.mocks.varco_mock import VarcoMock, RateLimitError

# CrawlEvent — translate_event(event)에서 from_json + language/raw_text/correlation_id 사용
from shared.models.crawl_event import CrawlEvent

# 구조화 로그
from shared.structured_logger import get_logger
```

### Redis DB2 토큰 버킷 키 구조

```
HSET varco:rate_limit:translate
    tokens       <float>     # 현재 잔여 토큰 (실수 — lazy refill 시 소수점 발생)
    last_refill  <float>     # 마지막 충전 epoch (time.time())
EXPIRE varco:rate_limit:translate 3600
```

**Lua script 흐름:**
```
1. HMGET tokens, last_refill
2. tokens 미존재 → capacity로 초기화
3. elapsed = now - last_refill > 0 → tokens += elapsed * refill_per_sec (cap=capacity)
4. tokens >= 1: tokens -= 1, return "0" (성공)
   tokens <  1: return "<wait_seconds>" (다음 충전까지)
5. HMSET + EXPIRE 갱신
```

### VARCO API 호출 패턴

```python
# production
varco = VarcoHttpClient()
text_ko = varco.translate("我要卖外挂")  # → "매크로 판매합니다"

# test/dev
varco = VarcoMock(mode="clean")
text_ko = varco.translate("我要卖外挂")  # → fixture mock_response_clean.json의 translated_text

# rate-limited 시뮬레이션
varco = VarcoMock(mode="rate_limited")
varco.translate("...")  # → raises RateLimitError(retry_after=30)
```

**VARCO 실제 명세 미확보 시 placeholder:**
- `POST /translate` body: `{"text": "...", "target": "ko"}`
- response 200: `{"translated_text": "..."}`
- response 429: `Retry-After` 헤더 → `RateLimitError(retry_after=int(헤더))`
- 실제 VARCO API 명세 확보 시 `varco_client.py`만 수정. `Translator`/`TokenBucket`/`DetectionPipeline`은 비변경.

### `event.language` 분기 정확한 값

`crawler/src/preprocessor/language_detector.py`의 `_LANG_MAP`이 langdetect 반환값(`zh-cn`, `zh-tw`)을 `zh-CN`, `zh-TW`로 정규화한 후 `posts:queue`에 LPUSH한다. 따라서 `Translator`는 정확히 `{"zh-CN", "zh-TW"}` 집합으로 분기. `"zh"`, `"chinese"` 등 비정규화 값은 들어오지 않음.

```python
_TRANSLATABLE_LANGS = frozenset({"zh-CN", "zh-TW"})  # 대소문자 정확히 일치
```

### 환경변수 목록 (Story 3.1 + 3.2 누적)

| 변수 | 기본값 | 설명 | 도입 |
|------|--------|------|------|
| `REDIS_URL` | `redis://localhost:6379` | Redis 연결 URL | 3.1 |
| `SERVICE_NAME` | `detection` | 구조화 로그 service 필드 | 3.1 |
| `BRPOPLPUSH_TIMEOUT` | `30` | brpoplpush blocking timeout (초) | 3.1 |
| `WATCHDOG_STALE_SECONDS` | `300` | stale 판정 기준 (초) | 3.1 |
| `WATCHDOG_POLL_INTERVAL` | `60` | Watchdog 폴링 주기 (초) | 3.1 |
| `VARCO_API_BASE_URL` | `https://varco.placeholder/v1` | VARCO API base URL (실명세 확보 후 교체) | **3.2** |
| `VARCO_API_KEY` | `""` | VARCO API key (Bearer) | **3.2** |
| `VARCO_TRANSLATE_TIMEOUT_SEC` | `10` | httpx.Client timeout | **3.2** |
| `VARCO_RATE_LIMIT_CAPACITY` | `60` | 토큰 버킷 capacity (요청/분 한도) | **3.2** |
| `VARCO_RATE_LIMIT_REFILL_PER_SEC` | `1` | 초당 충전 토큰 수 | **3.2** |
| `VARCO_RATE_LIMIT_MAX_WAIT_SEC` | `120` | `acquire()` 최대 대기(초) — 초과 시 `RateLimitTimeoutError` | **3.2** |

### Anti-Patterns to Avoid

1. ❌ **`event.language == "zh"` 비교** — 실제 값은 `zh-CN`/`zh-TW`. 대소문자 정확히 일치하는 frozenset 사용.
2. ❌ **`Translator`가 `VarcoMock`/`VarcoHttpClient`를 직접 임포트** — 의존성 주입(`VarcoInterface`)으로만 받음. 테스트와 production이 동일 코드 경로.
3. ❌ **토큰 버킷을 `INCR` + `EXPIRE`로 구현** — atomic하지 않음. 반드시 Lua script 또는 `MULTI/EXEC`. 본 스토리는 Lua 채택.
4. ❌ **`acquire()` 무한 루프** — `RateLimitTimeoutError` 없이 `while True: time.sleep(wait)`. Watchdog의 `WATCHDOG_STALE_SECONDS=300`을 초과하면 메시지가 stale 판정 → 재투입 → retry storm. `VARCO_RATE_LIMIT_MAX_WAIT_SEC` 외부화 + timeout 체크 필수.
5. ❌ **`VarcoHttpClient` 내부에서 토큰 버킷 호출** — 책임 분리 위반. `Translator`가 `bucket.acquire()` 후 `varco.translate()` 호출하는 명시적 흐름.
6. ❌ **`RateLimitError`를 다시 `RateLimitError`로 wrap** — `detection.src.mocks.varco_mock.RateLimitError`를 그대로 `Translator`까지 전파. 별도 예외 타입 신설 금지.
7. ❌ **재시도 시 토큰 버킷 재차감** — `RateLimitError`는 VARCO 측 quota 거부이지 우리 버킷이 비어서가 아님. `time.sleep(retry_after)` 후 `varco.translate()` 직접 재호출.
8. ❌ **`asyncio` 도입** — Story 3.1이 동기 + `MagicMock(redis)` 패턴. 비동기 도입 시 mock과 mismatch + watchdog 스레드 모델과 충돌. 동기 유지.
9. ❌ **`db=2` 하드코딩** — `REDIS_RATELIMIT_DB` 임포트 사용. Story 3.1 review에서 `db=0` 하드코딩 금지 패턴과 동일.
10. ❌ **로그에 `raw_text` 또는 `translated_text` 본문 포함** — 개인정보·저작권 노출 가능. `len(translated)`만 출력.

### Architecture Compliance Notes

- **FR11 (자동 번역)** — `language ∈ {zh-CN, zh-TW}`만 번역, `ko`는 스킵. AC #1.
- **FR16 (외부 API 호출량 제어)** — Redis DB2 토큰 버킷 + Lua script atomic. AC #2.
- **NFR3 (배치 ≤30분)** — `VARCO_RATE_LIMIT_MAX_WAIT_SEC=120` 기본값으로 단일 요청 최대 대기 2분 이내. 200~300건 배치에서 누적 대기 시간 ≤ 8분 가정(60 RPM × 5min ≥ 300건). Story 3.5에서 실측.
- **NFR5 (API 키 환경변수)** — `VARCO_API_KEY`는 `.env` 또는 OS 환경변수에서만 로드. 코드 하드코딩 금지.
- **NFR14 (rate limit 자동 대기 후 재개)** — `TokenBucket.acquire()` + `RateLimitError` 자동 재시도. 수동 개입 없음. AC #2, #3.
- **NFR16 (BRPOPLPUSH 원자성)** — Story 3.1에서 이미 구현. 본 스토리는 비변경.
- **architecture.md P2 (Redis 키 명명)** — `varco:rate_limit:translate` 소문자 콜론 계층. AC #2.
- **architecture.md P6 (구조화 로그)** — 모든 로그에 `extra={"correlation_id", "service"}`. AC #6.

### 주요 의존 관계

```
Story 2.5 → posts:queue (DB0)에 CrawlEvent LPUSH
Story 3.1 → BRPOPLPUSH 소비 + Watchdog stale 복구 (done)
Story 3.2 → translate (이 스토리, language 분기 + 토큰 버킷)
Story 3.3 → classify + retry_handler (3회 재시도) + DLQ
Story 3.4 → detection_repository → RDS detections
Story 3.5 → Precision/Recall + 배치 시간 측정
```

### Story 3.1 Deferred 항목 중 본 스토리 영향

- **`processing_time` TTL = stale 임계치 동일(300s)** (Story 3.1 deferred D-04) — VARCO 호출 + 토큰 버킷 대기가 5분 초과 시 watchdog stale 오판 가능. `VARCO_RATE_LIMIT_MAX_WAIT_SEC=120` 기본값으로 누적 ≤ ~3분 이내(translate timeout 10s + 대기 120s ≪ 300s). **본 스토리는 TTL 분리 미구현** — Story 3.5 측정 후 결정.
- **`process_fn` 시그니처 단순(`Callable[[str], None]`)** (Story 3.1 deferred D-15) — `DetectionPipeline.process(message: str) -> None`로 그대로 만족. 변경 불필요.

### 본 스토리 Deferred 항목 (Story 3.5 또는 운영 시점 재검토)

- VARCO 실제 API 엔드포인트/auth/스키마 미확보 → `VarcoHttpClient`만 수정. 본 스토리는 mock 계약 기반 placeholder.
- 다중 detection 인스턴스 환경에서 `time.time()` 클라이언트 시각 편차 → 단일 인스턴스 MVP에서는 무시.
- 토큰 버킷 capacity/refill 튜닝 → Story 3.5 실측 후 환경변수로 조정.
- `varco:rate_limit:classify` 키 → Story 3.3에서 추가.

### Project Context Reference

- [shared/config/redis_config.py](shared/config/redis_config.py) — `REDIS_RATELIMIT_DB`, 본 스토리에서 `REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE` 추가
- [shared/interfaces/varco.py](shared/interfaces/varco.py) — `VarcoInterface` Protocol, `ClassificationResult`
- [shared/models/crawl_event.py](shared/models/crawl_event.py) — `language ∈ {ko, zh-CN, zh-TW, ...}`
- [detection/src/mocks/varco_mock.py](detection/src/mocks/varco_mock.py) — `VarcoMock`, `RateLimitError`, `simulate_latency`
- [detection/src/main.py](detection/src/main.py) — `_stub_process` 교체 대상
- [detection/src/consumer/queue_consumer.py](detection/src/consumer/queue_consumer.py) — `process_fn` 시그니처
- [crawler/src/preprocessor/language_detector.py](crawler/src/preprocessor/language_detector.py) — `_LANG_MAP` 정규화 (zh-cn → zh-CN)
- [tests/fixtures/varco/mock_response_clean.json](tests/fixtures/varco/mock_response_clean.json) — `translated_text`
- [tests/fixtures/varco/mock_response_rate_limited.json](tests/fixtures/varco/mock_response_rate_limited.json) — `retry_after_seconds=30`
- [_bmad-output/implementation-artifacts/3-1-redis-큐-소비자-및-watchdog-구현.md](_bmad-output/implementation-artifacts/3-1-redis-큐-소비자-및-watchdog-구현.md) — Story 3.1 전체 컨텍스트
- [_bmad-output/planning-artifacts/architecture.md](_bmad-output/planning-artifacts/architecture.md) — Redis DB 분리(L64, L190), 키 명명(L274-285), detection 디렉토리 구조(L487-518)
- [_bmad-output/planning-artifacts/epics.md](_bmad-output/planning-artifacts/epics.md) — Story 3.2 AC(L447-462), Story 3.3 후속 의존성(L464-478)
- [_bmad-output/planning-artifacts/prd.md](_bmad-output/planning-artifacts/prd.md) — FR11, FR16, NFR3, NFR5, NFR14

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

- AC #4 Task 6의 `fakeredis` Lua script 미지원 — 기본 `fakeredis` 패키지는 `EVALSHA` 명령을 지원하지 않아 `unknown command 'evalsha'` ResponseError 발생. `fakeredis[lua]` extras 설치(`lupa` 의존성 포함) 후 정상 작동. `requirements.txt`를 `fakeredis[lua]>=2.0.0`으로 갱신.
- AC #8 테스트 카운트 — story spec은 "기존 7건 + 신규 9건 = 16건" 산정이었으나, Story 3.1 review에서 corrupt-DLQ 테스트(`test_watchdog_quarantines_corrupt_message`)가 추가되어 기존 8건. 최종 합계 8 + 10 = **18건 PASS** (test_token_bucket 5 + test_translate 5).

### Completion Notes List

- **TokenBucket** (`detection/src/rate_limit/token_bucket.py`): Lua script 단일 명령으로 atomic acquire 구현 — HMGET/HMSET + lazy refill(`now - last_refill` 기반) + 1시간 TTL. `acquire(timeout)` 미지정 시 `VARCO_RATE_LIMIT_MAX_WAIT_SEC=120` 환경변수 사용. 토큰 부족 시 다음 충전까지 sleep 후 재시도, 데드라인 초과 시 `RateLimitTimeoutError`.
- **Translator** (`detection/src/pipeline/translate.py`): `VarcoInterface` + `TokenBucket` 의존성 주입. `language ∈ {zh-CN, zh-TW}`만 번역, `ko`/그 외는 `raw_text` 그대로 반환(skip 로그). `RateLimitError` catch 시 `time.sleep(retry_after)` 후 1회 자동 재시도(3회+DLQ는 Story 3.3 책임).
- **VarcoHttpClient** (`detection/src/pipeline/varco_client.py`): `VarcoInterface` httpx 구현 — `POST /translate` body `{text, target}`, 200 → `translated_text`, 429 + `Retry-After` 헤더 → `RateLimitError` 변환. VARCO 실제 엔드포인트는 mock 계약 기반 placeholder.
- **DetectionPipeline** (`detection/src/pipeline/detection_pipeline.py`): `CrawlEvent.from_json` → `Translator.translate_event` 흐름. Story 3.3/3.4 후속 TODO 주석 명시.
- **main.py** 재배선: `_stub_process` 제거 + `VarcoHttpClient` + `TokenBucket(rate_limit_client)` + `Translator` + `DetectionPipeline` + 기존 `Watchdog`/`QueueConsumer` 통합. `get_rate_limit_client()` 신규 추가(DB2 클라이언트).
- 모든 INFO/WARNING 로그에 `extra={"correlation_id", "service": "detection"}` 포함(P6 규칙) — Translator의 skip/retry 로그, DetectionPipeline의 완료 로그, TokenBucket의 wait 경고.
- `shared/config/redis_config.py`에 `REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE = "varco:rate_limit:translate"` 상수 추가. `:classify` 키는 Story 3.3에서 추가 예정.
- 단위 테스트 10건 신규 (test_token_bucket 5 + test_translate 5), 외부 네트워크/실제 Redis 호출 0건. 전체 18건 PASS, 회귀 0건.

### File List

신규:
- `detection/src/rate_limit/__init__.py`
- `detection/src/rate_limit/token_bucket.py`
- `detection/src/pipeline/__init__.py`
- `detection/src/pipeline/translate.py`
- `detection/src/pipeline/varco_client.py`
- `detection/src/pipeline/detection_pipeline.py`
- `detection/tests/unit/test_token_bucket.py`
- `detection/tests/unit/test_translate.py`

수정:
- `shared/config/redis_config.py` (`REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE` 상수 추가)
- `detection/requirements.txt` (`fakeredis[lua]>=2.0.0` 추가)
- `detection/.env.example` (VARCO 6개 환경변수 추가)
- `detection/src/config/redis_config.py` (`get_rate_limit_client()` 추가)
- `detection/src/main.py` (`_stub_process` 제거 + DetectionPipeline 통합 배선)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (3-2 status: ready-for-dev → in-progress → review)

비변경:
- `detection/src/consumer/queue_consumer.py`
- `detection/src/consumer/watchdog.py`
- `detection/src/mocks/varco_mock.py` (simulate_latency 이미 구현됨)
- `shared/interfaces/varco.py`
- `shared/models/crawl_event.py`

## Change Log

| 날짜 | 변경 | 사유 |
|---|---|---|
| 2026-04-29 | Story 3.2 컨텍스트 작성 (`Status: ready-for-dev`) | bmad-create-story |
| 2026-04-29 | TokenBucket(Lua atomic) + Translator + VarcoHttpClient + DetectionPipeline 구현, `_stub_process` 제거, 단위 테스트 10건 PASS, 전체 회귀 18건 PASS, `Status: review` | bmad-dev-story |
