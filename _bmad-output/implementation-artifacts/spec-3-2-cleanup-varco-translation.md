---
title: 'Story 3-2 cleanup — VARCO Translation 코드 폐기'
type: 'chore'
created: '2026-05-27'
status: 'done'
baseline_commit: '21b56ae09b74104652f529c107f9f5a990597f06'
context:
  - _bmad-output/planning-artifacts/sprint-change-proposal-2026-05-27.md
  - _bmad-output/planning-artifacts/epics.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Sprint Change Proposal 2026-05-27로 FR11(VARCO Translation)이 폐기되고 Story 3-2 status가 `deprecated`로 표시됐다. `feat/epic3-detection` 브랜치에는 review 상태의 VARCO Translation 구현 코드가 남아있어, 다음 Story 3-3 재작성에 앞서 정리가 필요하다.

**Approach:** Translator 클래스·관련 테스트·import·Redis 키 상수·Protocol 메서드를 삭제하되, 재사용 부품(TokenBucket / RetryHandler / correlation_id 전파 / VarcoMock의 classify 경로 / LLMClassifier)은 그대로 보존하여 Story 3-3에서 흡수·재작성할 수 있도록 한다. 본 cleanup 후 pipeline은 한국어 raw_text를 classifier에 직접 전달하는 interim 상태가 되며, Story 3-3에서 OpenAI 멀티모달 호출로 전면 교체된다.

## Boundaries & Constraints

**Always:**
- `feat/epic3-detection` 브랜치에서 작업한다. main으로의 머지·rebase 금지.
- 재사용 부품(`detection/src/rate_limit/token_bucket.py`, `detection/src/retry/retry_handler.py`, `correlation_id` 전파 패턴, `LLMClassifier` 본체, `VarcoMock.classify`)은 한 줄도 변경하지 않는다.
- `detection/tests/unit/` 회귀는 cleanup 후에도 PASS여야 한다 (translate 관련 5건 제외).
- 모든 import 해결 가능해야 한다 (`python -c "from detection.src.main import main"` 성공).

**Ask First:**
- `detection/tests/integration/test_varco_pipeline.py` 통째 삭제 결정 — Translator 의존성을 빼면 통합 테스트로서의 가치가 사라지며 Story 3-3에서 `test_llm_pipeline.py`로 대체될 예정. 본 spec에서는 삭제 전제.

**Never:**
- `varco_client.py::classify`, `llm_classifier.py`, `mocks/varco_mock.py`를 본 cleanup에서 변경하지 않는다. Story 3-3 범위.
- `REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY` 상수 삭제 금지. Story 3-3에서 `LLM_RATE_LIMIT` 으로 rename.
- 신규 OpenAI 코드 작성 금지. 본 PR은 deletion-only chore.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| pytest detection/tests/unit/ | cleanup 후 working tree | translate 테스트 5건 제외하고 모두 PASS | N/A |
| `python -m detection.src.main` import | cleanup 후 | ImportError 없음 (실행은 Redis 부재로 실패해도 무방) | N/A |
| DetectionPipeline.process(message) | 한국어 raw_text가 담긴 CrawlEvent | classifier가 raw_text를 직접 받아 classify 호출 | retry_handler가 처리 |
| DetectionPipeline.process(message) | zh-CN/zh-TW raw_text | classifier가 중국어 raw_text 그대로 받음 (interim 동작 — Story 3-3에서 OpenAI native 다국어 처리로 해결) | TODO 주석으로 명시 |

</frozen-after-approval>

## Code Map

- `detection/src/pipeline/translate.py` — **삭제 대상**. Translator 클래스 본체.
- `detection/tests/unit/test_translate.py` — **삭제 대상**. Translator unit 5건.
- `detection/tests/integration/test_varco_pipeline.py` — **삭제 대상**. Translator+LLMClassifier 통합 테스트, Story 3-3에서 `test_llm_pipeline.py`로 대체 예정.
- `detection/src/pipeline/detection_pipeline.py` — **수정**. Translator 의존성 제거, classifier에 `event.raw_text` 직접 전달, Story 3-3 인용 TODO 주석 추가.
- `detection/src/pipeline/varco_client.py` — **수정**. `.translate()` 메서드만 삭제. `.classify()` 보존. 모듈 docstring에 Story 3-3 rewrite 예고 추가.
- `detection/src/main.py` — **수정**. Translator import + instantiation + TRANSLATE bucket import 제거. classifier wiring은 그대로.
- `shared/interfaces/varco.py` — **수정**. Protocol에서 `translate()` 메서드만 삭제. `ClassificationResult` + `classify()` 보존.
- `shared/config/redis_config.py` — **수정**. `REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE` 상수 삭제. `REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY` 보존.

