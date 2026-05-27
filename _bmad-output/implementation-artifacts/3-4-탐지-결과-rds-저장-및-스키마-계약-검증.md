# Story 3.4: 탐지 결과 RDS 저장 및 스키마 계약 검증

Status: review

> **본 스토리 핵심:** Story 3-3에서 분류 결과를 로그만 찍던 흐름을 RDS PostgreSQL에 영속 저장으로 확장. `DetectionRepository`가 `sources` UPSERT + `posts` UPSERT + `detections` INSERT 셋을 **1 트랜잭션**으로 처리하여 부분 실패 없이 멱등(`(post_id, model_version)` unique)을 보장한다. Spring API + React 대시보드(Epic 4 done)가 본 스토리 적용 직후 PostgreSQL을 조회해서 실제 탐지 데이터를 표시할 수 있다.
>
> **이 스토리에서 하지 않는 것:** crawler 측 `posts` 직접 INSERT (Epic 2 안 건드림), Tier별 정확도 측정(Story 3-5), Tier별 알림·보존(Story 3-6), threshold 기반 분기(부록 A-2 전수 저장 정책 — threshold는 대시보드 디스플레이 필터로만).
>
> **[전제 조건]** Story 3-3 review/done — OpenAI 멀티모달 분류 + Tier 라우팅 + CostCap 부품 보유. Story 3-1 done(Redis 큐 소비자 + Watchdog). `infra/.env`에 `DB_PASSWORD` 본인 값. `docker compose up -d postgres redis`로 컨테이너 가동. Flyway V1~V4 적용된 상태(또는 본 V5와 함께 처음부터).
>
> **[설계 결정 — 누가 `posts` row를 INSERT하나]**
> Detection이 `posts` UPSERT까지 담당하는 **B안** 채택 (Story 3-3 dev 대화 합의):
> - crawler 무변경 (Epic 2 done, PIVOT 후 142 PASS 회귀 위험 회피)
> - Spring API 신규 endpoint 없음 (HTTP 1홉 회피, 인증 설계 비용 0)
> - PostgreSQL `ON CONFLICT ... DO UPDATE RETURNING id` 한 트랜잭션으로 깔끔
> - 향후 Story 3-6 알림 발송도 같은 트랜잭션 직후에 Redis pub/sub 한 줄로 자연스럽게 확장 가능

## Story

개발자로서,
OpenAI 멀티모달 LLM이 분류한 탐지 결과가 RDS `detections` 테이블에 Tier 정보 + 비용 + 토큰 사용량과 함께 저장되고, 같은 게시글 재처리 시 중복 삽입이 방지되기를 원한다,
그래서 Spring API + 대시보드가 실 데이터를 조회·표시할 수 있고 운영자가 Tier별 필터·통계·보존 정책을 적용할 수 있다.

## Acceptance Criteria

1. **Given** Flyway V1~V4가 적용된 RDS PostgreSQL이 있을 때
   **When** 본 스토리의 `V5__add_tier_and_relax_post_url.sql` 마이그레이션이 적용되면
   **Then** 다음 5개 스키마 변경이 수행된다:
   - `sources` 테이블에 `UNIQUE (site_name)` 제약 추가 (detection이 ON CONFLICT UPSERT 하기 위함)
   - `sources.base_url` `NOT NULL` 제약 제거 (CrawlEvent에 base_url이 없음)
   - `posts.post_url` `NOT NULL` 제약 제거 (동일 사유)
   - `detections`에 4개 컬럼 추가:
     - `tier VARCHAR(2) NOT NULL DEFAULT 'T4' CHECK (tier IN ('T1','T2','T3','T4'))`
     - `image_observed BOOLEAN NOT NULL DEFAULT FALSE`
     - `token_usage_json JSONB`
     - `cost_usd NUMERIC(8, 5)`
   - `idx_detections_filter` 인덱스 재생성: `(detected_at DESC, tier, type, confidence DESC)` — Tier 필터 우선
   **And** V4의 `translated_text TEXT` 컬럼은 그대로 재사용(`LLMResponse.translated_text_ko` 값 매핑).

