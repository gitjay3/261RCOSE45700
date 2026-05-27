# Story 3-4 실사 통합 smoke

**일자**: 2026-05-27
**Story**: 3-4 Detection 결과 RDS 저장 (sources + posts + detections 1 트랜잭션)

## 실행 결과 (실 OpenAI gpt-4o 호출 + 실 PostgreSQL)

```
$ python detection/scripts/smoke_integration_db.py
[INFO] model=gpt-4o
[INFO] OpenAI key=...BGQA (length=164)
[INFO] DB=localhost:5432/tracker
[INFO] 큐 적재 완료: posts:queue len=1
{... cost recorded — model=gpt-4o cost=$0.00212 cumulative=$0.0021}
{... detection saved — id=2 post_id=smoke_3_4_20260527_092335 tier=T1}
{... classification — type=핵_치트 tier=T1 conf=0.980 cost=$0.00212 tokens(in/out)=537/78 image_observed=False}
{... 메시지 처리 완료}

=== Redis ===
  posts:queue       : 0 (0이어야 함)
  posts:processing  : 0 (0이어야 함)
  posts:dlq         : 0 (0이어야 함)

=== PostgreSQL ===
  sources         : ('smoke_source',)
  posts           : id=2, body=리니지M 월핵 최신 버전 팝니다. 탐지 안 됨. 텔레그램 @smoke_t..., lang=ko
  detections      : id=2
    - type        : 핵_치트
    - tier        : T1
    - confidence  : 0.980
    - is_illegal  : True
    - cost_usd    : $0.00212
    - model       : openai:gpt-4o:2026-05-27

[DONE] Story 3-4 실사 통합 smoke 통과 — 1건이 큐 → OpenAI → PostgreSQL까지 흘렀습니다.
```

## 검증된 흐름

| 단계 | 결과 |
|---|---|
| 큐 적재 (`posts:queue` LPUSH) | OK |
| `QueueConsumer.run_once` → BRPOPLPUSH | OK |
| `CostCap.check_and_hold` | OK |
| `LLMClient.classify` (실 OpenAI gpt-4o) | OK (537 in / 78 out tokens) |
| `TierRouter.route` → T1 | OK |
| `CostCap.record` → $0.00212 누적 | OK |
| **`DetectionRepository.save` (Story 3-4 신규)** | OK |
| → `sources` UPSERT (`smoke_source`) | id=1 신규 생성 |
| → `posts` UPSERT (source_id, post_id_at_source) | id=2 신규 생성 |
| → `detections` INSERT (post_id, model_version) | id=2 신규 생성 |
| `LREM` (ACK) | OK |
| DLQ 미사용 | OK |

3회 누적 실행 결과(직전 검증):
```
 id |  type   | tier | confidence | cost_usd |          detected_at
----+---------+------+------------+----------+-------------------------------
  1 | 핵_치트 | T1   |       0.95 |  0.00197 | 2026-05-27 08:07:28.838237+00
  2 | 핵_치트 | T1   |       0.95 |  0.00205 | 2026-05-27 08:08:20.704413+00
  3 | 핵_치트 | T1   |       0.95 |  0.00222 | 2026-05-27 08:12:07.591752+00
```
→ 매 실행마다 DB에 새 row 영속 누적, 각 호출의 비용/토큰이 정확히 기록됨.

## 통합 테스트 결과

```
54 passed in 7.71s
- detection/tests/integration/test_detection_repository.py (5건, 실 PG):
  · test_save_creates_sources_posts_detections — 3 테이블 row 생성 + 모든 컬럼 검증
  · test_save_t4_marks_is_illegal_false — T4 → is_illegal=false
  · test_save_is_idempotent_on_same_model_version — 동일 model_version 멱등성
  · test_save_different_model_version_allowed — 다른 model_version 둘 다 INSERT
  · test_save_translated_text_persisted — zh-CN 본문의 한국어 번역 저장
- detection/tests/integration/test_llm_pipeline.py (3건):
  · test_clean_path_acks_without_dlq (Story 3-3)
  · test_timeout_path_routes_to_dlq (Story 3-3)
  · test_pipeline_calls_repository_save_on_success — pipeline → save 호출 검증
- Story 3-3 기존 단위 테스트: 46 passed (변경 없음)
```

## DB 스키마 확장 (Flyway V5)

```sql
ALTER TABLE sources ADD CONSTRAINT sources_site_name_unique UNIQUE (site_name);
ALTER TABLE sources ALTER COLUMN base_url DROP NOT NULL;
ALTER TABLE posts ALTER COLUMN post_url DROP NOT NULL;
ALTER TABLE detections
    ADD COLUMN tier             VARCHAR(2) NOT NULL DEFAULT 'T4'
        CHECK (tier IN ('T1','T2','T3','T4')),
    ADD COLUMN image_observed   BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN token_usage_json JSONB,
    ADD COLUMN cost_usd         NUMERIC(8, 5);
DROP INDEX IF EXISTS idx_detections_filter;
CREATE INDEX idx_detections_filter
    ON detections (detected_at DESC, tier, type, confidence DESC);
```

V4의 `translated_text TEXT` 컬럼은 그대로 재사용 (LLMResponse.translated_text_ko 값 매핑).

## 본 smoke의 의미

- production 코드 경로 그대로 사용 (`detection/src/main.py`와 동일 wiring).
- Redis만 `fakeredis` in-memory로 치환, **PostgreSQL은 실제 컨테이너 + 실 OpenAI 호출**.
- crawler → 큐 → AI → DB까지 전 구간이 1건 흘러서 Spring API + React 대시보드가 진짜 데이터를 조회할 수 있는 상태가 됨.
- AI 결과가 로그에서 사라지지 않고 RDS에 영속됨 → 대시보드는 이제 mock에서 벗어남.

## 운영 모드 절차

```bash
# 1. Redis + PostgreSQL 띄우기
docker compose -f infra/docker-compose.yml --env-file infra/.env up -d redis postgres

# 2. Flyway 적용 — api/ Spring boot 띄울 때 V1-V5 자동 적용
# (dev에서는 detection/scripts/smoke_integration_db.py 실행 전에 미리 적용)

# 3. infra/.env 확인
grep "^OPENAI_API_KEY=" infra/.env
grep "^DB_PASSWORD=" infra/.env

# 4. crawler 1건 적재 (또는 seed_one_post.py)
python detection/scripts/seed_one_post.py --text "리니지M 월핵 팝니다"

# 5. detection main 실행 — Ctrl+C로 종료
SERVICE_NAME=detection python -m detection.src.main

# 6. PostgreSQL에서 확인
docker exec -it tracker-postgres psql -U tracker_user -d tracker -c \
  "SELECT id, type, tier, confidence FROM detections ORDER BY id DESC LIMIT 5;"
```

다음(Story 3-5/3-6) 없이도 운영자가 PostgreSQL을 직접 조회하면 결과를 볼 수 있다. Spring API + React 대시보드는 별도 트랙(Epic 4 done)에서 이미 구현됨 — DB만 채우면 대시보드에 자동 반영.

## 주의

- `infra/.env`의 `SERVICE_NAME`이 `crawler`로 박혀있어 로그 필드가 `"service": "crawler"`로 표시됨. detection을 운영 모드로 띄울 때는 `SERVICE_NAME=detection` 환경변수 override 필요 (위 명령어 참조).
- 본 smoke는 본인 OpenAI API 키 사용 — 매 실행마다 ~$0.002/post 비용 발생. 본인 부담.