## Tasks & Acceptance

**Execution:**
- [x] `detection/src/pipeline/translate.py` -- 파일 삭제 -- FR11 폐기로 Translator 클래스 불필요
- [x] `detection/tests/unit/test_translate.py` -- 파일 삭제 -- Translator 단위 테스트 5건 폐기
- [x] `detection/tests/integration/test_varco_pipeline.py` -- 파일 삭제 -- Story 3-3 `test_llm_pipeline.py`로 대체 예정
- [x] `detection/src/pipeline/detection_pipeline.py` -- Translator 파라미터 제거 + process()에서 `translated = self._translator.translate_event(event)` 라인 삭제 + classifier 호출을 `self._classifier.classify(event.raw_text)`로 변경 + Story 3-3 TODO 주석 -- pipeline 구동 유지
- [x] `detection/src/pipeline/varco_client.py` -- `.translate()` 메서드 + `_TRANSLATE_TIMEOUT_SEC` 환경변수 사용처 삭제 + 파일 상단 docstring에 "Story 3-3에서 llm_client.py로 대체 예정" 명시 -- classify 경로 보존
- [x] `detection/src/main.py` -- `from detection.src.pipeline.translate import Translator` 삭제 + `REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE` import 삭제 + `translate_bucket` + `translator = Translator(...)` 인스턴스화 삭제 + `DetectionPipeline(translator, classifier, retry_handler)` 호출을 `DetectionPipeline(classifier, retry_handler)`로 변경 -- main entry point 동작 유지
- [x] `shared/interfaces/varco.py` -- Protocol에서 `translate(self, text: str) -> str` 메서드 + 해당 docstring 제거 -- 계약 정합성
- [x] `shared/config/redis_config.py` -- `REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE: str = "varco:rate_limit:translate"` 라인 삭제 -- 미사용 상수 정리
- [x] (구현 중 발견 — Spec Change Log 참조) `detection/src/rate_limit/token_bucket.py` -- default `key` 인자를 `REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE` → `REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY`로 변경 -- 상수 제거의 필연적 영향
- [x] (구현 중 발견 — Spec Change Log 참조) `detection/tests/unit/test_token_bucket.py` -- 동일 상수 참조 갱신 -- 테스트 정합성

**Acceptance Criteria:**
- Given cleanup 완료, when `cd /Users/erdembileg/Desktop/SW/261R0136COSE45700 && .venv/bin/pytest detection/tests/unit/ -x` 실행, then translate 테스트 5건 제외하고 모두 PASS (exit 0)
- Given cleanup 완료, when `.venv/bin/python -c "from detection.src.main import main; print('ok')"` 실행, then `ok` 출력 (ImportError 없음)
- Given cleanup 완료, when `grep -rn "Translator\|translate_event\|REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE" detection/src/ shared/` 실행, then 0 결과 (잔존 참조 없음)
- Given cleanup 완료, when `git diff --stat`, then 3개 파일 삭제 + 7개 파일 수정 (재사용 부품 본체 무변경; token_bucket.py default 상수 1줄 + test_token_bucket.py 참조 갱신은 Spec Change Log 참조)

## Spec Change Log

### 2026-05-27 step-03 implementation finding — token_bucket.py 영향 확장

