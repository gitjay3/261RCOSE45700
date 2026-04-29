# Story 3.3: VARCO LLM 분류 및 재시도·DLQ 처리

Status: review

> **본 스토리 핵심:** Story 3.2가 끝낸 `Translator` 출력(한국어 텍스트)을 받아 `LLMClassifier`가 VARCO LLM API로 `is_illegal / type / confidence / reason`을 분류한다. classify 호출 실패(`TimeoutError`, `httpx.HTTPError`, `ConnectionError`)는 `RetryHandler`가 **인라인 3회 재시도**(exponential backoff 1s/2s/4s)하고, 3회 모두 실패하면 메시지를 **즉시 `posts:dlq`로 LPUSH + `posts:processing`에서 LREM + retry/processing_time 키 cleanup**한 뒤 `RetryExhaustedError`를 raise한다. `DetectionPipeline.process`의 Story 3.2 TODO(`classify`)를 본 스토리가 채운다. **이 스토리에서 RDS 저장(Story 3.4)·정확도 측정(Story 3.5)·Watchdog 변경은 하지 않는다.**
>
> **[전제 조건]** Story 3.2 `done` 또는 `review`. `detection/src/pipeline/{translate.py,detection_pipeline.py,varco_client.py}` + `rate_limit/token_bucket.py` 완성. `VarcoInterface` Protocol(`translate`, `classify`) 정의됨. `VarcoMock`이 `mode="illegal"` / `"clean"` / `"timeout"` / `"rate_limited"` 4모드 지원. `tests/fixtures/varco/mock_response_{clean,illegal,timeout}.json` 존재. Watchdog 기반 DLQ 격리(Story 3.1)와 본 스토리의 인라인 retry-DLQ는 **서로 다른 경로**임을 인지(아래 "두 DLQ 경로의 분리" 참조).

## Story

개발자로서,
게시글이 VARCO LLM으로 불법 여부와 유형이 분류되고, 실패 시 3회 재시도 후 DLQ로 격리되기를 원한다,
그래서 일시적 API 장애에도 데이터 유실 없이 파이프라인이 지속된다.

## Acceptance Criteria

1. **Given** 번역이 완료된(또는 한국어인) 게시글 텍스트가 있을 때 **When** `LLMClassifier.classify(text)`가 실행되면 **Then** VARCO LLM API를 호출하여 `ClassificationResult(is_illegal: bool, type: str, confidence: float, reason: str)`을 반환한다 (FR12, FR13, FR14).
   **And** `type`은 `{매크로_판매, 핵_배포, 계정_거래, 리세마라, 기타}` 5개 값 중 하나여야 하며, 그 외 값 수신 시 `ValueError`를 발생시킨다.
   **And** `confidence`는 `0.0 <= confidence <= 1.0` 범위여야 하며, 범위 외 값 수신 시 `ValueError`를 발생시킨다 (deferred-work L35).
   **And** classify 호출 직전 `TokenBucket(key=REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY).acquire()`로 토큰을 차감하여 분류 호출량을 제어한다(FR16, NFR14 — translate와 별도 quota).

