# Story 3.3: OpenAI 멀티모달 LLM 분류 + Tier 라우팅 (전면 재작성)

Status: review

> **본 스토리 핵심:** Story 3-2 review 코드(VARCO Translation)는 폐기. 본 스토리는 `detection/src/`에 OpenAI 멀티모달 LLM 단일 호출 + Tier 라우팅 + Tier 차등 retry + 일일 비용 cap을 본 구현한다. SPIKE 3.0(done) 결과(`gpt-4o`, `json_schema` strict, $0.0019/post, p95 3.69s)를 그대로 적용한다. **본 스토리의 성공 기준은 `python -m detection.src.main`이 실제로 떠서 `posts:queue` 메시지 1건을 소비하고 OpenAI 호출 → 결과 로그까지 흘러가는 것**(통합 실사 작동). RDS 저장은 Story 3-4, 정확도 측정은 Story 3-5, Tier 알림·보존은 Story 3-6.
>
> **[전제 조건]** Story 3-1 done(`QueueConsumer`/`Watchdog`/`BRPOPLPUSH` ACK 패턴). SPIKE 3.0 done(`smoke_openai.py`/`spike_llm.py` 결과 docs/llm-spike-2026-05-27.md). `infra/.env`에 본인 `OPENAI_API_KEY` 입력. `feat/epic3-detection` 브랜치.
>
> **[재사용 부품]** Story 3-2/3-3 review 코드에서 다음은 그대로 유지·확장:
> - `detection/src/retry/retry_handler.py` — `RetryHandler` + `RetryExhaustedError`. exception whitelist에 `openai.APITimeoutError` / `openai.APIConnectionError` 추가, attempts를 Tier별 차등으로 확장.
> - `detection/src/rate_limit/token_bucket.py` — `TokenBucket` Redis Lua atomic acquire. key constant rename만(`varco:` → `llm:`).
> - `detection/src/consumer/queue_consumer.py` + `consumer/watchdog.py` — Story 3-1 부품, 변경 없음.
> - `detection/src/pipeline/detection_pipeline.py` — interim TODO 제거 + 신 wiring.
> - `shared/correlation_id.py` + `shared/structured_logger.py` — 그대로.
>
> **[폐기]** Story 3-2 cleanup을 본 PR에 흡수:
> - `detection/src/pipeline/varco_client.py` — 삭제
> - `detection/src/mocks/varco_mock.py` — `llm_mock.py`로 rename + 재작성 (OpenAI 의미론)
> - `shared/interfaces/varco.py` — `shared/interfaces/llm.py`로 rename + Protocol 갱신
> - `shared/config/redis_config.py::REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY` → `REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY` (`llm:rate_limit:classify`)
> - `detection/src/pipeline/llm_classifier.py` — 재작성 (VARCO 호출 → OpenAI 호출 + tier_router)
> - 환경변수 `VARCO_*` → `LLM_*` 정리 (이미 `infra/.env.example`에 반영됨)
> - `tests/fixtures/varco/mock_response_*.json` → `tests/fixtures/llm/mock_response_*.json`으로 이동 + OpenAI schema 형식으로 교체

## Story

개발자로서,
게시글의 본문 텍스트와 첨부 이미지가 OpenAI 멀티모달 LLM 단일 호출로 분류되어 Tier(T1/T2/T3/T4)와 함께 결과가 산출되기를 원한다,
그래서 별도 번역·Vision 단계 없이 단일 호출로 다국어·이미지·불법 분류·Tier 라우팅이 통합 처리되고, 운영 환경에서 crawler → detection 파이프라인이 실사로 흐른다.

## Acceptance Criteria

1. **Given** `CrawlEvent`(텍스트 + `image_urls`/`s3_image_paths`)가 있을 때
   **When** `LLMClient.classify(text, images=[...])`가 호출되면
   **Then** `detection/src/pipeline/llm_client.py`의 `LLMClient`가 OpenAI Chat Completions API(`openai.OpenAI().chat.completions.create`)에 멀티모달 단일 호출을 보내고 다음 형식의 응답을 반환한다:
   ```python
   @dataclass
   class LLMResponse:
       type: str                     # enum: 핵_치트 / 사설서버 / 불법프로그램_배포 / 계정_거래 / 매크로_판매 / 리세마라 / 현금화 / 광고_도배 / 기타
       confidence: float             # 0.0~1.0
       reason_ko: str                # 항상 한국어
       translated_text_ko: str | None  # 한국어 원문이면 None, 외 언어면 한국어 번역
       image_observed: bool          # 이미지 첨부 시 LLM이 이미지를 실제로 인식했는지
       input_tokens: int
       output_tokens: int
       cost_usd: float               # 응답 직후 `cost_cap.estimate_cost()`로 산출
   ```
   **And** 호출은 `response_format={"type": "json_schema", "json_schema": {"name": "tracker_classification", "strict": True, "schema": {...}}}`로 구조화 출력을 강제한다 (스키마는 SPIKE의 `spike_llm.py::CLASSIFICATION_SCHEMA` 그대로 이식).
   **And** `LLMClient`는 다음 2개 public 메서드를 노출한다 (텍스트/이미지 분리 가능 인터페이스):
   - `classify(text: str, images: list[str] = []) -> LLMResponse` — 기본 진입점. `images`가 비면 텍스트 only, 채워지면 멀티모달.
   - `classify_text_only(text: str) -> LLMResponse` — 명시적 텍스트 only (fallback 경로).
   **And** `images`는 S3 URL / 로컬 경로 / `data:image/...;base64,...` URI 셋 다 받는다. 로컬 경로면 base64 인코딩 후 `data:` URI로 변환. S3 URL은 `s3://`이면 `s3_image_paths`에서 미리 presigned URL 변환 책임은 호출자(`DetectionPipeline`)에 위임. `LLMClient`는 string을 그대로 `image_url`로 전달.
   **And** 환경변수 `LLM_SEND_IMAGES=false`이면 `images` 인자가 채워졌어도 텍스트 only로 fallback (이미지 PII 차단 토글, 기본 `false`).
   **And** 환경변수 `LLM_SPLIT_TEXT_IMAGE=true`이면 텍스트 호출 + 이미지 호출을 별도로 보내고 결과를 merge (기본 `false` 단일 호출).
   **And** 호출 직전 `TokenBucket(key=REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY).acquire()`로 토큰 차감(NFR14).
   **And** 호출 직후 `cost_cap.record(input_tokens, output_tokens, model)`로 일일 누적 비용 갱신.