- **Finding**: `detection/src/rate_limit/token_bucket.py:8, :61`가 삭제 대상 상수 `REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE`를 import + default 인자로 사용 중. spec의 "재사용 부품 한 줄도 변경 안 함" 경계와 충돌.
- **Amendment**: token_bucket.py의 default `key` 인자를 `REDIS_KEY_VARCO_RATE_LIMIT_CLASSIFY`로 변경 (1 line + 1 import line). `test_token_bucket.py`도 동일 참조 갱신 (5개소, replace_all).
- **Avoids**: ImportError로 unit 테스트 collection 단계 전체 실패. 본 cleanup PR이 회귀 가능한 상태가 됨.
- **KEEP**: token_bucket의 동작·시그니처·테스트 의도 모두 무변경. 단지 기본 키 이름만 deprecated → still-active 상수로 교체. 의미상 동등 (사용자는 main.py에서 명시적으로 key를 전달하므로 default는 fixture에서만 사용).
- **최종 git diff**: 3 deletions + 7 modifications (spec 예상 5 + collateral 2).

## Verification

**Commands:**
- `.venv/bin/pytest detection/tests/unit/ -x` -- expected: 모든 테스트 PASS (translate 5건 제외)
- `.venv/bin/python -c "from detection.src.main import main"` -- expected: stdout `ok` 또는 silent exit 0
- `grep -rn "Translator\|translate_event\|REDIS_KEY_VARCO_RATE_LIMIT_TRANSLATE" detection/src/ shared/` -- expected: 0 results
- `grep -rn "from detection.src.pipeline.translate" .` -- expected: 0 results (테스트 파일까지 정리됐는지)
- `git diff --stat` -- expected: 3 deletions + 5 modifications

**Manual checks (if no CLI):**
- `detection/src/pipeline/varco_client.py`에 Story 3-3 rewrite 예고 docstring이 추가됐는지 시각 확인
- `detection_pipeline.py::process()` 메서드의 Story 3-3 TODO 주석이 OpenAI 멀티모달 호출 + Tier 라우팅을 명시하는지 확인

## Suggested Review Order

**Pipeline 재배선 (Entry point)**

- main()에서 Translator 인스턴스화 사라지고 DetectionPipeline이 2-arg 호출로 간소화됨 — 가장 먼저 봐야 할 design intent.
  [`main.py:19`](../../detection/src/main.py#L19)

- process()에서 translate_event() 한 단계가 제거되고 classifier가 raw_text를 직접 받는다 — interim 상태 TODO 명시.
  [`detection_pipeline.py:23`](../../detection/src/pipeline/detection_pipeline.py#L23)

**Interface 계약 축소**

- VarcoInterface Protocol에서 translate() 메서드가 사라진 자리 — classify-only 계약으로 좁아짐.
  [`shared/interfaces/varco.py:15`](../../shared/interfaces/varco.py#L15)

- VarcoHttpClient docstring에 Story 3-3 대체 예고 + translate() 메서드 본체 삭제 확인.
  [`varco_client.py:1`](../../detection/src/pipeline/varco_client.py#L1)

- `varco:rate_limit:translate` 상수 deletion — 그 외 상수는 보존.
  [`shared/config/redis_config.py:12`](../../shared/config/redis_config.py#L12)

**재사용 부품 보존 + 필연적 영향 (Spec Change Log 참조)**

- TokenBucket default `key` 인자가 deprecated TRANSLATE → still-active CLASSIFY로 변경 — 동작 무변경, 키 이름만.
  [`token_bucket.py:61`](../../detection/src/rate_limit/token_bucket.py#L61)

- test_token_bucket에서 동일 상수 참조 5개소 일괄 갱신.
  [`test_token_bucket.py:12`](../../detection/tests/unit/test_token_bucket.py#L12)

**Deletions**

- Translator 본체 (46 lines) — Sprint Change Proposal FR11 폐기 결과.
  [`translate.py (deleted)`](../../detection/src/pipeline/translate.py)

- Translator unit 5건 — 5 테스트 폐기.
  [`test_translate.py (deleted)`](../../detection/tests/unit/test_translate.py)

- 통합 테스트 — Story 3-3에서 test_llm_pipeline.py로 대체 예정.
  [`test_varco_pipeline.py (deleted)`](../../detection/tests/integration/test_varco_pipeline.py)

**문서 patch (review 피드백 반영)**

- detection/.env.example의 잘못된 "Deprecated" 헤더 — 일부는 여전히 활성. Transitional 섹션으로 분리.
  [`detection/.env.example:21`](../../detection/.env.example#L21)