2. **Given** `DetectionRepository`가 `CrawlEvent` + `LLMResponse` + `tier` + `model_version`을 받을 때
   **When** `repository.save(event, response, tier, model_version)`가 호출되면
   **Then** `detection/src/repository/detection_repository.py`의 `DetectionRepository`가 다음 **3단계를 1 트랜잭션 안에서** 수행한다:
   - **1단계** — `sources` UPSERT: `INSERT INTO sources (site_name, board_name) VALUES (event.source_id, event.site_name) ON CONFLICT (site_name) DO UPDATE SET board_name = COALESCE(sources.board_name, EXCLUDED.board_name) RETURNING id`
   - **2단계** — `posts` UPSERT: `INSERT INTO posts (source_id, post_id_at_source, body, language, crawled_at) VALUES (...) ON CONFLICT (source_id, post_id_at_source) DO UPDATE SET body = EXCLUDED.body, language = EXCLUDED.language RETURNING id`
   - **3단계** — `detections` INSERT: `INSERT INTO detections (post_id, is_illegal, type, tier, confidence, reason, translated_text, image_observed, token_usage_json::jsonb, cost_usd, model_version, detected_at) VALUES (...) ON CONFLICT (post_id, model_version) DO NOTHING RETURNING id`
   **And** psycopg3 `with pool.connection() as conn` 패턴으로 자동 commit/rollback (어느 단계든 실패 시 전체 롤백).
   **And** 모든 쿼리는 parameterized (`%s`) — SQL injection 0.
   **And** 반환값은 `detections.id` (신규 INSERT) 또는 `None` (멱등 conflict).

3. **Given** 동일 `(post_id, model_version)` 조합으로 2회 `save` 호출 시
   **When** 두 번째 호출이 발생하면
   **Then** V3의 unique constraint `(post_id, model_version)`이 ON CONFLICT DO NOTHING으로 무시되어 두 번째 호출은 **`None` 반환** (raise 없음).
   **And** `detections` 테이블의 row 개수는 1 (멱등성 보장).
   **And** 로그에 `"detection 멱등 skip — 이미 저장됨"` INFO 출력.

4. **Given** `tier`가 `T4`(=`기타`/clean)일 때
   **When** `repository.save`가 호출되면
   **Then** `detections.is_illegal = false`로 저장된다 (사업 정의: T4=정상 / T1~T3=위반).
   **And** `tier`가 T1/T2/T3이면 `is_illegal = true`.

5. **Given** `LLMResponse.translated_text_ko`에 한국어 번역이 들어있을 때
   **When** `repository.save`가 호출되면
   **Then** `detections.translated_text` 컬럼(V4)에 그대로 저장된다.
   **And** 한국어 원문이면 `LLMResponse.translated_text_ko = None` → `detections.translated_text = NULL`.
   **And** Spring API의 `DetectionResponse.translatedText` 필드가 이 컬럼을 직접 매핑 (Story 4.2 계약과 정합).

6. **Given** `DetectionPipeline`이 `repository`를 의존성 주입받을 때
   **When** `process(message)`가 분류 성공 후 흐름을 진행하면
   **Then** `cost_cap.record()` 직후, 로그 출력 **직전**에 `repository.save(event, response, tier, model_version)` 한 줄이 호출된다.
   **And** RDS 저장 실패(`psycopg.Error`)는 retryable로 catch하지 않고 호출자(`QueueConsumer`)에 propagate → `posts:processing` 잔류 → Watchdog이 재투입.
   **And** `repository = None`이면 save를 skip (테스트 편의 — 운영 wiring에서는 항상 inject).

7. **Given** PostgreSQL connection pool이 필요할 때
   **When** `detection/src/config/db_config.py::get_pool()`가 호출되면
   **Then** `psycopg.conninfo.make_conninfo()`로 conninfo 문자열을 안전하게 구성한다 (password 특수문자 escape).
   **And** `min_size=1, max_size=5` 기본 (env override 가능: `DB_POOL_MIN_SIZE`, `DB_POOL_MAX_SIZE`).
   **And** `DB_PASSWORD` 미설정 시 `RuntimeError("DB_PASSWORD 환경변수 미설정")` 명시적 차단.
   **And** `close_pool()`은 테스트/종료 시 명시적 호출 — finalizer 경고 회피.