2. **Given** `LLMResponse`의 `type`이 있을 때
   **When** `tier_router.route(type)` 또는 `tier_router.route_multi(types)`가 실행되면
   **Then** `detection/src/pipeline/tier_router.py`가 다음 매핑을 적용하여 `Tier` enum(`"T1" | "T2" | "T3" | "T4"`)을 반환한다:
   ```python
   TYPE_TO_TIER: dict[str, str] = {
       "핵_치트": "T1", "사설서버": "T1", "불법프로그램_배포": "T1",
       "계정_거래": "T2", "매크로_판매": "T2",
       "리세마라": "T3", "현금화": "T3", "광고_도배": "T3",
       "기타": "T4",
   }
   ```
   **And** `route_multi(types: list[str]) -> str`은 여러 type 후보 중 **가장 상위 Tier**를 선택한다(T1 > T2 > T3 > T4). 현 OpenAI 호출은 단일 type만 반환하지만, 향후 multi-label 응답 확장 대비 인터페이스 신설.
   **And** 알 수 없는 type은 `T4`로 fallback + WARNING 로그(`extra={"unknown_type": type}`).

3. **Given** `tier_config.py`에 Tier별 threshold가 정의되어 있을 때
   **When** `DetectionPipeline`이 분류 결과를 처리하면
   **Then** `detection/src/config/tier_config.py`가 다음 dict + env override를 제공한다:
   ```python
   TIER_THRESHOLDS: dict[str, float] = {
       "T1": float(os.environ.get("TIER_THRESHOLD_T1", "0.65")),
       "T2": float(os.environ.get("TIER_THRESHOLD_T2", "0.75")),
       "T3": float(os.environ.get("TIER_THRESHOLD_T3", "0.85")),
       "T4": float(os.environ.get("TIER_THRESHOLD_T4", "0.90")),
   }
   ```
   **And** **threshold는 RDS 저장 여부에 영향을 주지 않는다** — 모든 분류 결과(`is_illegal=false` 포함, `confidence < threshold` 포함, T4 포함)는 Story 3-4에서 1:1 저장된다 (Sprint Change Proposal 부록 A-2 전수 저장 정책). threshold는 대시보드 디스플레이 필터로만 작동하므로 본 스토리에서는 **참조만** 하고 분기에는 사용하지 않는다.
   **And** `tier_config.is_above_threshold(tier, confidence) -> bool` 유틸 함수를 노출하여 Story 3-4 / Epic 4에서 디스플레이 필터 적용 시 사용.

4. **Given** `LLMClient`가 OpenAI 호출 직후 token usage를 보고할 때
   **When** `cost_cap.record(input_tokens, output_tokens, model)`이 호출되면
   **Then** `detection/src/rate_limit/cost_cap.py`의 `CostCap` 클래스가 Redis(DB2, `llm:cost:YYYY-MM-DD` 키, TTL 48h)에 누적 비용(USD float * 1e6 → int micro-USD)을 atomic INCRBY로 갱신한다.
   **And** 호출 전 `cost_cap.check_and_hold()`가 다음 동작:
   - `cumulative_usd < LLM_DAILY_COST_CAP_USD`(기본 `$5`)면 즉시 return (호출 진행)
   - 도달하면 `_logger.warning("일일 비용 cap 도달 — hold")` + `time.sleep(60)` 후 재확인 (다음 날 자정 KST 넘어가면 키 만료 → 자동 재개)
   - `LLM_DAILY_COST_CAP_USD=0` 또는 unset이면 cap 비활성
   **And** 비용 산출 공식은 SPIKE의 `spike_llm.py::PRICING` 테이블 그대로 이식 (gpt-4o: input $2.50 / output $10.00 per 1M tokens). 모델별 단가 미등록 시 gpt-4o 가격 fallback.
   **And** Hold 상태는 `correlation_id` 없이 service-level 이벤트로 로그 — `extra={"service": "detection", "cumulative_usd": ...}`.

