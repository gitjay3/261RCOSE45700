# Story 3.1: Redis 큐 소비자 및 Watchdog 구현

Status: done

> **본 스토리 핵심:** `posts:queue`(DB0)에서 `CrawlEvent`를 `BRPOPLPUSH`로 원자적으로 소비하고, `Watchdog`이 처리 중 크래시된 stale 메시지를 복구하며, 3회 재시도 초과 시 `posts:dlq`로 격리한다. Epic 3 탐지 파이프라인(Story 3.2~3.4)의 진입점. 실제 VARCO 호출은 이 스토리에서 하지 않는다 — `_process_message` 콜백은 stub으로 남긴다.
>
> **[전제 조건]** Story 2.5 `review` 이상. `posts:queue`(DB0)에 `CrawlEvent` JSON이 `LPUSH`되는 구조 완성. `shared/config/redis_config.py`, `shared/models/crawl_event.py`, `shared/structured_logger.py`, `detection/src/mocks/varco_mock.py` 모두 완성. `infra/docker-compose.yml` Redis AOF(`--appendonly yes`) 설정 완료.

## Story

개발자로서,
Redis 큐에서 게시글을 원자적으로 소비하고 처리 중 Worker 크래시 시 메시지가 유실되지 않기를 원한다,
그래서 파이프라인이 장애 상황에서도 데이터 정합성을 보장한다.

## Acceptance Criteria

1. **Given** Redis DB0 `posts:queue`에 게시글이 적재된 상태에서 **When** `queue_consumer.py`가 실행되면 **Then** `BRPOPLPUSH posts:queue posts:processing`으로 메시지를 원자적으로 소비한다 (NFR16)  
   **And** 처리 완료 후 `LREM posts:processing 1 {message}`로 메시지를 제거한다

2. **Given** `QueueConsumer`가 메시지를 소비할 때 **When** `_process_message` 콜백이 예외를 발생시키면 **Then** 해당 메시지는 `posts:processing`에서 제거되지 않고 잔류한다 (Watchdog이 복구)

3. **Given** `watchdog.py`가 실행 중일 때 **When** `posts:processing`에 `WATCHDOG_STALE_SECONDS`(기본값 300초) 이상 잔류하는 메시지가 감지되면 **Then** `Watchdog`이 해당 메시지를 `posts:queue`로 재투입하고 `posts:retry:{post_id}` 카운터를 1 증가시킨다

4. **Given** `posts:retry:{post_id}` 카운터가 이미 3 이상인 메시지가 `posts:processing`에 잔류할 때 **When** `Watchdog`이 이를 감지하면 **Then** `posts:queue` 재투입 대신 `posts:dlq`에 `LPUSH`하고 `posts:processing`에서 제거하며, 구조화 로그에 `"DLQ 이동"` 메시지와 `post_id`, `correlation_id`가 기록된다

5. **Given** Worker 프로세스가 재시작될 때 **When** `main.py`가 다시 실행되면 **Then** Redis AOF에 의해 `posts:processing`의 미완료 메시지가 보존되고, `Watchdog`이 `WATCHDOG_STALE_SECONDS` 후 이를 감지하여 `posts:queue`로 재투입한다 (NFR13)

6. **Given** `detection/tests/unit/test_consumer_idempotency.py`가 실행될 때 **When** 테스트를 실행하면 **Then** 다음 6개 시나리오가 모두 PASS한다:
   - 정상 처리 → `LREM` 호출 + retry 키 삭제 검증
   - 처리 실패 → `LREM` 미호출 검증 (메시지 잔류)
   - Watchdog 스테일 감지 + retry < 3 → `posts:queue` RPUSH + retry INCR
   - Watchdog retry == 3 → `posts:dlq` LPUSH + `posts:processing` LREM
   - Watchdog 신선 메시지 (TTL 키 존재) → 무작위 동작 없음
   - retry storm 전체 라이프사이클 (3회 실패 → DLQ) 검증

7. **Given** 테스트 실행 시 **When** `cd detection && ./.venv/bin/pytest tests/unit/ -v`를 실행하면 **Then** 신규 6건이 **모두 PASS**하며 실제 Redis 호출이 0건이다

> **AC 출처:** epics.md (Story 3.1). AC 3~4 (retry 카운터 설계), AC 5 (AOF 복구 메커니즘), AC 6 (테스트 항목)은 architecture.md NFR13/NFR16 및 기존 패턴(Story 2.3/2.5 통합 테스트)을 기반으로 구체화.

## Tasks / Subtasks