2. **Given** classify 호출이 일시적 외부 오류(`TimeoutError`, `httpx.HTTPError`, `ConnectionError`)를 발생시킬 때 **When** `RetryHandler.execute_with_retry(callable, message, post_id, correlation_id)`가 이를 감지하면 **Then** 최대 **3회** 재시도하며 각 재시도 사이 **exponential backoff** (`backoff_seconds = base * 2^attempt` — 기본 base=1 → 1s/2s/4s)로 대기한다 (FR15, NFR11).
   **And** 1~3회차 시도 중 성공 시 즉시 결과를 반환하고 backoff은 더 이상 발생하지 않는다.
   **And** `RateLimitError`(VARCO 측 quota 거부)는 본 RetryHandler가 직접 재시도하지 **않는다** — `Translator`(Story 3.2)와 동일하게 호출 측이 `time.sleep(retry_after)` 후 1회 자동 재시도만 수행. RetryHandler는 retryable 예외 화이트리스트(아래 "재시도 대상 예외 분류" 참조)만 처리.
   **And** `ValueError`(스키마 위반 — AC #1) 같은 영구 오류는 재시도하지 **않고** 즉시 raise한다.

3. **Given** classify 호출이 retryable 예외로 4회 모두(원본 1회 + 재시도 3회) 실패할 때 **When** `RetryHandler`가 재시도 한도를 초과하면 **Then** 다음 순서로 정확히 한 번씩 실행한다(원자성은 deferred — 단일 instance MVP):
   1. `LPUSH posts:dlq <message>`
   2. `LREM posts:processing 1 <message>` (Story 3.1 ACK 패턴과 동일 count=1)
   3. `DELETE posts:retry:{post_id}` + `DELETE posts:processing_time:{post_id}` (Story 3.1 cleanup 패턴 재사용)
   4. ERROR 레벨 구조화 로그 출력: `"DLQ 이동 — VARCO classify 재시도 한도 초과 (attempts=4)"` + `extra={"post_id", "correlation_id", "service", "last_error_type"}` (Story 3.1 review patch P1 패턴)
   5. `RetryExhaustedError(post_id, attempts=4, last_error)` 예외를 raise하여 호출자(`DetectionPipeline.process`)에게 실패를 알림 — `QueueConsumer`의 기존 except 핸들러가 ERROR 로그만 남기고 LREM은 호출하지 않음(이미 retry_handler가 처리).

4. **Given** `detection/src/pipeline/detection_pipeline.py`의 Story 3.2 TODO(`classify(translated)`) 라인이 존재할 때 **When** 본 스토리 작업이 완료되면 **Then** `DetectionPipeline.process(message)`가 다음 흐름을 수행한다:
   ```
   event = CrawlEvent.from_json(message)
   translated = self._translator.translate_event(event)
   classification = self._retry_handler.execute_with_retry(
       lambda: self._classifier.classify(translated),
       message=message,
       post_id=event.post_id,
       correlation_id=event.correlation_id,
   )
   _logger.info(
       "classification completed — is_illegal=%s type=%s confidence=%.3f",
       classification.is_illegal, classification.type, classification.confidence,
       extra={"correlation_id": event.correlation_id, "service": "detection"},
   )
   # TODO(Story 3.4): detection_repository.save(event, classification, model_version)
   ```
   **And** `LLMClassifier`와 `RetryHandler`는 `DetectionPipeline.__init__`에서 의존성으로 주입되며, `main.py`에서 wiring한다 (Story 3.2 패턴 동일).

5. **Given** `detection/tests/unit/test_retry_handler.py`가 실행될 때 **When** 테스트를 실행하면 **Then** 다음 5개 시나리오가 모두 PASS한다 (실제 Redis 호출 0건 — `MagicMock`):
   - **첫 시도 성공** → 호출 1회 + sleep 0회 + DLQ 미호출
   - **2회차 성공** → 호출 2회 + sleep 1회(`time.sleep(1.0)` monkeypatch 검증) + DLQ 미호출
   - **3회 모두 실패 → 4회차도 실패 = 한도 초과** → 호출 4회 + DLQ LPUSH + processing LREM + retry/processing_time DELETE 호출 + `RetryExhaustedError` raise
   - **non-retryable 예외(`ValueError`)** → 호출 1회 + 즉시 re-raise + DLQ 미호출 + sleep 0회
   - **`RateLimitError`** → 호출 1회 + 즉시 re-raise + DLQ 미호출(Translator/호출자 책임)

6. **Given** `detection/tests/unit/test_llm_classifier.py`가 실행될 때 **When** 테스트를 실행하면 **Then** 다음 5개 시나리오가 모두 PASS한다 (`VarcoMock` + `MagicMock` 토큰 버킷):
   - `VarcoMock("clean").classify(...)` → `is_illegal=False, type="기타", confidence=0.92`(fixture) 반환 + `bucket.acquire()` 1회 호출
   - `VarcoMock("illegal").classify(...)` → `is_illegal=True, type="매크로_판매", confidence=0.95` 반환
   - VARCO 응답 `type="invalid_type"` → `ValueError("invalid type: invalid_type")` raise (`MagicMock(spec=VarcoInterface)` + `classify.return_value = ClassificationResult(..., type="invalid_type", ...)` 패턴)
   - VARCO 응답 `confidence=1.5` → `ValueError("confidence out of range: 1.5")` raise
   - VARCO 응답 `confidence=-0.1` → `ValueError("confidence out of range: -0.1")` raise

7. **Given** `detection/tests/integration/test_varco_pipeline.py`가 실행될 때 **When** 테스트를 실행하면 **Then** 다음 4개 통합 시나리오가 모두 PASS한다 (실제 Redis 호출 0건 — `MagicMock(redis.Redis)`, 외부 네트워크 0건 — `VarcoMock`만 사용):
   - **clean path**: `language="ko"` 이벤트 → translate 스킵 → classify(clean) → `is_illegal=False` 결과 로그 출력 + LREM(processing) 호출(`QueueConsumer.run_once` 통해 검증) + DLQ 미호출
   - **illegal path**: `language="zh-CN"` 이벤트 → translate(zh-CN→ko) → classify(illegal) → `is_illegal=True, type="매크로_판매"` 결과 로그 + LREM(processing) 호출 + DLQ 미호출
   - **timeout → DLQ path**: `VarcoMock(mode="timeout")` → classify가 4회 모두 `TimeoutError` → DLQ LPUSH + processing LREM + retry/processing_time DELETE + `RetryExhaustedError` raise (consumer가 ERROR 로그)
   - **mock_response_timeout fixture 사용 검증**: 위 timeout path에서 `VarcoMock(mode="timeout")`이 fixture `mock_response_timeout.json`을 로드함을 확인(epics.md AC #3 명시 요건)

8. **Given** 모든 신규 코드의 logger 호출에서 **When** logger를 통해 로그가 기록되면 **Then** `extra={"correlation_id": event.correlation_id, "service": "detection"}`이 모든 INFO/WARNING/ERROR 레벨에 포함된다 (architecture.md P6 — Story 3.1 review patch + Story 3.2 동일 패턴). DLQ 로그에는 `post_id` + `last_error_type` 추가 필드 포함.

9. **Given** 검증 환경에서 **When** `cd detection && ./.venv/bin/pytest tests/ -v`를 실행하면 **Then** Story 3.1+3.2 기존 18건 + 신규 14건(retry 5 + classifier 5 + integration 4) = **총 32건이 모두 PASS**하며 외부 네트워크/실제 Redis 호출이 0건이다.

> **AC 출처:** epics.md Story 3.3 (L464-478). AC #1의 type/confidence 검증은 deferred-work L35(`ClassificationResult.confidence 범위 검증`) + L32(`VarcoInterface 메서드 예외 계약`)에 따라 본 스토리에서 해소. AC #2의 exponential backoff(1s/2s/4s)·retryable 예외 화이트리스트, AC #3의 `RetryExhaustedError` 신설·정리 순서, AC #4의 wiring 코드는 architecture.md(NFR11 3회 재시도, P6 로깅) + Story 3.1 review patch(성공 cleanup, P6 cid) + Story 3.2 의존성 주입 패턴 + 표준 retry 알고리즘에 기반해 구체화. **VARCO LLM API 실제 엔드포인트/auth 헤더 명세는 미제공 — `VarcoHttpClient.classify()`는 mock 계약(`POST /classify` body `{text}`, response `{is_illegal, type, confidence, reason}`) 기반 placeholder. 실제 명세 확보 시 `VarcoHttpClient.classify` 메서드만 수정.**

## Tasks / Subtasks

- [x] **Task 1: shared 상수 추가 및 환경변수 정의** (AC: #1, #2)
  - [x] 1.1 `shared/config/redis_config.py`에 classify 토큰 버킷 키 + retry 설정 상수 추가:
    ```python
    REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY: str = "varco:rate_limit:classify"
    ```
    > Story 3.2 `:translate`와 별도 quota — VARCO Translation/LLM이 분리된 endpoint이므로 토큰 버킷도 분리. 단일 `varco:rate_limit` 키를 공유하면 translate 호출이 classify 호출 quota를 잠식.
  - [x] 1.2 `detection/.env.example`에 환경변수 추가:
    ```
    # Story 3.3 — VARCO LLM Classification
    VARCO_CLASSIFY_TIMEOUT_SEC=10
    VARCO_LLM_MODEL_VERSION=varco-llm-v1
    VARCO_RATE_LIMIT_CLASSIFY_CAPACITY=60
    VARCO_RATE_LIMIT_CLASSIFY_REFILL_PER_SEC=1
    RETRY_MAX_ATTEMPTS=3
    RETRY_BACKOFF_BASE_SEC=1
    ```
    > `VARCO_LLM_MODEL_VERSION`은 Story 3.4 `detections.model_version` 컬럼에 기록될 값. 본 스토리는 환경변수만 정의. `RETRY_MAX_ATTEMPTS=3`은 NFR11 — 원본 1회 + 재시도 3회 = 총 4회 호출. `RETRY_BACKOFF_BASE_SEC=1` → 대기 1s/2s/4s.

- [x] **Task 2: VarcoInterface 예외 계약 문서화** (AC: #2 — deferred-work L32 해소)
  - [x] 2.1 `shared/interfaces/varco.py`에 docstring으로 예외 계약 명시(코드 변경 없음 — 시그니처는 유지):
    ```python
    class VarcoInterface(Protocol):
        def translate(self, text: str) -> str:
            """텍스트를 한국어로 번역.
            
            Raises:
                RateLimitError: VARCO API quota 초과 (호출자가 retry_after 후 1회 자동 재시도).
                TimeoutError: HTTP 호출 타임아웃 (RetryHandler retryable).
                ConnectionError / httpx.HTTPError: 네트워크/HTTP 오류 (RetryHandler retryable).
            """
            ...
        
        def classify(self, text: str) -> ClassificationResult:
            """텍스트의 불법 여부와 유형을 분류.
            
            Raises:
                RateLimitError: VARCO API quota 초과.
                TimeoutError / ConnectionError / httpx.HTTPError: RetryHandler retryable.
                ValueError: 응답 스키마 위반 (type/confidence 검증 실패) — non-retryable.
            """
            ...
    ```
  - [x] 2.2 본 변경은 코드 동작 비변경 — 기존 Story 3.1/3.2 테스트 회귀 0건 확인.

- [x] **Task 3: LLMClassifier 구현** (AC: #1, #6)
  - [x] 3.1 `detection/src/pipeline/llm_classifier.py` 신규:
    ```python
    from __future__ import annotations
    
    import os
    
    from detection.src.rate_limit.token_bucket import TokenBucket
    from shared.interfaces.varco import ClassificationResult, VarcoInterface
    from shared.structured_logger import get_logger
    
    _SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
    _ALLOWED_TYPES = frozenset({"매크로_판매", "핵_배포", "계정_거래", "리세마라", "기타"})
    _logger = get_logger(__name__)
    
    
    class LLMClassifier:
        def __init__(
            self,
            varco: VarcoInterface,
            token_bucket: TokenBucket,
            model_version: str | None = None,
        ) -> None:
            self._varco = varco
            self._bucket = token_bucket
            self._model_version = model_version or os.environ.get(
                "VARCO_LLM_MODEL_VERSION", "varco-llm-v1"
            )
        
        @property
        def model_version(self) -> str:
            return self._model_version
        
        def classify(self, text: str) -> ClassificationResult:
            """text를 분류. AC #1 검증 포함."""
            self._bucket.acquire()
            result = self._varco.classify(text)
            
            if result.type not in _ALLOWED_TYPES:
                raise ValueError(f"invalid type: {result.type}")
            if not (0.0 <= result.confidence <= 1.0):
                raise ValueError(f"confidence out of range: {result.confidence}")
            
            return result
    ```
  - [x] 3.2 핵심 설계 결정:
    - **Translator와 동일한 구조** — `VarcoInterface` 의존성 주입 + `TokenBucket.acquire()` → API 호출 → 검증 → 반환.
    - **검증은 classify() 내부에서** — VARCO 응답이 잘못된 경우 즉시 `ValueError`. RetryHandler가 이 예외를 retryable 화이트리스트에 포함하지 **않음**(영구 오류).
    - **`model_version` property** — Story 3.4 `detection_repository.save()`에서 사용. 본 스토리는 노출만, 사용 안 함.
    - **`RateLimitError` catch 안 함** — Translator(Story 3.2)와 다르게, classify의 RateLimitError는 RetryHandler에 전파되지 않고 호출자(DetectionPipeline)가 처리하거나 그대로 raise. 본 스토리는 classify 내부에서 RateLimitError catch 안 함(정책: classify rate limit은 token bucket이 사전 차단하므로 VARCO 측 거부는 quota 동기화 어긋남 → 호출 실패로 간주).

- [x] **Task 4: RetryHandler 구현** (AC: #2, #3, #5)
  - [x] 4.1 `detection/src/retry/__init__.py` 신규(빈 파일).
  - [x] 4.2 `detection/src/retry/retry_handler.py` 신규:
    ```python
    from __future__ import annotations
    
    import os
    import time
    from collections.abc import Callable
    from typing import TypeVar
    
    import httpx
    import redis
    
    from detection.src.consumer.watchdog import processing_time_key, retry_key
    from detection.src.mocks.varco_mock import RateLimitError
    from shared.config.redis_config import (
        REDIS_KEY_POSTS_DLQ,
        REDIS_KEY_POSTS_PROCESSING,
    )
    from shared.structured_logger import get_logger
    
    _SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
    _MAX_ATTEMPTS = int(os.environ.get("RETRY_MAX_ATTEMPTS", "3"))
    _BACKOFF_BASE = float(os.environ.get("RETRY_BACKOFF_BASE_SEC", "1"))
    _logger = get_logger(__name__)
    
    # 재시도 대상 예외 화이트리스트 — 일시적 외부 오류만.
    # RateLimitError / ValueError 는 의도적으로 제외(아래 docstring 참조).
    _RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
        TimeoutError,
        ConnectionError,
        httpx.HTTPError,
    )
    
    T = TypeVar("T")
    
    
    class RetryExhaustedError(Exception):
        """재시도 한도 초과 후 DLQ 이동 완료 시 raise — QueueConsumer가 catch."""
        
        def __init__(self, post_id: str, attempts: int, last_error: BaseException) -> None:
            self.post_id = post_id
            self.attempts = attempts
            self.last_error = last_error
            super().__init__(
                f"retry exhausted after {attempts} attempts for post_id={post_id}: "
                f"{type(last_error).__name__}: {last_error}"
            )
    
    
    class RetryHandler:
        """retryable 예외를 exponential backoff으로 재시도. 한도 초과 시 DLQ 이동."""
        
        def __init__(self, redis_client: redis.Redis) -> None:
            self._redis = redis_client
        
        def execute_with_retry(
            self,
            func: Callable[[], T],
            *,
            message: str,
            post_id: str,
            correlation_id: str,
        ) -> T:
            last_error: BaseException | None = None
            total_attempts = _MAX_ATTEMPTS + 1  # 원본 1 + 재시도 N
            
            for attempt in range(total_attempts):
                try:
                    return func()
                except _RETRYABLE_EXCEPTIONS as exc:
                    last_error = exc
                    if attempt < total_attempts - 1:
                        backoff = _BACKOFF_BASE * (2 ** attempt)
                        _logger.warning(
                            "VARCO classify 재시도 — attempt=%d/%d, backoff=%.1fs, error=%s",
                            attempt + 1, total_attempts, backoff, type(exc).__name__,
                            extra={
                                "post_id": post_id,
                                "correlation_id": correlation_id,
                                "service": _SERVICE_NAME,
                            },
                        )
                        time.sleep(backoff)
                # RateLimitError / ValueError 등 비-retryable은 except 절에 안 잡힘 → 자동 propagate
            
            # 한도 초과 — DLQ 이동
            assert last_error is not None  # for mypy: 위 루프가 한 번이라도 except에 진입했음을 보장
            self._move_to_dlq(message, post_id, correlation_id, last_error, total_attempts)
            raise RetryExhaustedError(post_id, total_attempts, last_error)
        
        def _move_to_dlq(
            self,
            message: str,
            post_id: str,
            correlation_id: str,
            last_error: BaseException,
            attempts: int,
        ) -> None:
            self._redis.lpush(REDIS_KEY_POSTS_DLQ, message)
            self._redis.lrem(REDIS_KEY_POSTS_PROCESSING, 1, message)
            self._redis.delete(retry_key(post_id))
            self._redis.delete(processing_time_key(post_id))
            _logger.error(
                "DLQ 이동 — VARCO classify 재시도 한도 초과 (attempts=%d)",
                attempts,
                extra={
                    "post_id": post_id,
                    "correlation_id": correlation_id,
                    "service": _SERVICE_NAME,
                    "last_error_type": type(last_error).__name__,
                },
            )
    ```
  - [x] 4.3 핵심 설계 결정:
    - **`_MAX_ATTEMPTS=3`은 재시도 횟수만** — 총 호출 횟수는 원본 1 + 재시도 3 = **4회**. epics.md "3회 재시도 후 DLQ" 정확 해석.
    - **Exponential backoff `base * 2^attempt`** — attempt 0 실패 후 1s, attempt 1 실패 후 2s, attempt 2 실패 후 4s. 마지막 시도(attempt 3) 후에는 backoff 없이 즉시 DLQ.
    - **재시도 대상 예외 화이트리스트** — `TimeoutError`, `ConnectionError`, `httpx.HTTPError` 만. `RateLimitError`(quota — 다른 정책)·`ValueError`(영구 오류 — 재시도해도 같은 결과)·`AssertionError`(코드 버그)는 제외.
    - **`processing_time_key` / `retry_key` 재사용** — Story 3.1 `detection/src/consumer/watchdog.py`에서 이미 `def`로 export됨. 재구현 금지(QueueConsumer가 동일 함수 사용).
    - **DLQ 이동의 비원자성은 deferred** — Lua script 도입은 Story 3.5 측정 후. 단일 instance MVP에서 race window는 ms 단위(Story 3.1 D1 deferred 일관).
    - **`RetryExhaustedError` raise** — `DetectionPipeline.process` → `QueueConsumer.run_once`의 except 블록까지 전파됨. QueueConsumer는 ERROR 로그만 남기고 LREM 호출 안 함(이미 retry_handler가 LREM). 따라서 double-LREM 없음.
    - **`assert last_error is not None`** — `_RETRYABLE_EXCEPTIONS`에 catch된 경우에만 4회 루프가 모두 실패할 수 있으므로 last_error는 반드시 non-None. mypy/타입 안전성 확보.

- [x] **Task 5: VarcoHttpClient.classify 구현** (AC: #1)
  - [x] 5.1 `detection/src/pipeline/varco_client.py` 수정 — `classify()` `NotImplementedError`를 실제 구현으로 교체:
    ```python
    def classify(self, text: str) -> ClassificationResult:
        timeout = float(os.environ.get("VARCO_CLASSIFY_TIMEOUT_SEC", "10"))
        response = self._client.post("/classify", json={"text": text}, timeout=timeout)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "30"))
            raise RateLimitError(retry_after)
        response.raise_for_status()
        data = response.json()
        return ClassificationResult(
            is_illegal=bool(data["is_illegal"]),
            type=str(data["type"]),
            confidence=float(data["confidence"]),
            reason=str(data["reason"]),
        )
    ```
    > VARCO 실제 엔드포인트(`/classify`)·request body 키(`text`)·response 필드 4개는 mock 계약(`mock_response_clean.json` `classification` 객체)을 따랐다. 실제 API spec 확보 시 본 메서드만 수정.
  - [x] 5.2 `_client`는 Story 3.2의 단일 `httpx.Client(base_url, headers, timeout)` 인스턴스 재사용. `VARCO_CLASSIFY_TIMEOUT_SEC`은 `_client.post(timeout=...)`로 per-request override(translate timeout과 분리).

- [x] **Task 6: DetectionPipeline 통합** (AC: #4, #8)
  - [x] 6.1 `detection/src/pipeline/detection_pipeline.py` 수정 — classify + retry 호출 추가:
    ```python
    from __future__ import annotations
    
    import os
    
    from detection.src.pipeline.llm_classifier import LLMClassifier
    from detection.src.pipeline.translate import Translator
    from detection.src.retry.retry_handler import RetryHandler
    from shared.models.crawl_event import CrawlEvent
    from shared.structured_logger import get_logger
    
    _SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
    _logger = get_logger(__name__)
    
    
    class DetectionPipeline:
        def __init__(
            self,
            translator: Translator,
            classifier: LLMClassifier,
            retry_handler: RetryHandler,
        ) -> None:
            self._translator = translator
            self._classifier = classifier
            self._retry_handler = retry_handler
        
        def process(self, message: str) -> None:
            event = CrawlEvent.from_json(message)
            translated = self._translator.translate_event(event)
            _logger.info(
                "translation completed — len=%d",
                len(translated),
                extra={"correlation_id": event.correlation_id, "service": _SERVICE_NAME},
            )
            
            classification = self._retry_handler.execute_with_retry(
                lambda: self._classifier.classify(translated),
                message=message,
                post_id=event.post_id,
                correlation_id=event.correlation_id,
            )
            _logger.info(
                "classification completed — is_illegal=%s type=%s confidence=%.3f",
                classification.is_illegal,
                classification.type,
                classification.confidence,
                extra={"correlation_id": event.correlation_id, "service": _SERVICE_NAME},
            )
            # TODO(Story 3.4): detection_repository.save(event, classification, self._classifier.model_version)
    ```
  - [x] 6.2 핵심: `RetryExhaustedError`는 catch하지 않음 — `QueueConsumer.run_once`의 generic except가 ERROR 로그만 남기고 LREM 호출 안 함(retry_handler가 이미 LREM 완료). 별도 처리 불필요.

- [x] **Task 7: main.py 재배선** (AC: #4)
  - [x] 7.1 `detection/src/main.py` 수정 — `LLMClassifier` + classify용 `TokenBucket` + `RetryHandler` 추가:
    ```python
    from __future__ import annotations
    
    import threading
    
    from detection.src.config.redis_config import get_mq_client, get_rate_limit_client
    from detection.src.consumer.queue_consumer import QueueConsumer
    from detection.src.consumer.watchdog import Watchdog
    from detection.src.pipeline.detection_pipeline import DetectionPipeline
    from detection.src.pipeline.llm_classifier import LLMClassifier
    from detection.src.pipeline.translate import Translator
    from detection.src.pipeline.varco_client import VarcoHttpClient
    from detection.src.rate_limit.token_bucket import TokenBucket
    from detection.src.retry.retry_handler import RetryHandler
    from shared.config.redis_config import (
        REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY,
        REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE,
    )
    from shared.structured_logger import get_logger
    
    _logger = get_logger(__name__)
    
    
    def main() -> None:
        mq_client = get_mq_client()
        rate_limit_client = get_rate_limit_client()
        
        varco = VarcoHttpClient()
        translate_bucket = TokenBucket(
            rate_limit_client, key=REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE,
        )
        classify_bucket = TokenBucket(
            rate_limit_client, key=REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY,
        )
        translator = Translator(varco, translate_bucket)
        classifier = LLMClassifier(varco, classify_bucket)
        retry_handler = RetryHandler(mq_client)
        pipeline = DetectionPipeline(translator, classifier, retry_handler)
        
        watchdog = Watchdog(mq_client)
        consumer = QueueConsumer(mq_client, pipeline.process, watchdog=watchdog)
        
        watchdog_thread = threading.Thread(target=watchdog.run_forever, daemon=True)
        watchdog_thread.start()
        
        consumer.run_forever()
    
    
    if __name__ == "__main__":
        main()
    ```
  - [x] 7.2 핵심: classify 토큰 버킷은 **별도 `TokenBucket` 인스턴스** + 별도 키. `VARCO_RATE_LIMIT_CLASSIFY_CAPACITY` / `_REFILL_PER_SEC` 환경변수는 `TokenBucket(capacity=..., refill_per_sec=...)`로 명시 전달하지 않으면 `VARCO_RATE_LIMIT_CAPACITY` / `_REFILL_PER_SEC` 기본값을 공유함 — **본 스토리는 단순화를 위해 공유 기본값을 사용**(deferred: classify-specific quota 분리는 Story 3.5 측정 후). 환경변수만 정의하고 코드는 공유 기본값 사용.

- [x] **Task 8: RetryHandler 단위 테스트** (AC: #5)
  - [x] 8.1 `detection/tests/unit/test_retry_handler.py` 신규:
    ```python
    from __future__ import annotations
    
    from unittest.mock import MagicMock, call, patch
    
    import pytest
    
    from detection.src.mocks.varco_mock import RateLimitError
    from detection.src.retry.retry_handler import (
        RetryExhaustedError,
        RetryHandler,
    )
    from shared.config.redis_config import (
        REDIS_KEY_POSTS_DLQ,
        REDIS_KEY_POSTS_PROCESSING,
    )
    
    _MESSAGE = '{"post_id":"tieba_001","correlation_id":"cid-001"}'
    _POST_ID = "tieba_001"
    _CID = "cid-001"
    
    
    def test_first_attempt_success() -> None:
        mock_redis = MagicMock()
        handler = RetryHandler(mock_redis)
        func = MagicMock(return_value="ok")
        
        result = handler.execute_with_retry(
            func, message=_MESSAGE, post_id=_POST_ID, correlation_id=_CID,
        )
        
        assert result == "ok"
        assert func.call_count == 1
        mock_redis.lpush.assert_not_called()
    
    
    def test_second_attempt_success_with_backoff() -> None:
        mock_redis = MagicMock()
        handler = RetryHandler(mock_redis)
        func = MagicMock(side_effect=[TimeoutError("first fail"), "ok"])
        
        with patch("detection.src.retry.retry_handler.time.sleep") as mock_sleep:
            result = handler.execute_with_retry(
                func, message=_MESSAGE, post_id=_POST_ID, correlation_id=_CID,
            )
        
        assert result == "ok"
        assert func.call_count == 2
        mock_sleep.assert_called_once_with(1.0)  # 1 * 2^0
        mock_redis.lpush.assert_not_called()
    
    
    def test_retry_exhausted_moves_to_dlq() -> None:
        mock_redis = MagicMock()
        handler = RetryHandler(mock_redis)
        func = MagicMock(side_effect=TimeoutError("persistent"))
        
        with patch("detection.src.retry.retry_handler.time.sleep") as mock_sleep:
            with pytest.raises(RetryExhaustedError) as exc_info:
                handler.execute_with_retry(
                    func, message=_MESSAGE, post_id=_POST_ID, correlation_id=_CID,
                )
        
        assert func.call_count == 4  # 원본 1 + 재시도 3
        assert mock_sleep.call_count == 3  # backoff 1s, 2s, 4s
        mock_sleep.assert_has_calls([call(1.0), call(2.0), call(4.0)])
        mock_redis.lpush.assert_called_once_with(REDIS_KEY_POSTS_DLQ, _MESSAGE)
        mock_redis.lrem.assert_called_once_with(REDIS_KEY_POSTS_PROCESSING, 1, _MESSAGE)
        # retry_key + processing_time_key 둘 다 DELETE
        assert mock_redis.delete.call_count == 2
        assert exc_info.value.post_id == _POST_ID
        assert exc_info.value.attempts == 4
        assert isinstance(exc_info.value.last_error, TimeoutError)
    
    
    def test_non_retryable_value_error_propagates_immediately() -> None:
        mock_redis = MagicMock()
        handler = RetryHandler(mock_redis)
        func = MagicMock(side_effect=ValueError("bad schema"))
        
        with patch("detection.src.retry.retry_handler.time.sleep") as mock_sleep:
            with pytest.raises(ValueError, match="bad schema"):
                handler.execute_with_retry(
                    func, message=_MESSAGE, post_id=_POST_ID, correlation_id=_CID,
                )
        
        assert func.call_count == 1
        mock_sleep.assert_not_called()
        mock_redis.lpush.assert_not_called()
    
    
    def test_rate_limit_error_propagates_immediately() -> None:
        mock_redis = MagicMock()
        handler = RetryHandler(mock_redis)
        func = MagicMock(side_effect=RateLimitError(retry_after=30))
        
        with patch("detection.src.retry.retry_handler.time.sleep") as mock_sleep:
            with pytest.raises(RateLimitError):
                handler.execute_with_retry(
                    func, message=_MESSAGE, post_id=_POST_ID, correlation_id=_CID,
                )
        
        assert func.call_count == 1
        mock_sleep.assert_not_called()
        mock_redis.lpush.assert_not_called()
    ```
  - [x] 8.2 핵심: `time.sleep` monkeypatch로 wall-clock 의존성 제거. 모든 Redis 호출은 `MagicMock` — 실제 Redis 연결 0건.

- [x] **Task 9: LLMClassifier 단위 테스트** (AC: #6)
  - [x] 9.1 `detection/tests/unit/test_llm_classifier.py` 신규:
    ```python
    from __future__ import annotations
    
    from unittest.mock import MagicMock
    
    import pytest
    
    from detection.src.mocks.varco_mock import VarcoMock
    from detection.src.pipeline.llm_classifier import LLMClassifier
    from shared.interfaces.varco import ClassificationResult
    
    
    def test_classifies_clean_text() -> None:
        bucket = MagicMock()
        varco = VarcoMock(mode="clean")
        classifier = LLMClassifier(varco, bucket)
        
        result = classifier.classify("정상적인 게시글")
        
        assert result.is_illegal is False
        assert result.type == "기타"
        assert result.confidence == 0.92
        bucket.acquire.assert_called_once()
    
    
    def test_classifies_illegal_text() -> None:
        bucket = MagicMock()
        varco = VarcoMock(mode="illegal")
        classifier = LLMClassifier(varco, bucket)
        
        result = classifier.classify("매크로 판매합니다")
        
        assert result.is_illegal is True
        assert result.type == "매크로_판매"
        assert result.confidence == 0.95
    
    
    def test_invalid_type_raises_value_error() -> None:
        bucket = MagicMock()
        varco = MagicMock()
        varco.classify.return_value = ClassificationResult(
            is_illegal=True, type="invalid_type", confidence=0.9, reason="...",
        )
        classifier = LLMClassifier(varco, bucket)
        
        with pytest.raises(ValueError, match="invalid type: invalid_type"):
            classifier.classify("text")
    
    
    def test_confidence_above_one_raises_value_error() -> None:
        bucket = MagicMock()
        varco = MagicMock()
        varco.classify.return_value = ClassificationResult(
            is_illegal=True, type="기타", confidence=1.5, reason="...",
        )
        classifier = LLMClassifier(varco, bucket)
        
        with pytest.raises(ValueError, match="confidence out of range: 1.5"):
            classifier.classify("text")
    
    
    def test_confidence_below_zero_raises_value_error() -> None:
        bucket = MagicMock()
        varco = MagicMock()
        varco.classify.return_value = ClassificationResult(
            is_illegal=False, type="기타", confidence=-0.1, reason="...",
        )
        classifier = LLMClassifier(varco, bucket)
        
        with pytest.raises(ValueError, match="confidence out of range: -0.1"):
            classifier.classify("text")
    ```
  - [x] 9.2 핵심: `VarcoMock`은 fixture 로드 — 실제 `mock_response_clean.json` / `mock_response_illegal.json`이 의도한 값을 반환하는지 검증. `MagicMock(spec=...)` 사용 시 fixture 우회.

- [x] **Task 10: 통합 테스트** (AC: #7)
  - [x] 10.1 `detection/tests/integration/__init__.py` 신규(빈 파일).
  - [x] 10.2 `detection/tests/integration/test_varco_pipeline.py` 신규:
    ```python
    from __future__ import annotations
    
    from unittest.mock import MagicMock, patch
    
    import pytest
    
    from detection.src.consumer.queue_consumer import QueueConsumer
    from detection.src.consumer.watchdog import Watchdog
    from detection.src.mocks.varco_mock import VarcoMock
    from detection.src.pipeline.detection_pipeline import DetectionPipeline
    from detection.src.pipeline.llm_classifier import LLMClassifier
    from detection.src.pipeline.translate import Translator
    from detection.src.retry.retry_handler import RetryExhaustedError, RetryHandler
    from shared.config.redis_config import (
        REDIS_KEY_POSTS_DLQ,
        REDIS_KEY_POSTS_PROCESSING,
    )
    from shared.models.crawl_event import CrawlEvent
    
    
    def _make_message(language: str, post_id: str = "tieba_001") -> tuple[str, CrawlEvent]:
        event = CrawlEvent(
            post_id=post_id,
            source_id="tieba_freestyle",
            site_name="贴吧 (자유게시판)",
            raw_text="매크로 판매합니다" if language == "ko" else "我要卖外挂",
            language=language,
            detected_at="2026-04-29T10:00:00Z",
            correlation_id=f"cid-{post_id}",
        )
        return event.to_json(), event
    
    
    def _build_pipeline(varco: VarcoMock, mock_redis: MagicMock) -> DetectionPipeline:
        bucket = MagicMock()  # 토큰 버킷은 unit 테스트가 검증 — 통합에서는 no-op
        translator = Translator(varco, bucket)
        classifier = LLMClassifier(varco, bucket)
        retry_handler = RetryHandler(mock_redis)
        return DetectionPipeline(translator, classifier, retry_handler)
    
    
    def test_clean_korean_post_full_pipeline() -> None:
        mock_redis = MagicMock()
        message, event = _make_message("ko")
        mock_redis.brpoplpush.return_value = message
        
        varco = VarcoMock(mode="clean")
        pipeline = _build_pipeline(varco, mock_redis)
        consumer = QueueConsumer(mock_redis, pipeline.process)
        
        result = consumer.run_once()
        
        assert result is True
        # 정상 처리 → LREM 호출(QueueConsumer ack) + DLQ 미호출
        mock_redis.lrem.assert_called_once_with(REDIS_KEY_POSTS_PROCESSING, 1, message)
        mock_redis.lpush.assert_not_called()
    
    
    def test_illegal_chinese_post_full_pipeline() -> None:
        mock_redis = MagicMock()
        message, event = _make_message("zh-CN", post_id="tieba_002")
        mock_redis.brpoplpush.return_value = message
        
        varco = VarcoMock(mode="illegal")
        pipeline = _build_pipeline(varco, mock_redis)
        consumer = QueueConsumer(mock_redis, pipeline.process)
        
        result = consumer.run_once()
        
        assert result is True
        mock_redis.lrem.assert_called_once_with(REDIS_KEY_POSTS_PROCESSING, 1, message)
        mock_redis.lpush.assert_not_called()  # DLQ 미호출
    
    
    def test_timeout_path_moves_to_dlq() -> None:
        mock_redis = MagicMock()
        message, event = _make_message("ko", post_id="tieba_003")
        mock_redis.brpoplpush.return_value = message
        
        varco = VarcoMock(mode="timeout")
        pipeline = _build_pipeline(varco, mock_redis)
        consumer = QueueConsumer(mock_redis, pipeline.process)
        
        with patch("detection.src.retry.retry_handler.time.sleep"):
            result = consumer.run_once()
        
        assert result is True
        # retry_handler가 DLQ LPUSH + processing LREM 수행
        mock_redis.lpush.assert_called_once_with(REDIS_KEY_POSTS_DLQ, message)
        # LREM은 retry_handler가 1회 호출 — QueueConsumer는 RetryExhaustedError catch하므로 추가 호출 없음
        lrem_calls = [
            c for c in mock_redis.lrem.call_args_list
            if c == ((REDIS_KEY_POSTS_PROCESSING, 1, message),)
        ]
        assert len(lrem_calls) == 1
        # retry_key + processing_time_key DELETE (consumer cleanup은 RetryExhaustedError로 미실행)
        assert mock_redis.delete.call_count == 2
    
    
    def test_timeout_fixture_loaded_by_varco_mock() -> None:
        """epics.md AC #3 — mock_response_timeout.json fixture 로드 검증."""
        varco = VarcoMock(mode="timeout")
        assert varco._data.get("error") == "timeout"  # type: ignore[attr-defined]
        assert varco._data.get("latency_ms") == 30000  # type: ignore[attr-defined]
        with pytest.raises(TimeoutError, match="VARCO API timeout"):
            varco.classify("anything")
    ```
  - [x] 10.3 핵심:
    - **`MagicMock(redis.Redis)` 사용** — 실제 Redis 호출 0건. fixture 매핑(`brpoplpush.return_value`, `lrem.assert_*`)으로 호출 검증.
    - **`QueueConsumer.run_once()` 통해 검증** — 메인 진입점이 retry_handler까지 포함한 전체 흐름을 정상 호출하는지 확인.
    - **timeout path에서 `RetryExhaustedError` 전파 후 LREM 중복 검증** — QueueConsumer의 except 핸들러가 LREM을 호출 안 하는지 확인(retry_handler가 이미 LREM 했으므로 double-LREM 방지).
    - **`varco._data` private 접근** — type: ignore 주석 추가. 통합 테스트에서만 fixture 검증 목적으로 허용.

- [x] **Task 11: 검증 및 마무리**
  - [x] 11.1 `cd detection && ./.venv/bin/pytest tests/ -v` → Story 3.1+3.2 기존 18건 + 신규 14건 = **총 32건 PASS**
  - [x] 11.2 `_bmad-output/implementation-artifacts/sprint-status.yaml`의 `3-3-varco-llm-분류-및-재시도-dlq-처리` 상태 갱신: `ready-for-dev → in-progress → review`(dev 진행 시)
  - [x] 11.3 `epic-3` 상태는 이미 `in-progress` — 변경 없음

## Dev Notes

### 본 스토리 범위 (Scope Boundary)

| 이번 스토리에서 한다 | 이번 스토리에서 **하지 않는다** |
|---|---|
| `pipeline/llm_classifier.py` — VARCO LLM classify + type/confidence 검증 | `storage/detection_repository.py` — RDS 저장 → Story 3.4 |
| `retry/retry_handler.py` — exponential backoff 3회 재시도 + DLQ 이동 | DB `(post_id, model_version)` UniqueConstraint → Story 3.4 |
| `pipeline/varco_client.py` `classify()` 실제 구현(httpx) | 정확도 측정(Precision/Recall) → Story 3.5 |
| `DetectionPipeline.process` classify 단계 추가 + `RetryHandler` 통합 | Watchdog stale-recovery 로직 변경(Story 3.1 기존 유지) |
| `main.py`에 classify 토큰 버킷 + RetryHandler wiring | `varco:rate_limit:classify` capacity/refill 별도 튜닝 → Story 3.5 측정 후 |
| `shared/config/redis_config.py`에 `REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY` 상수 | `VarcoMock` mode 추가/변경(현재 4모드 그대로 사용) |
| `VarcoInterface` docstring 예외 계약 명시 | API spec 변경(시그니처 비변경) |
| 단위 테스트 10건(retry 5 + classifier 5) + 통합 테스트 4건 | 실제 VARCO API 통합 테스트 — 운영 검증 시점 |

### 두 DLQ 경로의 분리 (반드시 이해 필요)

| 경로 | 트리거 | 카운터 | 위치 | DLQ LPUSH 주체 |
|---|---|---|---|---|
| **Watchdog stale-recovery** (Story 3.1) | Worker 크래시 → 메시지 잔류 → `posts:processing_time:{id}` TTL 만료 | `posts:retry:{post_id}` Redis INCR (스캔 단위) | `Watchdog.scan_once` (별도 데몬 스레드) | `Watchdog` |
| **RetryHandler exhausted** (이 스토리) | classify 호출이 retryable 예외 4회 발생 | 인메모리 변수 `attempt` (loop 단위) | `RetryHandler.execute_with_retry` (메인 스레드) | `RetryHandler` |

**왜 둘 다 필요한가:**
- Watchdog만 있으면: classify 4회 실패 후에도 메시지 잔류 → Watchdog 300s 대기 → re-enqueue → 또 4회 실패 → 무한 루프(Watchdog retry < 3 한도까지). 빠른 격리 불가.
- RetryHandler만 있으면: Worker 크래시 시(SIGKILL/OOM) classify 실행 자체가 시작도 안 한 메시지를 복구 못 함.
- 두 경로는 **다른 실패 모드**를 다룸. 카운터도 분리. 본 스토리 RetryHandler가 DLQ 이동 시 `posts:retry:{post_id}` 키도 DELETE해 잔여 상태 누락 방지.

**예외 case:** 어떤 메시지가 RetryHandler로 한 번 DLQ 이동된 후, 동일 `post_id`로 다시 들어와 또 RetryHandler에서 실패하면? → 별개 메시지로 처리됨(in-memory counter 새로 시작). DedupChecker(Story 2.3 SHA-256 SET) + Story 3.4 `(post_id, model_version)` unique constraint 이중 안전망이 RDS 중복 삽입 방지.

### 재시도 대상 예외 분류

| 예외 | 분류 | RetryHandler 동작 | 이유 |
|---|---|---|---|
| `TimeoutError` | retryable | 재시도 | 일시적 — 재호출 시 회복 가능 |
| `ConnectionError` | retryable | 재시도 | 네트워크 일시 장애 |
| `httpx.HTTPError` (5xx 등) | retryable | 재시도 | 서버 일시 장애 |
| `RateLimitError` | non-retryable (호출자 처리) | 즉시 propagate | 토큰 버킷이 사전 차단해야 정상. quota 동기화 어긋난 신호 — 재시도해도 같은 결과. Translator의 `time.sleep(retry_after)` 패턴은 quota 거부 후 1회만 |
| `ValueError` (스키마 위반) | non-retryable (영구 오류) | 즉시 propagate | VARCO 응답이 잘못된 type/confidence — 재시도해도 같은 결과 |
| `AssertionError` / `TypeError` 등 | non-retryable (코드 버그) | 즉시 propagate | 우리 코드 버그 — 재시도가 무의미 |

**디자인 결정:** `_RETRYABLE_EXCEPTIONS`는 화이트리스트(블랙리스트가 아닌). 미지의 예외는 영구 오류로 가정 → 즉시 propagate가 안전한 default.

### 현재 `detection/` 구조 (Story 3.3 착수 시점)

```
detection/
├── pytest.ini
├── requirements.txt
├── .env.example                        # ← Story 3.3가 환경변수 추가
└── src/
    ├── __init__.py
    ├── main.py                         # ← Story 3.3가 wiring 확장
    ├── config/
    │   ├── __init__.py
    │   └── redis_config.py             # 변경 없음
    ├── consumer/
    │   ├── __init__.py
    │   ├── queue_consumer.py           # 변경 없음(retry_handler가 LREM 처리)
    │   └── watchdog.py                 # 변경 없음(retry_key/processing_time_key 함수 재사용)
    ├── mocks/
    │   ├── __init__.py
    │   └── varco_mock.py               # 변경 없음(classify 이미 구현됨)
    ├── pipeline/
    │   ├── __init__.py
    │   ├── translate.py                # 변경 없음
    │   ├── varco_client.py             # ← Story 3.3가 classify() 구현
    │   └── detection_pipeline.py       # ← Story 3.3가 classify 단계 추가
    └── rate_limit/
        ├── __init__.py
        └── token_bucket.py             # 변경 없음(key 인자로 classify 버킷 분리)
└── tests/
    └── unit/
        ├── test_consumer_idempotency.py  # 8건 PASS
        ├── test_token_bucket.py          # 5건 PASS
        └── test_translate.py             # 5건 PASS
```

**이 스토리에서 추가될 구조:**

```
detection/src/
├── pipeline/
│   └── llm_classifier.py               ← LLMClassifier (신규)
└── retry/                              ← 신규 디렉토리
    ├── __init__.py
    └── retry_handler.py                ← RetryHandler + RetryExhaustedError
detection/tests/
├── unit/
│   ├── test_retry_handler.py           ← 5건
│   └── test_llm_classifier.py          ← 5건
└── integration/                        ← 신규 디렉토리
    ├── __init__.py
    └── test_varco_pipeline.py          ← 4건 (clean / illegal / timeout-DLQ / fixture)
shared/config/redis_config.py           ← REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY 추가
shared/interfaces/varco.py              ← docstring 예외 계약(코드 비변경)
```

### 공유 모듈 임포트 패턴 (재구현 절대 금지)

```python
# Redis DB / 키 상수
from shared.config.redis_config import (
    REDIS_KEY_POSTS_DLQ,                      # = "posts:dlq" (이미 존재)
    REDIS_KEY_POSTS_PROCESSING,               # = "posts:processing" (이미 존재)
    REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE,     # Story 3.2 추가
    REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY,      # 본 스토리 신규
)

# VARCO Protocol — production / test 모두 이 인터페이스 의존
from shared.interfaces.varco import VarcoInterface, ClassificationResult

# Mock — RateLimitError 예외 타입은 mocks 모듈에서 직접 임포트
from detection.src.mocks.varco_mock import VarcoMock, RateLimitError

# Watchdog 헬퍼 함수 재사용 — retry_key, processing_time_key
from detection.src.consumer.watchdog import processing_time_key, retry_key

# Story 3.2 모듈 재사용
from detection.src.pipeline.translate import Translator
from detection.src.pipeline.varco_client import VarcoHttpClient
from detection.src.rate_limit.token_bucket import TokenBucket

# 구조화 로그
from shared.structured_logger import get_logger
```

### Redis DB0 키 영향(본 스토리)

```
posts:queue                # 변경 없음 (BRPOPLPUSH 소스)
posts:processing           # RetryHandler가 LREM 호출 (DLQ 이동 시)
posts:dlq                  # RetryHandler가 LPUSH 호출 (재시도 한도 초과 시)
posts:retry:{post_id}      # RetryHandler가 DELETE 호출 (Watchdog 카운터 cleanup)
posts:processing_time:{id} # RetryHandler가 DELETE 호출 (Watchdog stale 키 cleanup)
posts:corrupt              # 변경 없음 (Watchdog corrupt-DLQ 격리)
```

### Redis DB2 토큰 버킷 키 (본 스토리 추가)

```
HSET varco:rate_limit:classify
    tokens       <float>     # classify 호출 잔여 토큰
    last_refill  <float>     # 마지막 충전 epoch
EXPIRE varco:rate_limit:classify 3600
```

`TokenBucket(key=REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY)`로 인스턴스 분리. capacity/refill은 환경변수 기본값(`VARCO_RATE_LIMIT_CAPACITY=60`, `_REFILL_PER_SEC=1`) 공유 — Story 3.2와 동일 설정. 분리 튜닝은 Story 3.5 측정 후.

### VARCO API 호출 패턴 (classify)

```python
# production
varco = VarcoHttpClient()
result = varco.classify("매크로 판매합니다")
# → ClassificationResult(is_illegal=True, type="매크로_판매", confidence=0.95, reason="...")

# test/dev
varco = VarcoMock(mode="illegal")
result = varco.classify("...")
# → fixture mock_response_illegal.json의 classification 객체 반환

# timeout 시뮬레이션
varco = VarcoMock(mode="timeout")
varco.classify("...")  # → raises TimeoutError("VARCO API timeout")
```

**VARCO 실제 명세 미확보 시 placeholder:**
- `POST /classify` body: `{"text": "..."}`
- response 200: `{"is_illegal": bool, "type": str, "confidence": float, "reason": str}`
- response 429: `Retry-After` 헤더 → `RateLimitError(retry_after=int(헤더))`
- 실제 VARCO API 명세 확보 시 `varco_client.py`의 `classify()` 메서드만 수정.

### `type` enum 정확한 값 (한글 + 언더스코어)

```python
_ALLOWED_TYPES = frozenset({"매크로_판매", "핵_배포", "계정_거래", "리세마라", "기타"})
```

**근거:** prd.md L280, epics.md L474. **공백 아닌 언더스코어** — Python identifier 안전성 + DB 컬럼/JSON 일관성. fixture(`mock_response_illegal.json`)도 `"매크로_판매"` 사용 확인. 영어 표기는 사용 안 함(MVP 한글 고정).

### 환경변수 목록 (Story 3.1 + 3.2 + 3.3 누적)

| 변수 | 기본값 | 설명 | 도입 |
|------|--------|------|------|
| `REDIS_URL` | `redis://localhost:6379` | Redis 연결 URL | 3.1 |
| `SERVICE_NAME` | `detection` | 구조화 로그 service 필드 | 3.1 |
| `BRPOPLPUSH_TIMEOUT` | `30` | brpoplpush blocking timeout (초) | 3.1 |
| `WATCHDOG_STALE_SECONDS` | `300` | stale 판정 기준 (초) | 3.1 |
| `WATCHDOG_POLL_INTERVAL` | `60` | Watchdog 폴링 주기 (초) | 3.1 |
| `VARCO_API_BASE_URL` | `https://varco.placeholder/v1` | VARCO API base URL | 3.2 |
| `VARCO_API_KEY` | `""` | VARCO API key (Bearer) | 3.2 |
| `VARCO_TRANSLATE_TIMEOUT_SEC` | `10` | translate httpx timeout | 3.2 |
| `VARCO_RATE_LIMIT_CAPACITY` | `60` | 토큰 버킷 capacity | 3.2 |
| `VARCO_RATE_LIMIT_REFILL_PER_SEC` | `1` | 초당 충전 토큰 수 | 3.2 |
| `VARCO_RATE_LIMIT_MAX_WAIT_SEC` | `120` | acquire 최대 대기(초) | 3.2 |
| `VARCO_CLASSIFY_TIMEOUT_SEC` | `10` | classify httpx timeout (per-request override) | **3.3** |
| `VARCO_LLM_MODEL_VERSION` | `varco-llm-v1` | `detections.model_version` 값 (Story 3.4 사용) | **3.3** |
| `VARCO_RATE_LIMIT_CLASSIFY_CAPACITY` | `60` | classify 토큰 버킷 capacity (선언만, 코드 미사용 — Story 3.5에서 분리) | **3.3** |
| `VARCO_RATE_LIMIT_CLASSIFY_REFILL_PER_SEC` | `1` | classify 충전율 (선언만, 코드 미사용) | **3.3** |
| `RETRY_MAX_ATTEMPTS` | `3` | RetryHandler 재시도 횟수 (원본 + 3 = 총 4회) | **3.3** |
| `RETRY_BACKOFF_BASE_SEC` | `1` | exponential backoff base — 1s/2s/4s | **3.3** |

### Anti-Patterns to Avoid

1. ❌ **`_MAX_ATTEMPTS=4`로 설정** — epics.md "3회 재시도"는 재시도 횟수만. 원본 1 + 재시도 3 = 총 4회 호출. `_MAX_ATTEMPTS`는 정확히 3.
2. ❌ **`time.sleep(2 ** attempt)` — base 누락** — `RETRY_BACKOFF_BASE_SEC` 환경변수로 외부화. `base * (2 ** attempt)`.
3. ❌ **모든 예외를 `Exception`으로 catch한 후 재시도** — `RateLimitError`/`ValueError`/`KeyboardInterrupt`까지 재시도하는 재앙. 화이트리스트(`_RETRYABLE_EXCEPTIONS`) 사용.
4. ❌ **`RetryHandler`가 `posts:processing` LREM 안 함** — 메시지 잔류 → Watchdog이 또 stale 감지 → 카운터 증가 → 동일 메시지 두 경로(retry-DLQ + Watchdog-DLQ)로 두 번 격리. RetryHandler가 LREM + retry_key DELETE까지 책임.
5. ❌ **`RetryExhaustedError`를 `DetectionPipeline.process`에서 catch** — QueueConsumer의 except 핸들러에서 ERROR 로그 남기는 흐름이 끊김. 그대로 propagate.
6. ❌ **`RetryHandler.execute_with_retry`가 `func()` 호출 후 결과 미반환** — generic 함수이므로 반환값 보존 필수.
7. ❌ **`varco:rate_limit:classify` 키를 단일 `varco:rate_limit`로 통합** — translate 호출이 classify quota를 잠식. 별도 키 필수.
8. ❌ **`VARCO_LLM_MODEL_VERSION`을 코드 하드코딩** — 환경변수에서만 로드. Story 3.4에서 RDS 컬럼에 기록될 값 — 모델 교체 시 변경 가능.
9. ❌ **classify 호출 전 토큰 버킷 미차감** — translate와 동일 quota 정책. classify도 `bucket.acquire()` 필수.
10. ❌ **`type` 검증을 시도 후 raise — RetryHandler가 재시도** — `ValueError`는 non-retryable 화이트리스트에 미포함이므로 즉시 propagate(설계 의도). 그러나 `Exception` 광범위 catch 시 망가짐. 화이트리스트 엄수.
11. ❌ **`reason` 텍스트 로그 출력** — `reason`은 LLM 출력이므로 PII/민감정보 가능. `is_illegal/type/confidence`만 INFO 로그. `reason`은 ERROR 시에만(또는 Story 3.4 RDS 저장).
12. ❌ **`asyncio` 도입** — Story 3.1/3.2가 동기 패턴. 비동기 도입 시 RetryHandler `time.sleep` 차단·QueueConsumer 통합 일관성 망가짐. 동기 유지.
13. ❌ **DLQ LPUSH 후 LREM 실패 시 처리** — 비원자성 deferred(Story 3.5). 본 스토리는 sequential 호출만. Lua script atomic은 측정 후.

### Architecture Compliance Notes

- **FR12 (자동 분류)** — `LLMClassifier.classify` → `is_illegal` + `type` (5종 enum). AC #1.
- **FR13 (신뢰도 점수)** — `confidence` 0~1 검증. AC #1.
- **FR14 (판단 근거)** — `reason` 필드. AC #1 ClassificationResult.
- **FR15 (자동 재시도 + 격리)** — RetryHandler exponential backoff 3회 → DLQ. AC #2, #3.
- **FR16 (외부 API 호출량 제어)** — classify 토큰 버킷 분리. AC #1.
- **NFR3 (배치 ≤30분)** — backoff 1+2+4=7s × 200건 worst case ≈ 23분. 정상 path는 backoff 0. Story 3.5 측정.
- **NFR11 (3회 재시도 + DLQ)** — RetryHandler 정확 구현. AC #2, #3.
- **NFR12 (DLQ 알람)** — Story 5.1 Grafana 알람으로 후속. 본 스토리는 ERROR 로그만.
- **NFR14 (rate limit 자동 대기)** — TokenBucket(Story 3.2 재사용). AC #1.
- **architecture.md P2 (Redis 키 명명)** — `varco:rate_limit:classify` 소문자 콜론 계층. AC #1.
- **architecture.md P6 (구조화 로그)** — 모든 로그 `extra={"correlation_id", "service"}` + DLQ 로그 `post_id` + `last_error_type`. AC #8.
- **deferred-work.md L32 (VarcoInterface 예외 계약)** — Task 2가 docstring으로 해소.
- **deferred-work.md L35 (confidence 범위 검증)** — Task 3이 `LLMClassifier.classify` 내부에서 해소.

### 주요 의존 관계

```
Story 2.5 → posts:queue (DB0)에 CrawlEvent LPUSH
Story 3.1 → BRPOPLPUSH 소비 + Watchdog stale 복구 (done)
Story 3.2 → translate (zh-CN/zh-TW만, 토큰 버킷 :translate) (review)
Story 3.3 → classify (이 스토리) + retry_handler 3회 재시도 + DLQ
Story 3.4 → detection_repository → RDS detections (post_id, model_version) UNIQUE
Story 3.5 → Precision/Recall + 배치 시간 측정
```

### Story 3.1 / 3.2 Deferred 항목 중 본 스토리 영향

- **`processing_time` TTL = stale 임계치 동일(300s)** (Story 3.1 deferred D-04) — translate(Story 3.2 max 120s) + classify(본 스토리 추가) + RetryHandler backoff(최대 7s) + classify 호출(timeout 10s) ≤ 약 140s. 5분 임계 내. 단, classify 4회 모두 timeout 시 `4 * 10s + 7s = 47s` 추가 — 여전히 임계 내. 즉시 영향 없음.
- **VarcoInterface 예외 계약** (Story 3.1/1.2 deferred L32) — Task 2가 docstring으로 해소. 기존 코드 비변경 → 회귀 0건.
- **ClassificationResult.confidence 범위** (Story 1.2 deferred L35) — Task 3 `LLMClassifier.classify` 내부 검증으로 해소.
- **`_MAX_RETRIES` env 외부화** (Story 3.1 deferred) — `RETRY_MAX_ATTEMPTS` 환경변수로 RetryHandler에 한정 도입. Watchdog `_MAX_RETRIES=3` 하드코딩은 별도 후속.

### 본 스토리 Deferred 항목 (Story 3.5 또는 운영 시점 재검토)

- VARCO 실제 API 엔드포인트/auth/스키마 미확보 → `VarcoHttpClient.classify`만 수정. 본 스토리는 mock 계약 기반 placeholder.
- DLQ LPUSH + LREM + DELETE 비원자성(race window) → Lua script 통합. Story 3.5 측정 후.
- classify 토큰 버킷 capacity/refill을 translate와 분리 튜닝 → 환경변수 선언만, 코드 미사용. Story 3.5 측정 후 `TokenBucket(capacity=..., refill_per_sec=...)` 명시 전달.
- Backoff jitter(thundering herd 방지) → 단일 instance MVP는 불필요. 다중 instance 시 random.uniform(0, base) 추가.
- `RateLimitError` propagate 시 메시지 잔류 처리 → Watchdog이 stale 감지 후 재투입. 즉시 DLQ 이동 정책 검토는 운영 측정 후.
- `reason` 로그 정책(PII 우려) → INFO 로그에서 제외. 전수 로깅 필요 시 별도 audit log 검토.

### Project Context Reference

- [shared/config/redis_config.py](shared/config/redis_config.py) — `REDIS_KEY_POSTS_DLQ`, `REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY`(본 스토리 추가)
- [shared/interfaces/varco.py](shared/interfaces/varco.py) — `VarcoInterface` Protocol, `ClassificationResult` dataclass
- [shared/models/crawl_event.py](shared/models/crawl_event.py) — `CrawlEvent.from_json` + `post_id` / `correlation_id` 필드
- [shared/structured_logger.py](shared/structured_logger.py) — `get_logger(name)` JSON formatter
- [detection/src/mocks/varco_mock.py](detection/src/mocks/varco_mock.py) — `VarcoMock` 4모드(`clean/illegal/timeout/rate_limited`), `RateLimitError`
- [detection/src/pipeline/varco_client.py](detection/src/pipeline/varco_client.py) — `VarcoHttpClient` (본 스토리: `classify()` 구현)
- [detection/src/pipeline/translate.py](detection/src/pipeline/translate.py) — `Translator` (Story 3.2, 비변경)
- [detection/src/pipeline/detection_pipeline.py](detection/src/pipeline/detection_pipeline.py) — `DetectionPipeline.process` (본 스토리: classify 단계 추가)
- [detection/src/rate_limit/token_bucket.py](detection/src/rate_limit/token_bucket.py) — `TokenBucket(key=...)` (Story 3.2, 비변경, 키 인자만 분리)
- [detection/src/consumer/queue_consumer.py](detection/src/consumer/queue_consumer.py) — `QueueConsumer.run_once` (Story 3.1, 비변경)
- [detection/src/consumer/watchdog.py](detection/src/consumer/watchdog.py) — `processing_time_key` / `retry_key` 함수 재사용
- [detection/src/main.py](detection/src/main.py) — wiring (본 스토리: classify + retry 추가)
- [tests/fixtures/varco/mock_response_clean.json](tests/fixtures/varco/mock_response_clean.json) — `classification.is_illegal=False, type="기타", confidence=0.92`
- [tests/fixtures/varco/mock_response_illegal.json](tests/fixtures/varco/mock_response_illegal.json) — `classification.is_illegal=True, type="매크로_판매", confidence=0.95`
- [tests/fixtures/varco/mock_response_timeout.json](tests/fixtures/varco/mock_response_timeout.json) — `error="timeout", latency_ms=30000` → mock이 `TimeoutError` raise
- [_bmad-output/implementation-artifacts/3-1-redis-큐-소비자-및-watchdog-구현.md](_bmad-output/implementation-artifacts/3-1-redis-큐-소비자-및-watchdog-구현.md) — Watchdog DLQ 패턴 + retry_key 함수
- [_bmad-output/implementation-artifacts/3-2-varco-translation-연동-및-rate-limit-제어.md](_bmad-output/implementation-artifacts/3-2-varco-translation-연동-및-rate-limit-제어.md) — Translator + TokenBucket + DetectionPipeline 패턴
- [_bmad-output/implementation-artifacts/deferred-work.md](_bmad-output/implementation-artifacts/deferred-work.md) — L32(VarcoInterface 예외 계약) + L35(confidence 검증) 본 스토리에서 해소
- [_bmad-output/planning-artifacts/architecture.md](_bmad-output/planning-artifacts/architecture.md) — Redis DB 분리(L64, L274-285), detection 디렉토리(L487-518), retry/storage 위치(L503-506)
- [_bmad-output/planning-artifacts/epics.md](_bmad-output/planning-artifacts/epics.md) — Story 3.3 AC(L464-478), Story 3.4 후속 의존성(L480-494)
- [_bmad-output/planning-artifacts/prd.md](_bmad-output/planning-artifacts/prd.md) — FR12, FR13, FR14, FR15, FR16, NFR11, NFR12, NFR14, type enum(L280)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

- `cd detection && ./.venv/bin/pytest tests/ -v` → 32건 PASS (외부 네트워크/실제 Redis 호출 0건)
- `cd crawler && ./.venv/bin/pytest tests/` → 81건 PASS (회귀 0건)

### Completion Notes List

- AC #1 (LLMClassifier + type/confidence 검증) — `LLMClassifier.classify`가 `_ALLOWED_TYPES` frozenset(매크로_판매/핵_배포/계정_거래/리세마라/기타)으로 type 검증, `0.0 <= confidence <= 1.0` 범위 검증. classify 직전 `bucket.acquire()` 호출. deferred-work L35 해소.
- AC #2 (재시도 + backoff) — `RetryHandler.execute_with_retry`가 retryable 화이트리스트(`TimeoutError`/`ConnectionError`/`httpx.HTTPError`)만 재시도. 원본 1 + 재시도 3 = 총 4회 호출. backoff `base * 2^attempt` (1s/2s/4s).
- AC #3 (DLQ 이동) — 한도 초과 시 `LPUSH posts:dlq` → `LREM posts:processing` → `DELETE posts:retry:{id}` + `DELETE posts:processing_time:{id}` → ERROR 로그 → `RetryExhaustedError` raise 순서로 정확히 한 번씩.
- AC #4 (DetectionPipeline 통합) — `process()`에 `_retry_handler.execute_with_retry(lambda: classifier.classify(translated), ...)` 추가. `main.py`에서 `LLMClassifier` + `RetryHandler` + classify용 `TokenBucket(key=REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY)` wiring.
- AC #5 (RetryHandler 단위 테스트 5건) — first/second-attempt success, retry-exhausted-DLQ, ValueError/RateLimitError propagate. 모두 `MagicMock` + `time.sleep` monkeypatch.
- AC #6 (LLMClassifier 단위 테스트 5건) — VarcoMock clean/illegal fixture, invalid type, confidence > 1.0/< 0.0 검증.
- AC #7 (통합 테스트 4건) — clean Korean / illegal Chinese / timeout-DLQ / fixture 로드 검증. `QueueConsumer.run_once()` 통한 end-to-end. `MagicMock(redis.Redis)` — 실제 Redis 0건.
- AC #8 (구조화 로그) — 모든 INFO/WARNING/ERROR에 `extra={"correlation_id", "service"}`. DLQ 로그에 `post_id` + `last_error_type` 추가.
- AC #9 (32건 PASS) — Story 3.1+3.2 기존 18건 + 신규 14건(retry 5 + classifier 5 + integration 4) = **32건 모두 PASS** (0.42s).
- VarcoInterface docstring (deferred-work L32 해소) — `translate`/`classify` 메서드에 `Raises` 절 추가. 코드 시그니처 비변경.
- 회귀 0건 — crawler 81건 PASS 확인.

### File List

**신규**
- `detection/src/pipeline/llm_classifier.py` — `LLMClassifier` (VARCO classify + type/confidence 검증)
- `detection/src/retry/__init__.py` — 빈 패키지 마커
- `detection/src/retry/retry_handler.py` — `RetryHandler` + `RetryExhaustedError` (exponential backoff + DLQ 이동)
- `detection/tests/unit/test_retry_handler.py` — RetryHandler 단위 테스트 5건
- `detection/tests/unit/test_llm_classifier.py` — LLMClassifier 단위 테스트 5건
- `detection/tests/integration/__init__.py` — 빈 패키지 마커
- `detection/tests/integration/test_varco_pipeline.py` — 통합 테스트 4건

**수정**
- `shared/config/redis_config.py` — `REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY` 상수 추가
- `shared/interfaces/varco.py` — `translate`/`classify` 예외 계약 docstring 추가 (deferred-work L32 해소)
- `detection/.env.example` — Story 3.3 환경변수 6종 추가 (`VARCO_CLASSIFY_TIMEOUT_SEC`/`VARCO_LLM_MODEL_VERSION`/`VARCO_RATE_LIMIT_CLASSIFY_CAPACITY`/`VARCO_RATE_LIMIT_CLASSIFY_REFILL_PER_SEC`/`RETRY_MAX_ATTEMPTS`/`RETRY_BACKOFF_BASE_SEC`)
- `detection/src/pipeline/varco_client.py` — `classify()` 실제 구현으로 교체 (`POST /classify`, 429 → `RateLimitError`)
- `detection/src/pipeline/detection_pipeline.py` — `LLMClassifier` + `RetryHandler` DI + classify 단계 통합 (Story 3.2 TODO 해소)
- `detection/src/main.py` — classify용 별도 `TokenBucket` + `LLMClassifier` + `RetryHandler` wiring 추가

## Change Log

| 날짜 | 변경 | 사유 |
|---|---|---|
| 2026-04-29 | Story 3.3 컨텍스트 작성 (`Status: ready-for-dev`) | bmad-create-story |
| 2026-04-29 | Story 3.3 dev 완료 (`Status: in-progress → review`) — 신규 14건 + 회귀 18건 = 32건 PASS, classify + retry-DLQ 인라인 격리 구축 | bmad-dev-story |