5. **Given** OpenAI 호출이 일시적 외부 오류(`openai.APITimeoutError` / `openai.APIConnectionError` / `httpx.HTTPError` / `TimeoutError`)를 발생시킬 때
   **When** `RetryHandler`가 이를 감지하면
   **Then** `detection/src/retry/retry_handler.py`의 `_RETRYABLE_EXCEPTIONS` tuple에 `openai.APITimeoutError`, `openai.APIConnectionError`가 추가된다 (기존 `TimeoutError`/`ConnectionError`/`httpx.HTTPError` 유지).
   **And** **Tier 차등 retry** — `RetryHandler.execute_with_retry()` 시그니처에 `max_attempts: int | None = None` 추가. `DetectionPipeline`이 1차 호출(tier 미상) 시 환경변수 `RETRY_MAX_ATTEMPTS=3` default 사용, 응답에서 tier 확정 후 2회차 이상 호출은 발생하지 않는 구조(OpenAI 단일 호출 모델 → retry는 같은 tier에서). Tier 차등은 **호출 측에서** `max_attempts` 인자로 주입:
   ```python
   TIER_RETRY_ATTEMPTS = {"T1": 3, "T2": 2, "T3": 1, "T4": 0}
   ```
   현 흐름에서는 응답을 받기 전에는 tier를 모르므로 **default 3회 retry 적용 + 응답 후 cost_cap.record만 함**. Tier 차등 retry는 응답이 retryable 오류로 실패한 시나리오에서 동일 게시글 재시도 시 적용 — `DetectionPipeline`이 첫 시도 후 `LLMResponse.type`이 있으면 그 tier의 attempts로 재시도, 첫 시도부터 실패면 default 3 (실용 절충).
   **And** `RateLimitError`(OpenAI 429) → `Retry-After` 헤더 sleep 후 1회 자동 재시도, 본 `RetryHandler`는 catch하지 않음 (호출자 책임 — `LLMClient` 내부에서 1회 sleep+retry).
   **And** retry 한도 초과 시 기존 DLQ 이동 로직(`LPUSH posts:dlq` → `LREM posts:processing` → retry/processing_time DELETE → `RetryExhaustedError`) 그대로 동작.

6. **Given** `shared/config/redis_config.py`에 토큰 버킷 key 상수가 있을 때
   **When** 본 스토리 PR이 반영되면
   **Then** `REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY`가 `REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY = "llm:rate_limit:classify"`로 rename된다.
   **And** `detection/src/rate_limit/token_bucket.py`의 env var `VARCO_RATE_LIMIT_CAPACITY` / `VARCO_RATE_LIMIT_REFILL_PER_SEC` / `VARCO_RATE_LIMIT_MAX_WAIT_SEC`가 `LLM_RATE_LIMIT_CAPACITY` / `LLM_RATE_LIMIT_REFILL_PER_SEC` / `LLM_RATE_LIMIT_MAX_WAIT_SEC`로 rename된다 (default 값 60 / 1 / 120 유지).
   **And** `infra/.env.example`에 신규 env var 5종 추가: `LLM_RATE_LIMIT_CAPACITY=60`, `LLM_RATE_LIMIT_REFILL_PER_SEC=1`, `LLM_RATE_LIMIT_MAX_WAIT_SEC=120`, `TIER_THRESHOLD_T1=0.65` 등 4종. 기존 `LLM_*` 5종은 이미 존재(SPIKE 3.0 시점에 추가됨).

7. **Given** `DetectionPipeline.process(message)`가 큐 메시지를 받을 때
   **When** 본 스토리 작업이 완료되면
   **Then** `detection/src/pipeline/detection_pipeline.py`의 `process()`가 다음 흐름을 수행한다 (`# TODO(Story 3-3)` 라인 제거):
   ```python
   def process(self, message: str) -> None:
       event = CrawlEvent.from_json(message)

       self._cost_cap.check_and_hold()  # cap 도달 시 sleep

       images: list[str] = event.s3_image_paths or event.image_urls
       response = self._retry_handler.execute_with_retry(
           lambda: self._classifier.classify(event.raw_text, images=images),
           message=message,
           post_id=event.post_id,
           correlation_id=event.correlation_id,
       )

       tier = self._tier_router.route(response.type)

       self._cost_cap.record(response.input_tokens, response.output_tokens, self._classifier.model_version)

       _logger.info(
           "classification — type=%s tier=%s conf=%.3f cost=$%.5f tokens(in/out)=%d/%d image_observed=%s",
           response.type, tier, response.confidence, response.cost_usd,
           response.input_tokens, response.output_tokens, response.image_observed,
           extra={
               "correlation_id": event.correlation_id,
               "service": "detection",
               "post_id": event.post_id,
               "tier": tier,
               "model_version": self._classifier.model_version,
           },
       )
       # TODO(Story 3-4): detection_repository.save(event, response, tier, self._classifier.model_version)
   ```
   **And** `LLMClassifier.classify(text, images)`는 `LLMClient.classify(text, images)`를 위임 호출하고, `type` enum 검증(9개 값 중 하나)과 `confidence` 범위 검증(0.0~1.0)을 유지한다. 위반 시 `ValueError` (non-retryable, RetryHandler가 즉시 propagate).
   **And** `LLMClassifier.model_version` property는 `f"openai:{LLM_MODEL}:{date}"` 형식으로 반환 — Story 3-4에서 RDS `detections.model_version` 컬럼에 직접 매핑. `date`는 환경변수 `LLM_MODEL_RELEASE_DATE=2024-08-06` (default `gpt-4o` pin 날짜) 또는 클래스 생성 시점 `datetime.utcnow().date().isoformat()`. 운영 안정성을 위해 env var 사용 권장.

