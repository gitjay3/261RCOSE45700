# api

Tracker 백엔드 REST API. 탐지 결과 조회·통계·크롤링 트리거·활동 로그·알림 채널/규칙/전송 이력을 제공하는 Spring Boot 3.5 서비스.

---

## 빠른 시작

```bash
cd api

# 빌드 + 테스트
./gradlew build

# 테스트만
./gradlew test

# 로컬 실행 (PostgreSQL + Redis 필요)
./gradlew bootRun
```

Swagger UI: `http://localhost:8080/swagger-ui.html`

---

## 환경 변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `DB_HOST` | `localhost` | PostgreSQL 호스트 |
| `DB_HOST_PORT` | `5432` | PostgreSQL 포트 |
| `DB_NAME` | `tracker` | DB 이름 |
| `DB_USER` | `tracker_user` | DB 사용자 |
| `DB_PASSWORD` | 필수 | DB 비밀번호 |
| `DB_SSL_MODE` | `require` | JDBC sslmode |
| `REDIS_HOST` | `localhost` | Redis 호스트 |
| `REDIS_PORT` | `6379` | Redis 포트 |
| `REDIS_PASSWORD` | 미설정 | Redis 비밀번호 |
| `REDIS_CACHE_DB` | `3` | cache:detections Redis DB 번호 |

---

## API 엔드포인트

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/detections` | 탐지 목록. `site`, `type`, `lang`, `date`, `range=7d\|30d`, 신뢰도 필터 지원 |
| GET | `/api/detections/{id}` | 탐지 상세 (원문·번역·근거·이미지·원본 URL) |
| GET | `/api/detections/{id}/agent-runs` | agentic 모드 에이전트 실행 이력 |
| GET | `/api/stats` | 통계. `days=7\|30` 미설정 시 전체 기간 |
| POST | `/api/crawl/trigger` | 수동 크롤링 트리거 (Redis `crawl:trigger` pub/sub) |
| GET | `/api/crawl/jobs/{jobId}` | 크롤링 잡 진행 상황 |
| GET | `/api/crawl/stats` | 크롤링 집계 통계 |
| GET | `/api/crawl/running` | 현재 실행 중인 잡 목록 |
| GET | `/api/activity` | 활동 로그 목록 |
| POST | `/api/activity` | 활동 로그 기록 |
| GET | `/api/notifications/channels` | 알림 채널 목록 |
| POST | `/api/notifications/channels` | 알림 채널 추가 (Discord/Slack/Teams/Google Chat webhook) |
| POST | `/api/notifications/channels/{id}/test` | 알림 채널 테스트 발송 |
| GET | `/api/notifications/rules` | 알림 규칙 목록 |
| POST | `/api/notifications/rules` | 알림 규칙 생성 (minTier 기반 필터) |
| GET | `/api/notifications/deliveries` | 알림 전송 이력 |

---

## 데이터베이스 스키마 (Flyway)

| 마이그레이션 | 내용 |
|---|---|
| V1 | `sources`, `posts`, `post_images`, `detections` 기본 스키마 |
| V2 | `idx_detections_filter` 복합 인덱스 |
| V3 | `detections(post_id, model_version)` unique constraint |
| V4 | `detections.translated_text_ko` |
| V5 | `tier`, `image_observed`, `token_usage_json`, `cost_usd` + `sources.base_url` NULLABLE |
| V6 | `post_url` 백필 |
| V7 | 알림 관련 4개 테이블 (`notification_channels`, `notification_rules`, `notification_events`, `notification_deliveries`) |
| V8 | `activity_log` 테이블 |
| V9 | `detections.human_label`, `human_verified_at`, `label_source` (few-shot 라벨링) |
| V10 | `agent_runs` 테이블 (agentic 모드 에이전트 실행 이력) |
| V11 | `detections.model_version` 컬럼 길이 확장 |

---

## 디렉터리 구조

```
api/src/main/java/com/tracker/api/
├── TrackerApiApplication.java
├── config/              # Redis cache config, CORS, OpenAPI
├── controller/          # Detection, Stats, Crawl, Activity REST 컨트롤러
├── domain/              # JPA 엔티티 (Detection, Post, Source, AgentRun, ActivityLog)
├── dto/                 # 요청/응답 DTO
├── exception/           # ProblemDetail (RFC 9457) 기반 에러 핸들러
├── metrics/             # Prometheus 메트릭 (RedisQueueMetrics 등)
├── notification/        # 알림 서브시스템
│   ├── adapter/         # Discord/Slack/Teams/Google Chat webhook 어댑터
│   ├── controller/      # /api/notifications/* REST 컨트롤러
│   ├── domain/          # 알림 엔티티 (Channel, Rule, Event, Delivery)
│   ├── repository/      # Spring Data JPA 저장소
│   └── service/         # 알림 발송, 규칙 평가, 채널 관리, 암호화
├── repository/          # Detection, Post, Source JPA 저장소
├── service/             # 비즈니스 로직
└── util/                # 유틸리티

api/src/main/resources/
├── application.properties      # 운영 설정
└── db/migration/               # Flyway SQL 마이그레이션 V1~V11
```

---

## 외부 서비스 의존성

| 서비스 | 용도 |
|---|---|
| PostgreSQL/RDS | 탐지·통계·알림 데이터 영구 저장 |
| Redis DB0 | `crawl:trigger` pub/sub (수동 크롤링 트리거 발행) |
| Redis DB3 | `/api/stats` 캐시 (`cache:detections:stats`) |