8. **Given** `detection/tests/`에 통합 테스트가 있을 때
   **When** `pytest detection/tests/`를 실행하면
   **Then** 다음 ≥ 6개 신규 통합 테스트가 모두 PASS하며 **실 PostgreSQL 사용** (`requires_pg` decorator로 PG 미가동 시 자동 skip):
   - `test_save_creates_sources_posts_detections`: 3개 테이블에 row 생성 검증 + 모든 컬럼 값 검증
   - `test_save_t4_marks_is_illegal_false`: T4 → is_illegal=false
   - `test_save_is_idempotent_on_same_model_version`: 동일 model_version 2회 호출 → 두 번째 None
   - `test_save_different_model_version_allowed`: 다른 model_version → 둘 다 INSERT 성공
   - `test_save_translated_text_persisted`: zh-CN 원문의 한국어 번역 저장 검증
   - `test_pipeline_calls_repository_save_on_success`: pipeline이 정확한 인자로 save 호출
   **And** `detection/tests/conftest.py`의 `clean_db` fixture가 각 테스트 시작 시 `TRUNCATE detections, post_images, posts, sources RESTART IDENTITY CASCADE`로 격리.
   **And** Story 3-3 기존 48 PASS + 신규 ≥6 = **누적 ≥ 54 PASS** / 외부 OpenAI 호출 0건 (LLMMock + fakeredis 사용).

9. **Given** 운영 코드 경로 전체가 RDS까지 흘러야 할 때
   **When** dev가 **실사 통합 smoke**(`detection/scripts/smoke_integration_db.py`)를 실행하면
   1. fakeredis(in-memory) + 실 PostgreSQL 컨테이너 + **실 OpenAI gpt-4o 호출**
   2. `CrawlEvent` 1건을 큐에 LPUSH → `QueueConsumer.run_once`로 소비 → OpenAI 호출 → `repository.save` → ACK
   3. PostgreSQL에서 `sources` / `posts` / `detections` 3개 테이블에 row 들어갔는지 직접 SELECT로 확인
   **Then** 로그에 `"detection saved — id=N post_id=... tier=T1"` 한 줄 출력.
   **And** `posts:queue`/`posts:processing`/`posts:dlq` 모두 0건 (clean ACK).
   **And** `docs/integration-smoke-3-4.md`에 캡처. **이 AC가 본 스토리의 "성공" 그 자체**.
   **And** 운영 모드(Docker + 실 Redis) 절차도 함께 문서화.

10. **Given** 시크릿 검사 시
    **When** 코드베이스에 `OPENAI_API_KEY` / `DB_PASSWORD` 등 비밀값이 직접 들어가 있는지 grep하면
    **Then** **0건** 검출.
    **And** `infra/.env`는 `.gitignore`에 등록되어 git 추적 0.
    **And** 모든 설정은 `os.environ.get(...)` 패턴 + `infra/.env.example` placeholder.

> **AC 출처:** epics.md L631-650 Story 3.4 + Sprint Change Proposal 2026-05-27 §Section 4.2(스키마 갱신). 부록 A-2 전수 저장 정책(threshold = 디스플레이 필터). Story 3-3 본 구현(LLMResponse / TierRouter / CostCap)과의 인터페이스 계약. AC #9 실사 smoke는 사용자 결정(2026-05-27 dev 대화): "작동하는 모습 우선, 다른 파트와 함께 실사 돌아가는 모습 완성"이 본질 — 단위 테스트 통과만으로는 done 아님.

## Tasks / Subtasks