8. **Given** `detection/src/main.py`의 의존성 wiring이 있을 때
   **When** 본 스토리 작업이 완료되면
   **Then** `main.py`가 다음과 같이 갱신된다 (VARCO 의존 제거):
   ```python
   from detection.src.config.redis_config import get_mq_client, get_rate_limit_client
   from detection.src.consumer.queue_consumer import QueueConsumer
   from detection.src.consumer.watchdog import Watchdog
   from detection.src.pipeline.detection_pipeline import DetectionPipeline
   from detection.src.pipeline.llm_classifier import LLMClassifier
   from detection.src.pipeline.llm_client import LLMClient
   from detection.src.pipeline.tier_router import TierRouter
   from detection.src.rate_limit.cost_cap import CostCap
   from detection.src.rate_limit.token_bucket import TokenBucket
   from detection.src.retry.retry_handler import RetryHandler
   from shared.config.redis_config import REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY


   def main() -> None:
       mq_client = get_mq_client()
       rate_limit_client = get_rate_limit_client()

       llm_client = LLMClient()  # OpenAI 클라이언트 + env var 로딩 내부
       classify_bucket = TokenBucket(rate_limit_client, key=REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY)
       cost_cap = CostCap(rate_limit_client)
       classifier = LLMClassifier(llm_client, classify_bucket)
       tier_router = TierRouter()
       retry_handler = RetryHandler(mq_client)

       pipeline = DetectionPipeline(classifier, tier_router, cost_cap, retry_handler)

       watchdog = Watchdog(mq_client)
       consumer = QueueConsumer(mq_client, pipeline.process, watchdog=watchdog)

       watchdog_thread = threading.Thread(target=watchdog.run_forever, daemon=True)
       watchdog_thread.start()
       consumer.run_forever()
   ```

9. **Given** `detection/tests/`에 단위·통합 테스트가 있을 때
   **When** `cd detection && ./.venv/bin/pytest tests/ -v`를 실행하면
   **Then** 다음 신규 테스트 ≥ 8건이 모두 PASS하고 외부 네트워크/실 OpenAI 호출 0건이다:
   - `test_llm_client.py` 4건 — (a) text only 호출 (MagicMock(openai.OpenAI), response_format 인자 검증) (b) images 포함 멀티모달 호출 (content가 list 형태 + `image_url` 포함 검증) (c) `LLM_SEND_IMAGES=false` 시 텍스트 fallback (d) RateLimitError(429) → Retry-After sleep 후 재시도
   - `test_tier_router.py` 2건 — (a) 9개 type → Tier 매핑 전수 (b) 알 수 없는 type → T4 + WARNING 로그
   - `test_cost_cap.py` 2건 (fakeredis) — (a) record + check_and_hold 정상 흐름 (cap 미달) (b) cap 도달 → sleep 진입 (monkeypatch `time.sleep`)
   - `test_llm_pipeline.py` (integration, `llm_mock.py` 기반) 2건 — (a) clean path: 한국어 이벤트 → classify → T4 분류 → 로그 출력 + LREM 호출 (b) timeout → DLQ path: `LLMMock(mode="timeout")` → retry 3회 실패 → DLQ LPUSH + RetryExhaustedError
   **And** 기존 Story 3-1 테스트 8건(`test_consumer_idempotency.py` 등) + 본 스토리 신규 ≥10건 = **누적 ≥ 18건 PASS**. Story 3-2 review 테스트(`test_translate.py` 등)는 본 PR에서 삭제.
   **And** 폐기된 `test_token_bucket.py`(VARCO 단위) / `test_retry_handler.py`(VARCO 단위) / `test_llm_classifier.py`(기존 VARCO 단위)는 OpenAI 의미론에 맞게 갱신 — 단위 테스트 자체는 유지, mock 객체만 `LLMClient`로 교체.

10. **Given** 모든 단위·통합 테스트 통과 후
    **When** dev가 **실사 통합 smoke**를 수행하면 (사용자의 본 스토리 핵심 요청 — "다른 파트와 함께 실사 돌아가는 모습"):
    1. 로컬 `docker compose up -d redis postgres` (infra/docker-compose.yml — 기존 셋업)
    2. `infra/.env`에 본인 `OPENAI_API_KEY` 입력 확인
    3. **수동 큐 적재**: `redis-cli -n 0 LPUSH posts:queue '<CrawlEvent JSON>'` — 샘플은 SPIKE 라벨셋 한 줄을 `CrawlEvent.to_json()` 형식으로 변환 (스크립트 `detection/scripts/seed_one_post.py` 신규 작성, ≤30 lines)
    4. `cd detection && python -m detection.src.main` 실행
    5. 로그에 다음 1줄이 출력되어야 함: `classification — type=핵_치트 tier=T1 conf=0.95 cost=$0.0019 tokens(in/out)=120/45 image_observed=False`
    6. `redis-cli -n 0 LLEN posts:processing` → `0` 확인 (LREM 정상)
    **Then** 위 6단계가 사람 손으로 1회 성공함을 PR description 또는 `docs/integration-smoke-3-3.md`(≤20 lines)에 캡처 또는 로그 인용으로 증빙한다. **이 AC가 본 스토리의 "성공" 그 자체**.
    **And** 실사 smoke는 **crawler를 실제로 띄울 필요 없음** — 큐 적재 스크립트로 우회. crawler까지 묶은 end-to-end는 Epic 3 closing(Story 3-6 완료 후) 또는 Story 5-4 e2e 데모에서.
    **And** OpenAI 비용은 단일 호출이므로 ≤ $0.005, dev 본인 부담 수용.

> **AC 출처:** epics.md L602-630 Story 3.3 AC + SPIKE 3.0 권장값 (`gpt-4o`/`json_schema`/$5 cap). sprint-change-proposal-2026-05-27.md §Section 4.2 architecture 갱신(L88, L577-608, L782). 부록 A-2 전수 저장 정책(threshold는 디스플레이 필터). AC #10은 사용자 결정(2026-05-27 대화): "detection 본 구현 + 다른 파트와 함께 실사 돌아가는 모습 완성"이 본질 — 단위 테스트 통과만으로는 본 스토리 done 아님.

## Tasks / Subtasks