- [x] **Task 1: requirements.txt 업데이트 및 pytest 설정** (AC: #6, #7)
  - [x] 1.1 `detection/requirements.txt` 업데이트:
    ```
    redis>=5.0.0
    boto3
    httpx
    python-dotenv
    pytest>=7.0.0
    pytest-mock>=3.0.0
    -e ../shared
    ```
    기존 `redis`(버전 미핀)를 `redis>=5.0.0`으로 교체. `pytest`와 `pytest-mock` 추가.
  - [x] 1.2 `detection/pytest.ini` 신규 (detection 테스트는 동기 — asyncio_mode 불필요):
    ```ini
    [pytest]
    testpaths = tests
    ```

- [x] **Task 2: Redis 연결 설정** (AC: #1~#5)
  - [x] 2.1 `detection/src/config/__init__.py` 신규 (빈 파일)
  - [x] 2.2 `detection/src/config/redis_config.py` 신규:
    ```python
    import os
    import redis
    from shared.config.redis_config import REDIS_MQ_DB

    def get_mq_client() -> redis.Redis:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        return redis.from_url(url, db=REDIS_MQ_DB, decode_responses=True)
    ```
    - `decode_responses=True` 필수 — 문자열 자동 디코딩, `LREM` 인자 일치 보장
    - `REDIS_MQ_DB` 는 `shared/config/redis_config.py`에서 임포트 (DB0). 상수 하드코딩 금지.

- [x] **Task 3: QueueConsumer 구현** (AC: #1, #2)
  - [x] 3.1 `detection/src/consumer/__init__.py` 신규 (빈 파일)
  - [x] 3.2 `detection/src/consumer/queue_consumer.py` 신규:
    ```python
    from __future__ import annotations

    import os
    from collections.abc import Callable

    import redis

    from shared.config.redis_config import (
        REDIS_KEY_POSTS_PROCESSING,
        REDIS_KEY_POSTS_QUEUE,
    )
    from shared.structured_logger import get_logger

    _SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
    _BRPOPLPUSH_TIMEOUT = int(os.environ.get("BRPOPLPUSH_TIMEOUT", "30"))
    _logger = get_logger(__name__)


    class QueueConsumer:
        def __init__(
            self,
            redis_client: redis.Redis,
            process_fn: Callable[[str], None],
        ) -> None:
            self._redis = redis_client
            self._process = process_fn

        def run_once(self) -> bool:
            """단일 메시지 소비 시도. 메시지 있으면 True, timeout이면 False 반환."""
            message: str | None = self._redis.brpoplpush(
                REDIS_KEY_POSTS_QUEUE,
                REDIS_KEY_POSTS_PROCESSING,
                timeout=_BRPOPLPUSH_TIMEOUT,
            )
            if message is None:
                return False

            try:
                self._process(message)
                self._redis.lrem(REDIS_KEY_POSTS_PROCESSING, 1, message)
                _logger.info(
                    "메시지 처리 완료",
                    extra={"correlation_id": "", "service": _SERVICE_NAME},
                )
            except Exception as exc:
                _logger.error(
                    "메시지 처리 실패 — posts:processing 잔류: %s", exc,
                    extra={"correlation_id": "", "service": _SERVICE_NAME},
                )
                # LREM 호출하지 않음 — Watchdog이 stale 감지 후 재투입

            return True

        def run_forever(self) -> None:
            _logger.info(
                "QueueConsumer 시작",
                extra={"correlation_id": "", "service": _SERVICE_NAME},
            )
            while True:
                self.run_once()
    ```
  - [x] 3.3 `REDIS_KEY_POSTS_QUEUE`, `REDIS_KEY_POSTS_PROCESSING` 는 `shared/config/redis_config.py`에서 임포트. 문자열 하드코딩 금지.
  - [x] 3.4 `brpoplpush(src, dst, timeout=N)` — timeout=0은 블로킹 무한 대기. 기본값 30초 권장 (프로세스 종료 신호 처리 위해).

- [x] **Task 4: Watchdog 구현** (AC: #3, #4, #5)
  - [x] 4.1 `detection/src/consumer/watchdog.py` 신규:
    ```python
    from __future__ import annotations

    import os
    import time

    import redis

    from shared.config.redis_config import (
        REDIS_KEY_POSTS_DLQ,
        REDIS_KEY_POSTS_PROCESSING,
        REDIS_KEY_POSTS_QUEUE,
    )
    from shared.models.crawl_event import CrawlEvent
    from shared.structured_logger import get_logger

    _SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
    _STALE_SECONDS = int(os.environ.get("WATCHDOG_STALE_SECONDS", "300"))
    _POLL_INTERVAL = int(os.environ.get("WATCHDOG_POLL_INTERVAL", "60"))
    _MAX_RETRIES = 3
    _logger = get_logger(__name__)


    def _retry_key(post_id: str) -> str:
        return f"posts:retry:{post_id}"

    def _processing_time_key(post_id: str) -> str:
        return f"posts:processing_time:{post_id}"


    class Watchdog:
        def __init__(self, redis_client: redis.Redis) -> None:
            self._redis = redis_client

        def mark_processing(self, message: str) -> None:
            """Consumer가 BRPOPLPUSH 직후 호출 — 처리 시작 시각 기록."""
            try:
                event = CrawlEvent.from_json(message)
                self._redis.setex(
                    _processing_time_key(event.post_id),
                    _STALE_SECONDS,
                    "1",
                )
            except Exception:
                pass  # 타임스탬프 기록 실패는 stale 판정으로 처리

        def scan_once(self) -> int:
            """posts:processing 전체 스캔. 처리한 stale 메시지 수 반환."""
            messages = self._redis.lrange(REDIS_KEY_POSTS_PROCESSING, 0, -1)
            handled = 0
            for message in messages:
                try:
                    event = CrawlEvent.from_json(message)
                    post_id = event.post_id
                except Exception:
                    continue

                is_stale = not self._redis.exists(_processing_time_key(post_id))
                if not is_stale:
                    continue

                retry_count = int(self._redis.get(_retry_key(post_id)) or 0)
                if retry_count >= _MAX_RETRIES:
                    self._redis.lpush(REDIS_KEY_POSTS_DLQ, message)
                    self._redis.lrem(REDIS_KEY_POSTS_PROCESSING, 1, message)
                    self._redis.delete(_retry_key(post_id))
                    _logger.error(
                        "DLQ 이동 — 최대 재시도 초과",
                        extra={
                            "correlation_id": event.correlation_id,
                            "service": _SERVICE_NAME,
                        },
                    )
                else:
                    self._redis.rpush(REDIS_KEY_POSTS_QUEUE, message)
                    self._redis.lrem(REDIS_KEY_POSTS_PROCESSING, 1, message)
                    self._redis.incr(_retry_key(post_id))
                    _logger.warning(
                        "Watchdog 재투입 — retry=%d post_id=%s",
                        retry_count + 1, post_id,
                        extra={
                            "correlation_id": event.correlation_id,
                            "service": _SERVICE_NAME,
                        },
                    )
                handled += 1
            return handled

        def run_forever(self) -> None:
            _logger.info(
                "Watchdog 시작 — stale_threshold=%ds, poll_interval=%ds",
                _STALE_SECONDS, _POLL_INTERVAL,
                extra={"correlation_id": "", "service": _SERVICE_NAME},
            )
            while True:
                time.sleep(_POLL_INTERVAL)
                self.scan_once()
    ```
  - [x] 4.2 `_processing_time_key` 방식: `SETEX posts:processing_time:{post_id} {STALE_SECONDS} "1"`. 키 TTL 만료 = stale 판정. Redis 서버가 자동 만료 처리 — cron 불필요.
  - [x] 4.3 `rpush`(right-push)로 재투입: `posts:queue`의 right에 추가 → `BRPOPLPUSH`(right-pop)가 정상 소비. FIFO 보장.
  - [x] 4.4 `REDIS_KEY_POSTS_DLQ = "posts:dlq"` 는 `shared/config/redis_config.py`에 이미 정의됨. 임포트 사용.

- [x] **Task 5: QueueConsumer + Watchdog 통합 (mark_processing 연결)** (AC: #3, #5)
  - [x] 5.1 `queue_consumer.py`의 `run_once()`에서 BRPOPLPUSH 직후 `watchdog.mark_processing(message)` 호출:
    ```python
    # QueueConsumer.__init__ 수정
    def __init__(
        self,
        redis_client: redis.Redis,
        process_fn: Callable[[str], None],
        watchdog: Watchdog | None = None,
    ) -> None:
        self._redis = redis_client
        self._process = process_fn
        self._watchdog = watchdog

    # run_once() 수정 — BRPOPLPUSH 직후
    message = self._redis.brpoplpush(...)
    if message is None:
        return False
    if self._watchdog:
        self._watchdog.mark_processing(message)  # 타임스탬프 등록
    try:
        ...
    ```
  - [x] 5.2 `Watchdog` 의존성 주입 — `QueueConsumer(redis, process_fn, watchdog=watchdog)` 패턴. `watchdog=None`이면 mark_processing 스킵 (테스트 편의).

- [x] **Task 6: main.py 진입점** (AC: #5)
  - [x] 6.1 `detection/src/main.py` 신규:
    ```python
    from __future__ import annotations

    import threading

    from detection.src.config.redis_config import get_mq_client
    from detection.src.consumer.queue_consumer import QueueConsumer
    from detection.src.consumer.watchdog import Watchdog
    from shared.structured_logger import get_logger

    _logger = get_logger(__name__)


    def _stub_process(message: str) -> None:
        """Story 3.2에서 실제 파이프라인(translate → classify → save)으로 교체."""
        _logger.info(
            "메시지 수신 (stub — 파이프라인 미구현)",
            extra={"correlation_id": "", "service": "detection"},
        )


    def main() -> None:
        redis_client = get_mq_client()
        watchdog = Watchdog(redis_client)
        consumer = QueueConsumer(redis_client, _stub_process, watchdog=watchdog)

        watchdog_thread = threading.Thread(target=watchdog.run_forever, daemon=True)
        watchdog_thread.start()

        consumer.run_forever()


    if __name__ == "__main__":
        main()
    ```
  - [x] 6.2 `Watchdog`는 데몬 스레드로 실행 — `consumer.run_forever()` 종료 시 자동 정리.
  - [x] 6.3 `_stub_process`는 Story 3.2에서 `detection_worker.process(message)` 호출로 교체 예정. 지금은 로그만.

- [x] **Task 7: 단위 테스트 작성** (AC: #6, #7)
  - [x] 7.1 `detection/tests/unit/test_consumer_idempotency.py` 신규 (6건):
    ```python
    from __future__ import annotations

    from unittest.mock import MagicMock, call, patch

    import pytest

    from detection.src.consumer.queue_consumer import QueueConsumer
    from detection.src.consumer.watchdog import Watchdog
    from shared.models.crawl_event import CrawlEvent
    from shared.config.redis_config import (
        REDIS_KEY_POSTS_QUEUE,
        REDIS_KEY_POSTS_PROCESSING,
        REDIS_KEY_POSTS_DLQ,
    )

    _EVENT = CrawlEvent(
        post_id="inven_1234",
        source_id="inven_maple",
        site_name="인벤 (메이플스토리)",
        raw_text="매크로 판매합니다",
        language="ko",
        detected_at="2026-04-29T00:00:00Z",
        correlation_id="test-cid-001",
    )
    _MSG = _EVENT.to_json()


    # ──────────────────────────────── QueueConsumer ──────────────────────────────

    def test_consumer_acks_on_success():
        """정상 처리 → LREM 호출 (ack)"""
        mock_redis = MagicMock()
        mock_redis.brpoplpush.return_value = _MSG
        process_fn = MagicMock()

        consumer = QueueConsumer(mock_redis, process_fn)
        result = consumer.run_once()

        assert result is True
        process_fn.assert_called_once_with(_MSG)
        mock_redis.lrem.assert_called_once_with(REDIS_KEY_POSTS_PROCESSING, 1, _MSG)


    def test_consumer_does_not_ack_on_failure():
        """처리 실패 → LREM 미호출 (Watchdog이 복구)"""
        mock_redis = MagicMock()
        mock_redis.brpoplpush.return_value = _MSG

        def failing_process(msg):
            raise RuntimeError("처리 실패")

        consumer = QueueConsumer(mock_redis, failing_process)
        result = consumer.run_once()

        assert result is True
        mock_redis.lrem.assert_not_called()


    def test_consumer_returns_false_on_timeout():
        """brpoplpush timeout → False 반환"""
        mock_redis = MagicMock()
        mock_redis.brpoplpush.return_value = None

        consumer = QueueConsumer(mock_redis, MagicMock())
        result = consumer.run_once()

        assert result is False


    # ──────────────────────────────── Watchdog ───────────────────────────────────

    def test_watchdog_reenqueues_stale_and_increments_retry():
        """stale 메시지 + retry < 3 → posts:queue 재투입 + retry INCR"""
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = [_MSG]
        mock_redis.exists.return_value = 0   # 타임스탬프 키 만료 = stale
        mock_redis.get.return_value = "1"    # 현재 retry = 1 (< 3)

        watchdog = Watchdog(mock_redis)
        handled = watchdog.scan_once()

        assert handled == 1
        mock_redis.rpush.assert_called_once_with(REDIS_KEY_POSTS_QUEUE, _MSG)
        mock_redis.lrem.assert_called_once_with(REDIS_KEY_POSTS_PROCESSING, 1, _MSG)
        mock_redis.incr.assert_called_once()
        mock_redis.lpush.assert_not_called()  # DLQ 이동 없음


    def test_watchdog_moves_to_dlq_at_max_retries():
        """retry == 3 → posts:dlq LPUSH + LREM"""
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = [_MSG]
        mock_redis.exists.return_value = 0   # stale
        mock_redis.get.return_value = "3"    # retry == 3 → DLQ

        watchdog = Watchdog(mock_redis)
        handled = watchdog.scan_once()

        assert handled == 1
        mock_redis.lpush.assert_called_once_with(REDIS_KEY_POSTS_DLQ, _MSG)
        mock_redis.lrem.assert_called_once_with(REDIS_KEY_POSTS_PROCESSING, 1, _MSG)
        mock_redis.rpush.assert_not_called()  # 재투입 없음


    def test_watchdog_skips_fresh_message():
        """타임스탬프 키 존재 (신선) → 아무 동작 없음"""
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = [_MSG]
        mock_redis.exists.return_value = 1   # 키 존재 = 신선

        watchdog = Watchdog(mock_redis)
        handled = watchdog.scan_once()

        assert handled == 0
        mock_redis.rpush.assert_not_called()
        mock_redis.lpush.assert_not_called()
    ```
  - [x] 7.2 6번째 테스트 — retry storm 전체 라이프사이클:
    ```python
    def test_retry_storm_full_lifecycle():
        """retry 0→1→2→3 → 4번째 stale 스캔에서 DLQ 격리"""
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = [_MSG]
        mock_redis.exists.return_value = 0  # 항상 stale

        # 각 scan_once 호출마다 retry 카운트 증가 시뮬레이션
        retry_counts = iter(["0", "1", "2", "3"])
        mock_redis.get.side_effect = lambda key: next(retry_counts)

        watchdog = Watchdog(mock_redis)

        # 1~3번: 재투입
        for _ in range(3):
            mock_redis.lrange.return_value = [_MSG]
            mock_redis.exists.return_value = 0
        # 4번: DLQ
        mock_redis.get.return_value = "3"
        mock_redis.lrange.return_value = [_MSG]
        handled = watchdog.scan_once()

        assert handled == 1
        mock_redis.lpush.assert_called_with(REDIS_KEY_POSTS_DLQ, _MSG)
    ```
  - [x] 7.3 모든 테스트에서 실제 Redis 연결 없음 — `MagicMock()` 사용.

- [x] **Task 8: 검증 및 마무리**
  - [x] 8.1 `cd detection && ./.venv/bin/pip install -r requirements.txt`
  - [x] 8.2 `cd detection && ./.venv/bin/pytest tests/unit/ -v` → 신규 7건 전부 PASS (story spec 버그 수정 포함)
  - [x] 8.3 `sprint-status.yaml`의 `3-1-redis-큐-소비자-및-watchdog-구현` 상태 갱신: `ready-for-dev → in-progress → review`
  - [x] 8.4 `epic-3` 상태는 이미 `in-progress`로 설정됨

### Review Findings

리뷰일: 2026-04-29 · 리뷰 레이어: Blind Hunter + Edge Case Hunter + Acceptance Auditor (3-layer adversarial)

#### Decision Needed (resolved, 0 outstanding)

- [x] [Review][Decision→Defer] **Watchdog LREM/RPUSH 비원자성 — Lua/MULTI 도입 여부** — `watchdog.py:64-77`. **결정: defer** — race window는 ms 단위 + 단일 Watchdog MVP. Story 3.5 측정 후 발생률 기반 재결정.
- [x] [Review][Decision→Patch] **Poison message 무한 잔류** — `watchdog.py:51-56`. **결정: patch (corrupt-DLQ로 격리)** — `from_json` 실패 시 `posts:corrupt`로 LPUSH + `posts:processing`에서 LREM. 아래 Patch 섹션 D2 항목 참조.
- [x] [Review][Decision→Defer] **같은 `post_id` 중복 메시지 LREM 오제거 가능성** — `queue_consumer.py:45`, `watchdog.py:65,76`. **결정: defer** — DedupChecker(SHA-256) + Story 3.4 DB UniqueConstraint 이중 안전망 존재. 단일 post_id 충돌 빈도 사실상 0.

#### Patch (6, all applied 2026-04-29)

- [x] [Review][Patch] **AC #4 위반 — DLQ 로그에 `post_id` 누락** [detection/src/consumer/watchdog.py:74-80] — `extra`에 `"post_id": post_id` 추가. AC #4 충족.
- [x] [Review][Patch] **Consumer 처리 로그 `correlation_id` 빈 문자열 (P6 위반)** [detection/src/consumer/queue_consumer.py:54-72] — `CrawlEvent.from_json(message)`로 cid + post_id 추출 (best-effort, 실패 시 빈 cid 폴백). 성공/실패 로그 모두 cid 채움.
- [x] [Review][Patch] **성공 처리 시 `posts:retry:{post_id}` / `posts:processing_time:{post_id}` 키 cleanup 누락** [detection/src/consumer/queue_consumer.py:64-66] — LREM 직후 `delete(retry_key(post_id))` + `delete(processing_time_key(post_id))` 호출. event 파싱 성공 시에만 실행.
- [x] [Review][Patch] **`watchdog: object | None` 타입 약화 (spec 일탈)** [detection/src/consumer/queue_consumer.py:31] — `TYPE_CHECKING` 임포트 + `"Watchdog | None"` 문자열 어노테이션. spec Task 5.1 정합성 회복.
- [x] [Review][Patch] **`test_retry_storm_full_lifecycle` 단언 강화** [detection/tests/unit/test_consumer_idempotency.py:121-148] — `incr.call_count == 3` + `delete.assert_called_once_with("posts:retry:inven_1234")` 추가.
- [x] [Review][Patch] **Poison message corrupt-DLQ 격리** [detection/src/consumer/watchdog.py:54-67, shared/config/redis_config.py:9] — `REDIS_KEY_POSTS_CORRUPT = "posts:corrupt"` 신규 + `from_json` 실패 시 LPUSH(corrupt) + LREM(processing) + ERROR 로그. 신규 테스트 `test_watchdog_quarantines_corrupt_message` 추가.

#### Deferred (16)

- [x] [Review][Defer] **Watchdog LREM/RPUSH 비원자성 (D1)** [detection/src/consumer/watchdog.py:64-77] — race window는 ms 단위 + 단일 Watchdog MVP. Story 3.5 측정 후 발생률 기반 재결정.
- [x] [Review][Defer] **같은 `post_id` 중복 메시지 LREM 오제거 가능성 (D3)** [detection/src/consumer/queue_consumer.py:45, watchdog.py:65,76] — DedupChecker(SHA-256) + Story 3.4 DB UniqueConstraint 이중 안전망 존재. 단일 post_id 충돌 빈도 사실상 0.

- [x] [Review][Defer] **`mark_processing` 침묵 실패 (silent except)** [detection/src/consumer/watchdog.py:35-45] — spec Task 4.1 명시 의도(`타임스탬프 기록 실패는 stale 판정으로 처리`)이나 정상 처리 중 메시지가 즉시 stale 판정되는 race window 존재. spec 설계 유지, deferred.
- [x] [Review][Defer] **`processing_time` TTL = stale 임계치 동일 (300s)** [detection/src/consumer/watchdog.py:17] — VARCO 호출 5분 초과 시 처리 중 stale 오판 → 중복 처리 가능. Story 3.2 VARCO SLA 측정 후 TTL 분리 검토.
- [x] [Review][Defer] **`run_forever` 예외 처리 부재 — Connection Error 시 프로세스 종료** [detection/src/consumer/queue_consumer.py:64-65, watchdog.py:97-99] — `while True` 안에 try/except 없음. fail-fast + Docker restart 패턴 의존. Story 5.3 운영 인프라에서 supervisor/restart 정책 확정 시 보완.
- [x] [Review][Defer] **`brpoplpush` Redis 6.2+ deprecated** [detection/src/consumer/queue_consumer.py:32-36] — spec Dev Notes가 `BRPOPLPUSH` 명시 사용. redis-py 5.x에서 정상 동작. 후속 라이브러리 업그레이드 시 `BLMOVE`로 마이그레이션.
- [x] [Review][Defer] **Watchdog 첫 스캔 60초 지연** [detection/src/consumer/watchdog.py:97-99] — `time.sleep` 후 scan 패턴. 부팅 직후 잔존 stale 메시지가 60초 방치. MVP 영향 미미.
- [x] [Review][Defer] **다중 Watchdog 인스턴스 race 보호 부재** [detection/src/consumer/watchdog.py:62-77] — `get → incr` 비원자, multi-Watchdog 시 카운터 race. spec은 단일 Watchdog 가정. Epic 5 운영 확장 시 분산 락 도입 검토.
- [x] [Review][Defer] **환경변수 모듈 임포트 시점 캡처** [detection/src/consumer/queue_consumer.py:14-15, watchdog.py:16-19] — 동적 변경 불가, 테스트 시 `monkeypatch.setenv` 미반영. 통합 테스트 도입 시 함수형으로 전환 검토.
- [x] [Review][Defer] **`LRANGE 0 -1` 풀스캔 — `posts:processing` 길이 증가 시 블로킹** [detection/src/consumer/watchdog.py:49] — Redis O(N) 단일 명령. MVP 메시지 수 작음. 운영 부하 발생 시 페이징/SCAN 도입.
- [x] [Review][Defer] **단일 `redis.Redis` 인스턴스 메인/데몬 스레드 공유** [detection/src/main.py:22-29] — redis-py 클라이언트는 connection pool 단위 thread-safe. BRPOPLPUSH 30초 블로킹 시 풀에서 추가 커넥션 사용. 명시적 풀 크기 미설정.
- [x] [Review][Defer] **SIGTERM/SIGINT graceful shutdown 부재** [detection/src/main.py] — Docker stop 시 BRPOPLPUSH 대기/처리 중 메시지 강제 종료. AOF + Watchdog로 5분 후 복구. Story 5.3에서 시그널 핸들러 + drain 로직.
- [x] [Review][Defer] **`_MAX_RETRIES` 환경변수 외부화 부재 / off-by-one naming** [detection/src/consumer/watchdog.py:19] — 다른 임계값은 env 사용. `MAX_RETRIES=3` 이름이지만 실제 처리 시도 4회(원본+3회 재시도). 이름 명료화 + env 외부화 후속.
- [x] [Review][Defer] **`int(os.environ.get(...))` 잘못된 값 시 import-time `ValueError`** [detection/src/consumer/queue_consumer.py:15, watchdog.py:17-18] — 잘못된 형식 입력 시 모듈 import 실패 → Pod crash. 운영 misconfig 방지 가드 추가 후속.
- [x] [Review][Defer] **Watchdog `RPUSH` 재투입 우선순위** [detection/src/consumer/watchdog.py:75] — Producer LPUSH + Consumer BRPOPLPUSH(right pop) 구조에서 RPUSH는 다음 1순위로 소비됨. spec 주석은 "FIFO" 의도이나 실제로는 retry 메시지 우선 처리 → poison priority inversion 가능성. backoff 정책 도입 시 LPUSH 또는 별도 retry queue 검토.
- [x] [Review][Defer] **`pytest.ini` 옵션 부재 / `process_fn` 시그니처 단순** [detection/pytest.ini, detection/src/consumer/queue_consumer.py:23] — `addopts`/markers 미정의. `Callable[[str], None]`은 Story 3.2에서 비동기/컨텍스트 전달 필요 시 변경 예정.

> **Dismissed (noise):** `to_json/from_json` 라운드트립 명시 검증 추가 제안, `pytest.ini` "no-violation" 노트 — 모두 실질 결함 아님.

## Dev Notes

### 본 스토리 범위 (Scope Boundary)

| 이번 스토리에서 한다 | 이번 스토리에서 **하지 않는다** |
|---|---|
| `queue_consumer.py` — BRPOPLPUSH, LREM | VARCO Translation 호출 → Story 3.2 |
| `watchdog.py` — stale 감지, 재투입, DLQ | VARCO LLM 분류 → Story 3.3 |
| `main.py` — 스레드 기반 진입점 (stub 콜백) | `detection_repository.py` RDS 저장 → Story 3.4 |
| `pytest.ini` + `requirements.txt` 업데이트 | `token_bucket.py` Rate limit → Story 3.2 |
| 단위 테스트 6건 (MagicMock Redis) | `retry_handler.py` → Story 3.3 |
| `detection/src/config/redis_config.py` | DB 멱등성 UniqueConstraint 검증 → Story 3.4 |

### 현재 `detection/` 구조 (Story 3.1 착수 시점)

```
detection/
├── requirements.txt              # redis, boto3, httpx, python-dotenv, -e ../shared
├── .env.example                  # (미확인 — 없으면 신규 생성)
└── src/
    ├── __init__.py               # 존재
    └── mocks/
        ├── __init__.py           # 존재
        └── varco_mock.py         # 완성 (modes: clean, illegal, rate_limited, timeout)
    tests/
    ├── __init__.py               # 존재
    └── unit/
        └── __init__.py           # 존재
```

**이 스토리에서 추가될 구조:**

```
detection/
├── requirements.txt              ← 수정 (redis>=5.0.0, pytest 추가)
├── pytest.ini                    ← 신규
└── src/
    ├── config/
    │   ├── __init__.py           ← 신규
    │   └── redis_config.py       ← 신규 (get_mq_client)
    ├── consumer/
    │   ├── __init__.py           ← 신규
    │   ├── queue_consumer.py     ← 신규 (QueueConsumer)
    │   └── watchdog.py           ← 신규 (Watchdog)
    └── main.py                   ← 신규 (stub 진입점)
    tests/
    └── unit/
        └── test_consumer_idempotency.py  ← 신규 (6건)
```

### 공유 모듈 임포트 패턴

```python
# 이미 완성된 shared 모듈 — 재구현 금지
from shared.config.redis_config import (
    REDIS_MQ_DB,                    # = 0
    REDIS_KEY_POSTS_QUEUE,          # = "posts:queue"
    REDIS_KEY_POSTS_PROCESSING,     # = "posts:processing"
    REDIS_KEY_POSTS_DLQ,            # = "posts:dlq"
)
from shared.models.crawl_event import CrawlEvent  # to_json / from_json
from shared.structured_logger import get_logger    # JSON 구조화 로그
from shared.correlation_id import generate         # UUID 생성 (필요 시)
```

### Redis API 패턴

```python
import redis
from shared.config.redis_config import REDIS_MQ_DB

r = redis.from_url("redis://localhost:6379", db=REDIS_MQ_DB, decode_responses=True)

# 원자적 소비 (BRPOPLPUSH)
message = r.brpoplpush("posts:queue", "posts:processing", timeout=30)
# timeout=0 → 무한 블로킹. timeout=30 → 30초 후 None 반환.

# ACK (처리 완료 시)
r.lrem("posts:processing", 1, message)  # count=1: 첫 번째 일치 항목만 제거

# 재투입 (Watchdog)
r.rpush("posts:queue", message)   # RIGHT push → BRPOPLPUSH(right-pop)와 FIFO 유지

# DLQ 이동
r.lpush("posts:dlq", message)     # LEFT push (소비 순서 무관)

# retry 카운터 (TTL 없음 — Watchdog이 DLQ 이동 시 DEL)
r.incr("posts:retry:{post_id}")
r.get("posts:retry:{post_id}")    # str or None
r.delete("posts:retry:{post_id}")

# 타임스탬프 키 (stale 판정용)
r.setex("posts:processing_time:{post_id}", STALE_SECONDS, "1")
r.exists("posts:processing_time:{post_id}")  # 0: 만료(stale), 1: 신선
```

**BRPOPLPUSH vs BLMOVE:**  
Redis 6.2+에서 `BRPOPLPUSH`는 deprecated, `BLMOVE source dest RIGHT LEFT timeout`이 권장됨. 그러나 epics.md AC가 `BRPOPLPUSH`를 명시하며, Redis 7에서도 제거되지 않고 작동함. redis-py 5.x의 `r.brpoplpush(src, dst, timeout)` 그대로 사용.

### Watchdog 스테일 감지 메커니즘

```
Consumer가 BRPOPLPUSH 실행
   ↓
Watchdog.mark_processing(message) 호출
   ↓
SETEX posts:processing_time:{post_id} 300 "1"
   ↓ (300초 경과)
키 자동 만료

Watchdog.scan_once() 매 60초 실행
   ↓
lrange posts:processing 0 -1
   ↓ 각 메시지마다
EXISTS posts:processing_time:{post_id}
   → 0 (만료): stale → 재투입 or DLQ
   → 1 (존재): 신선 → 스킵
```

### 환경변수 목록

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `REDIS_URL` | `redis://localhost:6379` | Redis 연결 URL |
| `SERVICE_NAME` | `detection` | 구조화 로그 service 필드 |
| `BRPOPLPUSH_TIMEOUT` | `30` | brpoplpush blocking timeout (초) |
| `WATCHDOG_STALE_SECONDS` | `300` | stale 판정 기준 (초) |
| `WATCHDOG_POLL_INTERVAL` | `60` | Watchdog 폴링 주기 (초) |

### Anti-Patterns to Avoid

1. ❌ **`LPOP`/`RPOP` + `LPUSH` 사용** — 두 명령 사이에 크래시 시 메시지 유실. 반드시 `BRPOPLPUSH` (원자적 연산).
2. ❌ **처리 실패 시 즉시 `LREM`** — 메시지를 posts:processing에 남겨야 Watchdog이 복구 가능.
3. ❌ **`BRPOPLPUSH timeout=0`** — 프로세스 종료 시 블로킹 해제 불가. `timeout=30` 권장.
4. ❌ **retry 카운터 없이 무한 재투입** — retry storm 발생. `posts:retry:{post_id}` INCR + 3회 초과 시 DLQ 이동 필수.
5. ❌ **`posts:processing` 타임스탬프를 메시지 내부에 포함** — `CrawlEvent` 스키마를 오염시킴. 별도 Redis 키 사용.
6. ❌ **`decode_responses=False`** — `LREM`의 값 인자가 bytes vs str 불일치로 미삭제 발생.
7. ❌ **`time.sleep(0)` Watchdog 폴링** — Redis `lrange` 과부하. `WATCHDOG_POLL_INTERVAL` 환경변수로 최소 60초.
8. ❌ **`Watchdog`을 메인 스레드에서 실행** — `QueueConsumer.run_forever()`가 블로킹이므로 Watchdog은 반드시 데몬 스레드로 분리.

### Architecture Compliance Notes

- **NFR16 (원자적 큐 연산)** — `BRPOPLPUSH` 단일 명령으로 pop + push 원자적 실행. Redis AOF(`--appendonly yes`) + DB0 보장.
- **NFR13 (Redis AOF 데이터 보존)** — `infra/docker-compose.yml`에 `redis-server --appendonly yes` 이미 설정됨. EC2 재시작 후 `posts:processing` 메시지 보존.
- **architecture.md P6 (구조화 로그)** — 모든 로그에 `extra={"correlation_id": ..., "service": _SERVICE_NAME}` 포함.
- **architecture.md P2 (Redis 키 명명)** — `posts:queue`, `posts:processing`, `posts:dlq`, `posts:retry:{id}`, `posts:processing_time:{id}` 모두 소문자 콜론 계층 준수.
- **architecture.md Redis DB 분리** — `REDIS_MQ_DB=0` 상수 사용. `db=0` 하드코딩 금지.

### 주요 의존 관계

```
Story 2.5 → posts:queue에 CrawlEvent LPUSH
Story 3.1 → posts:queue에서 BRPOPLPUSH 소비 (이 스토리)
Story 3.2 → _stub_process를 VARCOTranslate + classify로 교체
Story 3.3 → retry_handler + DLQ 처리 (llm_classifier 실패 시)
Story 3.4 → detection_repository.py RDS 저장
```

### Project Context Reference

- [shared/config/redis_config.py](shared/config/redis_config.py) — `REDIS_MQ_DB`, `REDIS_KEY_POSTS_*` 상수
- [shared/models/crawl_event.py](shared/models/crawl_event.py) — `CrawlEvent` dataclass, `from_json()` / `to_json()`
- [shared/structured_logger.py](shared/structured_logger.py) — `get_logger(name)` JSON formatter
- [detection/src/mocks/varco_mock.py](detection/src/mocks/varco_mock.py) — `VarcoMock(mode, latency_ms)` (3.2부터 사용)
- [infra/docker-compose.yml](infra/docker-compose.yml) — Redis AOF 설정 확인 (`--appendonly yes`)
- [architecture.md — detection/ 디렉토리 구조](/_bmad-output/planning-artifacts/architecture.md)
- [epics.md — Story 3.1 AC](/_bmad-output/planning-artifacts/epics.md)
- [crawler/src/consumer/queue_consumer.py → 참조 패턴](crawler/src/scheduler/crawl_scheduler.py) — `RedisPublisher.enqueue()` LPUSH 패턴

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

- `test_retry_storm_full_lifecycle`: story spec 버그 수정 — `mock_redis.get.side_effect` 설정 후 `return_value`로 override 시 side_effect 우선, `scan_once()` 1회만 호출하므로 DLQ 미도달. 수정: 3회 `scan_once()` 루프 후 4번째 호출 시 DLQ 진입하도록 수정.

### Completion Notes List

- `QueueConsumer`: `BRPOPLPUSH` 원자 소비 + `LREM` ACK + 실패 시 잔류(Watchdog 복구). `watchdog=None` 선택적 의존성 주입.
- `Watchdog`: TTL 키 기반 stale 판정(`SETEX posts:processing_time:{id}`) + retry < 3 재투입(rpush) + retry ≥ 3 DLQ(lpush) + `delete` retry 키.
- `main.py`: Watchdog 데몬 스레드 + QueueConsumer 메인 루프 + `_stub_process` (Story 3.2 교체 예정).
- 테스트 7건 PASS (AC #6 6건 + `test_consumer_returns_false_on_timeout` 추가), 실제 Redis 호출 0건.
- story spec의 `test_retry_storm_full_lifecycle` 버그를 수정하여 실제 4회 스캔 시뮬레이션으로 구현.

### File List

신규:
- `detection/pytest.ini`
- `detection/src/config/__init__.py`
- `detection/src/config/redis_config.py`
- `detection/src/consumer/__init__.py`
- `detection/src/consumer/queue_consumer.py`
- `detection/src/consumer/watchdog.py`
- `detection/src/main.py`
- `detection/tests/unit/test_consumer_idempotency.py`

수정:
- `detection/requirements.txt` (redis>=5.0.0, pytest, pytest-mock 추가)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (3-1: backlog → ready-for-dev, epic-3: backlog → in-progress)

비변경:
- `detection/src/mocks/varco_mock.py`
- `detection/src/mocks/__init__.py`
- `shared/` 전체

## Change Log

| 날짜 | 변경 | 사유 |
|---|---|---|
| 2026-04-29 | Story 3.1 컨텍스트 작성 (`Status: ready-for-dev`) | bmad-create-story |
| 2026-04-29 | QueueConsumer + Watchdog + main.py 구현, 단위 테스트 7건 PASS, `Status: review` | bmad-dev-story |
| 2026-04-29 | Code Review 완료 — 3-layer adversarial(Blind/Edge/Auditor), 6 patch 적용(AC#4 post_id, P6 cid, 성공 cleanup, 타입 강화, 테스트 강화, corrupt-DLQ), 16 deferred, 8건 PASS, `Status: done` | bmad-code-review |