- [x] **Task 1 (AC: #1) — Flyway V5 마이그레이션 작성**
  - [x] 1.1 `api/src/main/resources/db/migration/V5__add_tier_and_relax_post_url.sql` 신규
  - [x] 1.2 `sources(site_name)` UNIQUE 추가
  - [x] 1.3 `sources.base_url` / `posts.post_url` NULLABLE
  - [x] 1.4 `detections`에 `tier` / `image_observed` / `token_usage_json` / `cost_usd` 컬럼 추가
  - [x] 1.5 `idx_detections_filter` 재생성 — tier 정렬 키 우선
  - [x] 1.6 로컬 PostgreSQL 컨테이너에 V1~V5 적용 검증

- [x] **Task 2 (AC: #7) — `db_config.py` 신규 작성**
  - [x] 2.1 `detection/src/config/db_config.py` 신규
  - [x] 2.2 `psycopg.conninfo.make_conninfo()` 사용 — password 특수문자 escape 안전
  - [x] 2.3 lazy global `ConnectionPool`, `min_size`/`max_size` env override
  - [x] 2.4 `DB_PASSWORD` 미설정 시 RuntimeError 명시적 차단
  - [x] 2.5 `close_pool()` 헬퍼 — 테스트/종료 finalizer 경고 회피

- [x] **Task 3 (AC: #2, #3, #4, #5) — `DetectionRepository` 신규 작성**
  - [x] 3.1 `detection/src/repository/__init__.py` + `detection_repository.py` 신규
  - [x] 3.2 `save(event, response, tier, model_version) -> int | None` 단일 public 메서드 (write 전용)
  - [x] 3.3 `with pool.connection()` 트랜잭션 — sources UPSERT → posts UPSERT → detections INSERT
  - [x] 3.4 `_parse_crawled_at`: ISO 8601 + 'Z' 접미사 지원, fallback `datetime.now(utc)`
  - [x] 3.5 `is_illegal = tier != "T4"` (T4 정상, T1-T3 위반)
  - [x] 3.6 `token_usage_json`: `json.dumps()` + `%s::jsonb` cast
  - [x] 3.7 ON CONFLICT DO NOTHING RETURNING id — 멱등 시 None 반환

- [x] **Task 4 (AC: #6) — `DetectionPipeline` 갱신**
  - [x] 4.1 `__init__`에 `repository: DetectionRepository | None = None` 추가
  - [x] 4.2 `process()` 흐름: cost_cap.record → repository.save (있으면) → 로그
  - [x] 4.3 `repository=None`이면 save skip (테스트 편의)

- [x] **Task 5 — `main.py` wiring 갱신**
  - [x] 5.1 `get_pool()` import + `DetectionRepository(db_pool)` 생성
  - [x] 5.2 `DetectionPipeline(classifier, tier_router, cost_cap, retry_handler, repository=repository)`

- [x] **Task 6 — 의존성 추가**
  - [x] 6.1 `detection/requirements.txt`: `psycopg[binary,pool]>=3.2.0`
  - [x] 6.2 detection venv에 install

- [x] **Task 7 (AC: #8) — 통합 테스트 작성**
  - [x] 7.1 `detection/tests/conftest.py` 신규 — `db_pool` session fixture + `clean_db` (TRUNCATE) + `requires_pg` skip decorator
  - [x] 7.2 `detection/tests/integration/test_detection_repository.py` 5건 (3 테이블 생성 / T4 / 멱등 / 다중모델 / 번역)
  - [x] 7.3 `detection/tests/integration/test_llm_pipeline.py`에 `test_pipeline_calls_repository_save_on_success` 추가 (1건)
  - [x] 7.4 `pytest detection/tests/ -q` 누적 **54 PASS / 7.71s / 외부 OpenAI 호출 0**

- [x] **Task 8 (AC: #9) — 실사 통합 smoke + 문서화**
  - [x] 8.1 `detection/scripts/smoke_integration_db.py` 신규 — fakeredis + 실 PG + 실 OpenAI
  - [x] 8.2 try/finally로 `close_pool()` 호출 — finalizer 경고 회피
  - [x] 8.3 실행 후 PostgreSQL에서 `sources` / `posts` / `detections` SELECT로 검증
  - [x] 8.4 `docs/integration-smoke-3-4.md` 작성 — 실행 로그 캡처 + 흐름 검증 표 + 운영 모드 절차
  - [x] 8.5 3회 실행 누적 검증: detection id 1 → 2 → 3 → ... DB에 영속 누적 확인

- [x] **Task 9 (AC: #10) — 시크릿 검사**
  - [x] 9.1 grep으로 `sk-`/하드코드 password 검색 → **0건**
  - [x] 9.2 `git ls-files infra/`에 `.env` 없음 확인
  - [x] 9.3 모든 설정 `os.environ.get(...)` 패턴 확인
  - [x] 9.4 `infra/.env.example` placeholder 유지

- [x] **Task 10 — 코드 자체 검토**
  - [x] 10.1 `psycopg.conninfo.make_conninfo` 사용 (평문 conninfo 조합 회피)
  - [x] 10.2 V5 SQL 주석 번호 정정 (1→2→3→4→5)
  - [x] 10.3 smoke pool close — try/finally 추가
  - [x] 10.4 회귀 테스트 54 PASS + 실사 smoke 재확인

## Dev Notes

### 본 스토리의 성공 기준 = AC #9 (실사 통합 smoke)

- 사용자 결정 (2026-05-27 dev 대화): "작동하는 모습 우선 — 다른 파트와 함께 실사 돌아가는 모습 완성이 본질".
- 단위 테스트 통과만으로는 done 아님. `smoke_integration_db.py`가 실제로 큐 → OpenAI → PostgreSQL에 row INSERT까지 흘러야 함.

### 코드 검토 결과 (작성 직전 자가 review)

| # | 항목 | 조치 |
|---|---|---|
| 1 | `db_config.py` password 평문 conninfo 조합 → 특수문자 escape 안전 X | **수정** — `psycopg.conninfo.make_conninfo()` 사용 |
| 2 | V5 SQL 주석 번호 중복 (`1, 2, 3, 3, 4`) | **수정** — `1, 2, 3, 4, 5`로 정정 |
| 3 | `smoke_integration_db.py` pool close 누락 → `PythonFinalizationError` 경고 | **수정** — try/finally + `close_pool()` |
| 4 | `infra/.env`의 `SERVICE_NAME=crawler`로 박혀있어 detection 로그에서 service=crawler 표시 | **정보성** — 환경 설정 이슈, 코드 무변경. 운영에서 detection 띄울 때 `SERVICE_NAME=detection` override 필요 |
| 5 | `CrawlEvent`에 title/author/post_url 없어 posts 컬럼 NULL | **정보성** — 의도된 동작. crawler 향후 추가 시 채워짐 |

### 저장하는 값 — 정확한 정의

**`sources` 테이블** (UPSERT — site_name unique):
| 컬럼 | 값 | 출처 |
|---|---|---|
| id | BIGSERIAL | DB |
| site_name | 영문 ID | `CrawlEvent.source_id` |
| board_name | 사람 읽는 이름 | `CrawlEvent.site_name` |
| base_url | NULL | (안 채움 — crawler가 향후) |

**`posts` 테이블** (UPSERT — (source_id, post_id_at_source) unique):
| 컬럼 | 값 | 출처 |
|---|---|---|
| id | BIGSERIAL | DB |
| source_id | FK | UPSERT 결과 |
| post_id_at_source | 사이트별 게시글 ID | `CrawlEvent.post_id` |
| body | 게시글 본문 | `CrawlEvent.raw_text` |
| language | 언어 | `CrawlEvent.language` |
| crawled_at | 크롤 시각 | `CrawlEvent.detected_at` (ISO 8601 파싱) |
| title / author / post_url | NULL | (CrawlEvent에 없음) |

**`detections` 테이블** (INSERT — (post_id, model_version) unique 멱등):
| 컬럼 | 값 | 출처 |
|---|---|---|
| id | BIGSERIAL | DB |
| post_id | FK | UPSERT 결과 |
| is_illegal | `tier != "T4"` | 계산값 |
| type | 분류 카테고리 (`핵_치트` 등) | `LLMResponse.type` |
| tier | T1/T2/T3/T4 | `TierRouter.route()` 결과 |
| confidence | 0~1 | `LLMResponse.confidence` |
| reason | 한국어 판단 근거 | `LLMResponse.reason_ko` |
| translated_text | 외국어→한국어 번역 (한국어 원문이면 NULL) | `LLMResponse.translated_text_ko` |
| image_observed | bool | `LLMResponse.image_observed` |
| token_usage_json | `{input_tokens, output_tokens}` JSONB | `LLMResponse.{input_tokens, output_tokens}` |
| cost_usd | NUMERIC(8,5) | `LLMResponse.cost_usd` |
| model_version | `openai:gpt-4o:YYYY-MM-DD` | `LLMClassifier.model_version` |
| detected_at | NOW() | DB |

**저장 안 하는 것:**
- threshold 점수 (`tier_config.py`의 `TIER_THRESHOLDS`) — 코드 설정값, 대시보드 디스플레이 필터로만 작동
- `correlation_id` — 로그 추적용, DB 컬럼 없음
- `s3_text_path` / `s3_image_paths` — `post_images` 테이블 별도, detection은 안 채움 (crawler 책임)

### 환경변수 (`infra/.env.example` baseline)

| 변수 | 기본 | 본 스토리에서 |
|---|---|---|
| `DB_HOST` | `localhost` | 로컬 dev 기본. 운영에서는 RDS endpoint로 override |
| `DB_PORT` | `5432` | PostgreSQL 기본 포트 |
| `DB_NAME` | `tracker` | |
| `DB_USER` | `tracker_user` | |
| `DB_PASSWORD` | (없음) | **필수** — `infra/.env`에 본인 값. 미설정 시 RuntimeError |
| `DB_SSL_MODE` | `disable` | 로컬 dev. 운영 RDS는 `require` |
| `DB_POOL_MIN_SIZE` | `1` | pool 최소 연결 수 |
| `DB_POOL_MAX_SIZE` | `5` | pool 최대 연결 수. multi-worker 확장 시 늘림 |
| `SERVICE_NAME` | `detection` | 로그 필드. 현 `infra/.env`에는 `crawler`로 박혀있음 — detection 띄울 때 override 필요 |

### Story 3-3 / 3-5 / 3-6과의 경계

- **Story 3-3 (done)**: OpenAI 호출 + Tier 라우팅 + CostCap. 본 스토리에서 그대로 재사용.
- **Story 3-5 (backlog)**: Tier별 confusion matrix + 라벨셋 ≥300건 측정. 본 스토리에서 정확도 측정 0.
- **Story 3-6 (backlog)**: T1 알림 (Redis pub/sub) + Tier 보존 정책 (`retention/tier_retention_job.py`). 본 스토리에서 알림·archive 0.

### Directory Tree (신규/수정)

```
api/src/main/resources/db/migration/
  └── V5__add_tier_and_relax_post_url.sql        # Task 1: 신규
detection/src/
  ├── config/
  │   └── db_config.py                            # Task 2: 신규
  ├── repository/
  │   ├── __init__.py                             # Task 3.1: 신규
  │   └── detection_repository.py                 # Task 3: 신규
  ├── pipeline/
  │   └── detection_pipeline.py                   # Task 4: 갱신 (repository 주입)
  └── main.py                                     # Task 5: wiring 갱신
detection/scripts/
  └── smoke_integration_db.py                     # Task 8.1: 신규
detection/tests/
  ├── conftest.py                                 # Task 7.1: 신규 (DB fixture)
  └── integration/
      ├── test_detection_repository.py            # Task 7.2: 신규 5건
      └── test_llm_pipeline.py                    # Task 7.3: 1건 추가
detection/requirements.txt                        # Task 6: psycopg 추가
docs/integration-smoke-3-4.md                     # Task 8.4: 신규
_bmad-output/implementation-artifacts/
  └── 3-4-탐지-결과-rds-저장-및-스키마-계약-검증.md  # 본 스토리 파일
```

### Testing Standards

- pytest, 단위 테스트는 외부 호출 0건. 통합 테스트는 실 PostgreSQL 사용(`requires_pg`로 PG 미가동 시 자동 skip).
- 통합 테스트의 isolation: `clean_db` fixture가 `TRUNCATE RESTART IDENTITY CASCADE`로 처음 상태로.
- AC #9 실사 smoke는 pytest 범위 밖 (실 OpenAI 호출 발생). `docs/integration-smoke-3-4.md`에 캡처.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.4] — L631-650 AC 출처
- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-05-27.md#Section 4.2 Architecture 갱신] — 스키마 변경 매핑
- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-05-27.md#부록 A-2 전수 저장 정책] — threshold는 디스플레이 필터로만
- [Source: _bmad-output/implementation-artifacts/3-3-openai-멀티모달-llm-분류-tier-라우팅.md] — Story 3-3 LLMResponse / TierRouter / CostCap 인터페이스
- [Source: api/src/main/resources/db/migration/V1__init_schema.sql] — sources / posts / detections 원본 스키마
- [Source: api/src/main/resources/db/migration/V4__add_translated_text.sql] — translated_text 컬럼 (재사용)
- [Source: shared/models/crawl_event.py] — CrawlEvent 필드 정의
- [Source: shared/interfaces/llm.py] — LLMResponse 필드 정의

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context) — 2026-05-27 단일 세션 dev (사후 스토리 파일 작성).

### Debug Log References

- `detection/tests/` — 54 passed in 7.71s, 외부 OpenAI 호출 0건
- `detection/scripts/smoke_integration_db.py` — 실 OpenAI gpt-4o 호출 ≥3회, 매 호출당 $0.00197~$0.00222
- 코드 검토에서 발견된 3개 이슈 모두 수정 후 재실행 확인

### Completion Notes List

- **AC #9 실사 통합 smoke 통과** — 실 OpenAI 호출로 `핵_치트 / T1 / conf=0.98 / $0.00212 / 537·78 tokens`가 큐 → AI → PostgreSQL까지 흘러서 `detections.id=N` 행이 영속 저장됨. `docs/integration-smoke-3-4.md`에 캡처.
- **54 PASS** (Story 3-3 48 + Story 3-4 신규 6). 외부 OpenAI/실 Redis 호출 0건. 실 PostgreSQL 통합 테스트는 자동 skip 가능.
- **트랜잭션 정합성** — `with pool.connection()` 패턴으로 sources/posts/detections 3개 INSERT/UPSERT가 한 트랜잭션. 어느 단계든 실패 시 전체 롤백.
- **멱등성** — `(post_id, model_version)` ON CONFLICT DO NOTHING. 동일 게시글 재처리 시 두 번째는 None 반환, row 누적 없음. test_detection_repository.py에서 검증.
- **B안 채택 사유 명시** — crawler 무변경, Spring API 무변경, detection 안에서 트랜잭션 1개로 처리. 사용자 결정과 일치.
- **사후 스토리 작성** — 본 스토리 파일은 dev 진입 절차 누락 후 사후 작성. 향후 같은 실수 방지를 위해 메모리 갱신.
- **코드 자가 review 3개 fix** — `make_conninfo` / V5 주석 번호 / smoke pool close. 모두 적용 후 54 PASS + smoke 재통과.
- **운영 시 SERVICE_NAME override 필요** — 현 `infra/.env`에 `SERVICE_NAME=crawler` (crawler 트랙 기본값). detection 띄울 때는 `SERVICE_NAME=detection`으로 환경변수 override 필요. 코드 변경 없음, 운영 가이드 사항.

### File List

**신규:**
- `api/src/main/resources/db/migration/V5__add_tier_and_relax_post_url.sql` — Flyway V5
- `detection/src/config/db_config.py` — psycopg ConnectionPool wrapper
- `detection/src/repository/__init__.py`
- `detection/src/repository/detection_repository.py` — save 트랜잭션
- `detection/scripts/smoke_integration_db.py` — 실사 smoke (실 OpenAI + 실 PG)
- `detection/tests/conftest.py` — DB fixture + `requires_pg` skip decorator
- `detection/tests/integration/test_detection_repository.py` — 5 통합 테스트
- `docs/integration-smoke-3-4.md` — 실사 smoke 결과 캡처 + 운영 모드 절차
- `_bmad-output/implementation-artifacts/3-4-탐지-결과-rds-저장-및-스키마-계약-검증.md` — 본 스토리 파일

**수정:**
- `detection/src/main.py` — `db_pool` + `DetectionRepository` wiring
- `detection/src/pipeline/detection_pipeline.py` — `repository` 의존성 주입 + `save` 호출
- `detection/src/pipeline/llm_classifier.py` — (Story 3-3 작성분) `model_version` 포맷
- `detection/requirements.txt` — `psycopg[binary,pool]>=3.2.0` 추가
- `detection/tests/integration/test_llm_pipeline.py` — `test_pipeline_calls_repository_save_on_success` 추가
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — 3-4 backlog → review

### Change Log

| 일자 | 변경 | 비고 |
|---|---|---|
| 2026-05-27 | Story 3-4 dev 완료 (review로 이동) | 54 PASS / 실사 smoke 통과 / B안 (detection이 posts UPSERT 책임) |
| 2026-05-27 | 코드 자가 review 3개 fix 적용 | make_conninfo / V5 주석 / smoke pool close |
| 2026-05-27 | 사후 스토리 파일 작성 (dev-story 절차 누락 만회) | 메모리에 절차 위반 방지 규칙 추가 |