- [x] **Task 1 (AC: #6) — Redis key + env var rename (cleanup 선행)**
  - [x] 1.1 `shared/config/redis_config.py`: `REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY` → `REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY`. 값 `"llm:rate_limit:classify"`. `# 2026-05-27 PIVOT` 주석 추가.
  - [x] 1.2 `detection/src/rate_limit/token_bucket.py`: env var 3종 rename(`VARCO_*` → `LLM_*`). default 값 유지.
  - [x] 1.3 import 정리.
  - [x] 1.4 잔존 `VARCO_RATE_LIMIT` / `varco:rate_limit` 0건 (cleanup commit으로 일괄 제거).

- [x] **Task 2 (AC: #1) — `LLMClient` 신규 작성**
  - [x] 2.1 `LLMResponse` dataclass (shared/interfaces/llm.py로 이동) + `LLMClient` 클래스.
  - [x] 2.2 `CLASSIFICATION_SCHEMA` + `SYSTEM_PROMPT`을 spike_llm.py에서 이식.
  - [x] 2.3 `classify(text, images=[])` — `LLM_SEND_IMAGES=false` 시 텍스트 fallback.
  - [x] 2.4 `LLM_SPLIT_TEXT_IMAGE=true` 분리 호출 + merge.
  - [x] 2.5 `classify_text_only(text)` 명시적 진입점.
  - [x] 2.6 429 Retry-After 1회 자동 재시도 → 2회차도 429이면 `RateLimitError` raise.

- [x] **Task 3 (AC: #2) — `TierRouter` 신규 작성**
  - [x] 3.1 `TYPE_TO_TIER` dict + `TIER_PRIORITY` list.
  - [x] 3.2 `route` + `route_multi`.
  - [x] 3.3 알 수 없는 type → T4 fallback + WARNING.

- [x] **Task 4 (AC: #3) — `tier_config.py` 신규 작성**
  - [x] 4.1 `TIER_THRESHOLDS` + env override + `TIER_RETRY_ATTEMPTS`.
  - [x] 4.2 `is_above_threshold` 유틸.

- [x] **Task 5 (AC: #4) — `CostCap` 신규 작성**
  - [x] 5.1 `CostCap.__init__` + `LLM_DAILY_COST_CAP_USD` 로딩.
  - [x] 5.2 `record` — micro-USD INCRBY + 48h TTL.
  - [x] 5.3 `check_and_hold` — sleep loop (max 5회).
  - [x] 5.4 `PRICING` 이식 + gpt-4o fallback.

- [x] **Task 6 (AC: #5) — `RetryHandler` exception whitelist 확장**
  - [x] 6.1 `APITimeoutError` / `APIConnectionError` 추가.
  - [x] 6.2 `max_attempts` 인자 추가.
  - [x] 6.3 로그 문구 "VARCO classify" → "LLM classify".

- [x] **Task 7 (AC: #7) — `LLMClassifier` + `DetectionPipeline` 재작성**
  - [x] 7.1 `LLMClassifier` — LLMInterface 위임 + 9-type enum + confidence 검증 + `model_version` `openai:{model}:{date}`.
  - [x] 7.2 `DetectionPipeline` — check_and_hold → classify → route → record → 구조화 로그.
  - [x] 7.3 9-type enum 반영.

- [x] **Task 8 (AC: #8) — `main.py` wiring 갱신**
  - [x] 8.1 VARCO import 제거.
  - [x] 8.2 LLMClient/TierRouter/CostCap import.
  - [x] 8.3 `DetectionPipeline(classifier, tier_router, cost_cap, retry_handler)` 적용.

- [x] **Task 9 — Story 3-2 cleanup**
  - [x] 9.1 `varco_client.py` 삭제.
  - [x] 9.2 `varco_mock.py` → `llm_mock.py` rename + 재작성.
  - [x] 9.3 `shared/interfaces/varco.py` → `llm.py` rename + Protocol 갱신.
  - [x] 9.4 `tests/fixtures/varco/` → `tests/fixtures/llm/` 이전 + JSON 5필드 schema 교체.
  - [x] 9.5 `test_varco_pipeline.py` → `test_llm_pipeline.py` 신규 작성.
  - [x] 9.6 잔존 키워드 정리 (PIVOT 메모는 의도적으로 보존).

- [x] **Task 10 (AC: #9) — 단위·통합 테스트**
  - [x] 10.1 `test_llm_client.py` 4건 (httpx Response로 RateLimitError 정밀 검증 포함).
  - [x] 10.2 `test_tier_router.py` 11건 (parametrize 9 + multi + fallback).
  - [x] 10.3 `test_cost_cap.py` 4건.
  - [x] 10.4 `test_llm_pipeline.py` 통합 2건 (clean ACK + timeout → DLQ).
  - [x] 10.5 기존 테스트 갱신 (token_bucket / retry_handler / llm_classifier — `openai.APITimeoutError`/`APIConnectionError` retryable + max_attempts override).
  - [x] 10.6 **`pytest detection/tests/` — 48 passed in 7.40s / 외부 네트워크 0건 확인**.

- [x] **Task 11 (AC: #10) — 실사 통합 smoke**
  - [x] 11.1 `detection/scripts/seed_one_post.py` 신규 (외부 Redis 모드 — Docker 띄운 후 사용).
  - [x] 11.2 `infra/.env`의 `OPENAI_API_KEY` 본인 키 확인 (164자 sk-).
  - [x] 11.3 **Docker 미가동 환경 대비** — `detection/scripts/smoke_integration.py` 신규(fakeredis in-memory + 실 OpenAI 호출). production 코드 경로 그대로.
  - [x] 11.4 `python detection/scripts/smoke_integration.py` 1회 실행 — **실 OpenAI gpt-4o 호출 1건 성공**.
  - [x] 11.5 결과: `type=핵_치트 tier=T1 conf=0.950 cost=$0.00197 tokens(in/out)=537/63`, `posts:queue=0 / posts:processing=0 / posts:dlq=0`.
  - [x] 11.6 `docs/integration-smoke-3-3.md` 작성 — 실행 로그 캡처 + 검증된 흐름 + 운영(Docker+실 Redis) 모드 절차.
  - [x] 11.7 OpenAI 비용 ≤ $0.005 — 실측 $0.00197.

## Dev Notes

### 본 스토리의 성공 기준 = AC #10 (실사 smoke)

- 사용자가 강조: "completion이 부족해도 smoke 정도면 OK + 다른 파트와 함께 실사 돌아가는 모습 완성이 본질".
- 단위·통합 테스트 통과만으로는 done 아님 — `python -m detection.src.main`이 떠서 OpenAI 호출 → 결과 로그까지 1회 흘러가야 한다.
- crawler까지 묶은 end-to-end는 본 스토리에서 하지 **않음** — `seed_one_post.py`로 큐만 적재.

### 재사용 부품의 사실상 그대로 유지

- `RetryHandler` — exception whitelist 2종 추가 + 로그 문구만 갱신. 핵심 로직 동일.
- `TokenBucket` — Redis key constant rename만. Lua script 그대로.
- `RetryExhaustedError` — 그대로.
- `QueueConsumer` / `Watchdog` — 변경 0건.
- `correlation_id` 전파 패턴 — 그대로.

### Tier 차등 retry — 현 흐름에서의 실용 절충

- AC #5의 Tier 차등 retry는 이상적으로 "응답 후 tier 확인 → 다음 호출에 그 tier의 attempts 적용". 그러나 OpenAI 단일 호출 모델에서는 응답을 받기 전 tier를 모름.
- 본 스토리는 **default 3회 retry**(env var `RETRY_MAX_ATTEMPTS`)로 통일 + `TIER_RETRY_ATTEMPTS` dict는 코드에 정의만 해두고 사용 부위는 후속(예: Story 3-6 알림 로직에서 T4 재시도 0회 보장)에서 활용.
- 실용 절충에 대한 1-2문장 메모를 `detection/src/retry/retry_handler.py` 상단 docstring에 추가.

### 전수 저장 정책 — 본 스토리에서의 함의

- threshold 미달 + T4 + `is_illegal=false`도 모두 RDS 저장 대상 (Story 3-4).
- 본 스토리에서는 RDS 저장이 없으므로 threshold 분기 미사용 — `tier_config.is_above_threshold()` 함수는 정의만 하고 호출하지 않는다.
- `DetectionPipeline.process()`에서 분류 결과는 무조건 로그 + (Story 3-4 TODO) 저장 호출. 조건 분기 0.

### OpenAI 단가 산출 (cost_cap)

- gpt-4o: input $2.50 / output $10.00 per 1M tokens (`spike_llm.py::PRICING`).
- 이미지 토큰: `detail=auto`(기본)에서 OpenAI가 자동 계산하여 `usage.prompt_tokens`에 합산해 반환. 별도 분리 집계 0(SPIKE에서 확인).
- micro-USD 정수로 INCRBY → Redis 원자성 + float 누적 오차 회피.

### LLMClient 멀티모달 content 구성 패턴

```python
user_content: list[dict] = [{"type": "text", "text": f"게시글:\n{text}"}]
if not LLM_SEND_IMAGES:
    images = []
for img in images:
    if img.startswith("data:") or img.startswith("http"):
        url = img
    else:  # 로컬 경로
        with open(img, "rb") as f:
            url = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
    user_content.append({"type": "image_url", "image_url": {"url": url}})

resp = client.chat.completions.create(
    model=LLM_MODEL,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ],
    response_format={
        "type": "json_schema",
        "json_schema": {"name": "tracker_classification", "strict": True, "schema": CLASSIFICATION_SCHEMA},
    },
)
```

### Story 3-4 / 3-5 / 3-6과의 경계

- **Story 3-4**: RDS `detections` 테이블 저장 + Flyway V5 마이그레이션 + `DetectionResponse.translatedText` API 매핑. 본 스토리에서는 `# TODO(Story 3-4)` 한 줄만 남긴다.
- **Story 3-5**: Tier별 confusion matrix + 라벨셋 ≥300건 측정. 본 스토리에서는 정확도 측정 0.
- **Story 3-6**: T1 알림 + Tier 보존 정책 + 이미지 PII 토글 최종 결정. 본 스토리에서는 `LLM_SEND_IMAGES=false` default만.

### 환경변수 매트릭스 (본 스토리에서 사용·신규)

| 변수 | 기본 | 본 스토리에서의 의미 |
|---|---|---|
| `OPENAI_API_KEY` | placeholder | **본인 키 필수**. AC #10 smoke 차단 요인 |
| `LLM_MODEL` | `gpt-4o` | SPIKE 검증값 |
| `LLM_DAILY_COST_CAP_USD` | `5` | CostCap 활성. 0이면 비활성 |
| `LLM_SEND_IMAGES` | `false` | 본 스토리 default false(이미지 PII 차단). AC #10은 텍스트 only로 smoke |
| `LLM_SPLIT_TEXT_IMAGE` | `false` | 단일 호출 |
| `LLM_WORKER_COUNT` | `1` | 본 스토리는 단일 worker (multi-worker는 Story 3-6 알림 큐와 함께 검토) |
| `LLM_TIMEOUT_SEC` | `30` | SPIKE 검증값 |
| `LLM_MODEL_RELEASE_DATE` | `2024-08-06` | model_version 포맷용 |
| `LLM_RATE_LIMIT_CAPACITY` | `60` | 신규 rename |
| `LLM_RATE_LIMIT_REFILL_PER_SEC` | `1` | 신규 rename |
| `LLM_RATE_LIMIT_MAX_WAIT_SEC` | `120` | 신규 rename |
| `TIER_THRESHOLD_T1` ~ `T4` | 0.65 / 0.75 / 0.85 / 0.90 | tier_config 신규 |
| `RETRY_MAX_ATTEMPTS` | `3` | 기존 유지 |
| `RETRY_BACKOFF_BASE_SEC` | `1` | 기존 유지 |

### 신규 type enum (Story 3-3 schema)

```
핵_치트, 사설서버, 불법프로그램_배포 — T1
계정_거래, 매크로_판매 — T2
리세마라, 현금화, 광고_도배 — T3
기타 — T4
```

- 기존 5종(`핵_배포 / 매크로_판매 / 계정_거래 / 리세마라 / 기타`)에서 9종으로 확장.
- 기존 코드의 `_ALLOWED_TYPES` 검증을 9종으로 갱신.
- SPIKE 라벨셋 v1의 `핵_배포`는 신 enum에서 `핵_치트` 또는 `불법프로그램_배포` (둘 다 T1)로 mapping — Story 3-5에서 라벨셋 v2 작성 시 명확히 분리.

### Project Structure Notes

```
detection/src/
├── main.py                          # Task 8: wiring 갱신
├── config/
│   ├── redis_config.py              # 변경 0
│   └── tier_config.py               # Task 4: 신규
├── consumer/
│   ├── queue_consumer.py            # 변경 0
│   └── watchdog.py                  # 변경 0
├── mocks/
│   ├── varco_mock.py                # Task 9.2: → llm_mock.py rename + 재작성
│   └── llm_mock.py                  # (rename 결과)
├── pipeline/
│   ├── detection_pipeline.py        # Task 7.2: 재작성
│   ├── llm_classifier.py            # Task 7.1: 재작성
│   ├── llm_client.py                # Task 2: 신규
│   ├── tier_router.py               # Task 3: 신규
│   └── varco_client.py              # Task 9.1: 삭제
├── rate_limit/
│   ├── token_bucket.py              # Task 1.2: env var rename
│   └── cost_cap.py                  # Task 5: 신규
└── retry/
    └── retry_handler.py             # Task 6: whitelist 확장
detection/scripts/
├── smoke_openai.py                  # 변경 0 (SPIKE 산출)
├── spike_llm.py                     # 변경 0 (SPIKE 산출)
└── seed_one_post.py                 # Task 11.1: 신규
detection/tests/
├── unit/
│   ├── test_llm_client.py           # Task 10.1: 신규
│   ├── test_tier_router.py          # Task 10.2: 신규
│   ├── test_cost_cap.py             # Task 10.3: 신규
│   ├── test_llm_classifier.py       # Task 10.5: 갱신
│   ├── test_retry_handler.py        # Task 10.5: 갱신
│   ├── test_token_bucket.py         # Task 10.5: 갱신
│   └── test_consumer_idempotency.py # 변경 0
└── integration/
    ├── test_llm_pipeline.py         # Task 10.4: 신규 (test_varco_pipeline.py rename)
    └── (test_varco_pipeline.py 삭제)
shared/
├── interfaces/
│   ├── varco.py                     # Task 9.3: 삭제
│   └── llm.py                       # (rename 결과)
└── config/
    └── redis_config.py              # Task 1.1: constant rename
tests/fixtures/
├── varco/                           # Task 9.4: → llm/ rename
└── llm/                             # (rename 결과)
infra/
└── .env.example                     # Task 1.3 + Task 4 + Task 5: env var 추가
docs/
└── integration-smoke-3-3.md         # Task 11.6: 신규
```

### Testing Standards

- pytest, 외부 네트워크 호출 0건 강제. `MagicMock(openai.OpenAI)` 또는 `respx` 사용.
- `LLMMock` 모드: `clean` / `illegal` / `rate_limited` / `timeout` 4종 (varco_mock의 패턴 유지).
- fixture JSON은 OpenAI 응답 schema(`{type, confidence, reason_ko, translated_text_ko, image_observed}`)로 작성.
- AC #10의 실사 smoke는 pytest 범위 밖. PR description에 캡처/로그 인용.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.3] — L602-630 AC 출처
- [Source: _bmad-output/implementation-artifacts/3-0-spike-openai-멀티모달-poc.md#Story 3-3 본 구현 입력값] — 권장값 표 (gpt-4o, $5 cap, json_schema strict 등)
- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-05-27.md#Section 4.2] — architecture 갱신 매핑
- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-05-27.md#부록 A-2] — 전수 저장 정책 (threshold는 디스플레이 필터만)
- [Source: _bmad-output/planning-artifacts/architecture.md#Cross-Cutting Concerns 14] — L88 결정 사항 (a)~(f)
- [Source: _bmad-output/planning-artifacts/architecture.md#detection 디렉터리 트리] — L577-608
- [Source: _bmad-output/planning-artifacts/architecture.md#파이프라인 도식] — L782-783
- [Source: detection/scripts/spike_llm.py] — `CLASSIFICATION_SCHEMA` / `SYSTEM_PROMPT` / `PRICING` / `NEW_TYPE_TO_TIER` 이식 원본
- [Source: detection/scripts/smoke_openai.py] — OpenAI 호출 패턴 참고
- [Source: detection/src/retry/retry_handler.py] — RetryHandler 재사용 부품
- [Source: detection/src/rate_limit/token_bucket.py] — TokenBucket 재사용 부품
- [Source: detection/src/consumer/queue_consumer.py + watchdog.py] — Story 3-1 (변경 0)
- [Source: shared/models/crawl_event.py] — `event.s3_image_paths` / `event.image_urls` 입력 필드
- [Source: infra/.env.example#LLM API Key] — env var 5종 baseline

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context) — 2026-05-27 단일 세션 dev-story 실행.

### Debug Log References

- `detection/tests/` — 48 passed in 7.40s, 외부 네트워크 0건
- `detection/scripts/smoke_integration.py` — 실 OpenAI gpt-4o 호출 1건, $0.00197/post

### Completion Notes List

- **AC #10 실사 통합 smoke 통과** — 실 OpenAI 호출로 `핵_치트/T1/conf=0.95/$0.00197/537·63 tokens`가 큐 → LLM → ACK까지 1건 흘렀음. `docs/integration-smoke-3-3.md`에 캡처.
- **48 PASS** (Story 3-1 기존 8건 + 본 스토리 신규 ≥10건 + 갱신본 합계). 외부 네트워크/실 Redis 호출 0건.
- **Story 3-2 cleanup 흡수** — `varco_client.py`/`varco_mock.py`/`shared/interfaces/varco.py`/`tests/fixtures/varco/` 일괄 폐기 + `llm_*`로 rename. 잔존 `VARCO` 키워드는 PIVOT 메모 외 0건.
- **재사용 부품 유지** — `RetryHandler` / `TokenBucket` / `RetryExhaustedError` / `QueueConsumer` / `Watchdog`은 변경 최소 (exception whitelist 2종 + max_attempts 인자 + key 상수만).
- **transient 절충** — Tier 차등 retry는 OpenAI 단일 호출에서 응답 전 tier 미상이라 default 3회 적용. `TIER_RETRY_ATTEMPTS`는 `tier_config.py`에 dict로 정의만 + Story 3-6에서 활용 예정.
- **threshold는 디스플레이 필터로만** — `tier_config.is_above_threshold()` 정의만 + `DetectionPipeline`에서는 미사용 (부록 A-2 전수 저장 정책 준수).
- **Docker 미가동 회피책** — `detection/scripts/smoke_integration.py`로 fakeredis in-memory + 실 OpenAI 호출 통합 smoke. 운영(외부 Redis) 모드 절차도 `docs/integration-smoke-3-3.md`에 별도 명시.
- **cost_cap 모델명 추출** — `LLMClassifier.model_version` `openai:{model}:{date}` 형식에서 `model` 부분만 추출하여 `cost_cap.record(..., model=...)`에 전달. PRICING fallback이 gpt-4o라 잘못 추출 시에도 cost는 산출됨.
- **Crawler 회귀 미실행** — detection venv에 `crawl4ai` 미설치라 collection 단계 에러. 본 스토리는 crawler 코드 0 변경, `shared/config/redis_config.py` 상수만 추가했으므로 crawler 의존성 영향 없음.

### File List

**신규 작성:**
- `detection/src/pipeline/llm_client.py` — OpenAI 멀티모달 클라이언트
- `detection/src/pipeline/tier_router.py` — type → Tier 매핑
- `detection/src/config/tier_config.py` — Tier threshold + retry attempts
- `detection/src/rate_limit/cost_cap.py` — 일일 비용 cap
- `detection/src/mocks/llm_mock.py` — 통합 테스트용 mock
- `shared/interfaces/llm.py` — LLMInterface Protocol + LLMResponse + RateLimitError
- `detection/scripts/seed_one_post.py` — 외부 Redis 큐 적재 (운영 모드 smoke용)
- `detection/scripts/smoke_integration.py` — fakeredis + 실 OpenAI 호출 1건 smoke
- `detection/tests/unit/test_llm_client.py` (4건)
- `detection/tests/unit/test_tier_router.py` (11건 — parametrize)
- `detection/tests/unit/test_cost_cap.py` (4건)
- `detection/tests/integration/test_llm_pipeline.py` (2건)
- `tests/fixtures/llm/mock_response_clean.json`
- `tests/fixtures/llm/mock_response_illegal.json`
- `tests/fixtures/llm/mock_response_timeout.json`
- `tests/fixtures/llm/mock_response_rate_limited.json`
- `docs/integration-smoke-3-3.md` — 실사 smoke 결과 + 운영 모드 절차

**수정:**
- `detection/src/main.py` — wiring 전면 갱신
- `detection/src/pipeline/llm_classifier.py` — LLMClient 위임 + 9-type + model_version
- `detection/src/pipeline/detection_pipeline.py` — 새 흐름 (cost_cap + tier_router 통합)
- `detection/src/retry/retry_handler.py` — exception whitelist + max_attempts
- `detection/src/rate_limit/token_bucket.py` — env var rename + 키 상수 갱신
- `detection/tests/unit/test_llm_classifier.py` — 9-type + LLMResponse
- `detection/tests/unit/test_retry_handler.py` — openai 예외 retryable + max_attempts
- `detection/tests/unit/test_token_bucket.py` — 키 상수 갱신
- `shared/config/redis_config.py` — `REDIS_KEY_LLM_RATE_LIMIT_CLASSIFY` 추가
- `infra/.env.example` — `LLM_MODEL_RELEASE_DATE` / `LLM_RATE_LIMIT_*` / `TIER_THRESHOLD_*` 추가
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — 3-3 in-progress → review

**삭제:**
- `detection/src/pipeline/varco_client.py`
- `detection/src/mocks/varco_mock.py`
- `shared/interfaces/varco.py`
- `tests/fixtures/varco/` (디렉토리 + 4 JSON 파일)

### Change Log

| 일자 | 변경 | 비고 |
|---|---|---|
| 2026-05-27 | Story 3-3 dev 완료 (review로 이동) | 48 PASS / 실사 smoke 통과 / Story 3-2 cleanup 흡수 |
