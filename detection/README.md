# detection

Redis 큐에서 `CrawlEvent`를 소비해 OpenAI gpt-4o 멀티모달 LLM으로 불법 게시글을 분류하고 RDS에 저장하는 탐지 파이프라인.

---

## 동작 모드

| 모드 | 동작 |
|---|---|
| `single` (기본) | `LLMClassifier` → gpt-4o 단일 호출로 분류·번역·근거 동시 산출 |
| `agentic` | S0 정규화 → S1 트리아지(gpt-4o-mini) → S2b LinkTracer(1-hop 추적) → S3 종합(gpt-4o). 비용 차등 멀티 에이전트 |

`DETECTION_MODE=single|agentic` 환경변수로 전환. 기본값은 `single`.

---

## 빠른 시작

```bash
cd detection

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

# 단위 테스트 (외부 서비스 불필요)
pytest tests/unit -q

# 통합 테스트 (PostgreSQL 필요, CI에서는 skip)
pytest tests/integration -q -m "not pg"

# ruff 린트
ruff check src/ tests/ scripts/ ../shared/
```

---

## 환경 변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `OPENAI_API_KEY` | 필수 | OpenAI API 키 (Docker secrets `/run/secrets/openai_api_key` → shim 변환) |
| `REDIS_URL` | `redis://localhost:6379` | Redis 접속 URL |
| `DB_HOST` | `localhost` | PostgreSQL 호스트 |
| `DB_PORT` | `5432` | PostgreSQL 포트 |
| `DB_NAME` | `tracker` | DB 이름 |
| `DB_USER` | `tracker_user` | DB 사용자 |
| `DB_PASSWORD` | — | DB 비밀번호 |
| `DB_SSL_MODE` | `disable` | psycopg3 sslmode (`require` 등) |
| `DETECTION_MODE` | `single` | `single` 또는 `agentic` |
| `LLM_MODEL` | `gpt-4o` | 분류 모델 ID |
| `TRIAGE_MODEL` | `gpt-4o-mini` | 트리아지 모델 ID (agentic 모드) |
| `LLM_TIMEOUT_SEC` | `30` | LLM 호출 타임아웃(초) |
| `LLM_DAILY_COST_CAP_USD` | `5` | 일일 비용 상한 USD. `0`이면 cap 비활성 |
| `TIER_THRESHOLD_T1` | `0.65` | T1 신뢰도 임계값 |
| `TIER_THRESHOLD_T2` | `0.75` | T2 신뢰도 임계값 |
| `TIER_THRESHOLD_T3` | `0.85` | T3 신뢰도 임계값 |
| `TIER_THRESHOLD_T4` | `0.90` | T4 신뢰도 임계값 |
| `LINK_TRACE_TIMEOUT_SEC` | `5` | LinkTracer HTTP 타임아웃(초) |
| `LINK_TRACE_PROXY` | 미설정 | LinkTracer 프록시 URL |
| `LINK_TRACE_MAX_BYTES` | `524288` | LinkTracer 응답 최대 크기(Bytes) |
| `FAST_PATH_CONFIDENCE` | `0.75` | agentic 모드 fast-path 임계값 |
| `SERVICE_NAME` | `detection` | 구조화 로그 서비스 이름 |

---

## 디렉터리 구조

```
detection/
├── requirements.txt
├── pytest.ini
├── scripts/                    # 운영자 CLI 스크립트
│   ├── seed_one_post.py        # 테스트 게시글 1건 주입
│   ├── smoke_integration.py    # 실 OpenAI 단일 호출 smoke
│   ├── smoke_integration_db.py # 실 OpenAI + DB smoke
│   ├── smoke_agent_pipeline.py # agentic 모드 smoke
│   ├── label_detections.py     # 수동 라벨링 CLI
│   ├── build_fewshot_corpus.py # few-shot 코퍼스 빌드
│   ├── labelset_snapshot.py    # 라벨셋 스냅샷 (agreement/coverage)
│   └── spike_llm.py            # LLM PoC 실험용
└── src/
    ├── main.py                 # 진입점 — 모드별 컨슈머/오케스트레이터 기동
    ├── agents/                 # agentic 모드 에이전트
    │   ├── contracts.py        # AgentResult 타입 계약
    │   ├── normalizer.py       # S0: 변형문자 정규화 + 링크 추출
    │   ├── triage_agent.py     # S1: gpt-4o-mini 트리아지
    │   ├── link_tracer.py      # S2b: 1-hop HTTP 링크 추적
    │   ├── link_fetch_guard.py # SSRF/파일 다운로드 가드
    │   ├── url_policy.py       # 공식 도메인 whitelist
    │   └── orchestrator.py     # S0→S1→S2b→S3 결정론적 흐름
    ├── config/
    │   ├── db_config.py        # psycopg3 ConnectionPool
    │   ├── redis_config.py     # Redis DB0(MQ)/DB2(rate_limit) 클라이언트
    │   └── tier_config.py      # T1~T4 신뢰도 임계값
    ├── consumer/
    │   ├── queue_consumer.py   # Redis BRPOPLPUSH 컨슈머
    │   └── watchdog.py         # 처리 중 stale 메시지 DLQ 복구 (300s TTL)
    ├── mocks/
    │   └── llm_mock.py         # 테스트용 LLM mock (clean/illegal/rate_limited/timeout)
    ├── pipeline/
    │   ├── detection_pipeline.py # single 모드 파이프라인 오케스트레이터
    │   ├── llm_client.py         # OpenAI HTTP 클라이언트 (structured output + 이미지)
    │   ├── llm_classifier.py     # LLMClassifier — 9-type 분류 + Tier 라우팅
    │   └── tier_router.py        # 신뢰도 → T1/T2/T3/T4 매핑
    ├── prompts/
    │   ├── registry.py           # 시스템 프롬프트 조합 (domain_guide + type_guidance + few-shot)
    │   ├── domain_guide.md       # 게임 도메인 지식 + 은어 사전 + 오탐 방지 규칙
    │   ├── type_guidance.md      # 9유형 판별 경계 규칙
    │   └── examples/             # few-shot 코퍼스 (game × type JSONL)
    ├── rate_limit/
    │   ├── token_bucket.py       # Redis Lua atomic 토큰 버킷 (llm:rate_limit:classify)
    │   └── cost_cap.py           # 일일 비용 상한 가드 (LLM_DAILY_COST_CAP_USD)
    ├── repository/
    │   └── detection_repository.py # posts UPSERT + detections INSERT 단일 트랜잭션
    └── retry/
        └── retry_handler.py      # 지수 백오프 재시도 (1s/2s/4s, 최대 3회)
```

---

## 테스트

```bash
# 단위 테스트 — 165건 (외부 서비스 불필요)
pytest tests/unit -q

# 통합 테스트 — 20건, 실 PostgreSQL 필요
pytest tests/integration -q

# 전체 — 185건
pytest -q
```

단위 테스트는 `llm_mock.py` + `fakeredis[lua]`로 100% mock 동작. 통합 테스트는 실 DB 연결 필요(CI에서 skip 마킹).

---

## 외부 서비스 의존성

| 서비스 | 용도 | 테스트에선 |
|---|---|---|
| OpenAI API | gpt-4o/gpt-4o-mini 분류·번역 | `llm_mock.py` 주입 |
| Redis DB0 | `posts:queue` BRPOPLPUSH 컨슈머 | `fakeredis` |
| Redis DB2 | `llm:rate_limit:classify` 토큰 버킷 | `fakeredis[lua]` |
| PostgreSQL | `sources/posts/detections/agent_runs` 저장 | 실 DB (통합 테스트) |

---

## LinkTracer 배포 판단 기준

`agentic` 모드에서 S2b LinkTracer가 외부 링크 페이지를 1-hop fetch한 뒤, **LLM 미사용** 규칙 기반으로 `is_distribution_site`를 판정한다. 코드: [detection/src/agents/link_tracer.py](src/agents/link_tracer.py)

### 판정 흐름

```
링크 URL 수신
  ├─ 메신저 도메인? → fetch 없이 kind=messenger 기록, 판정 종료
  ├─ SSRF 가드 차단? → kind=blocked, 판정 종료
  └─ 1-hop HTTP fetch → 페이지 제목 + 본문 발췌
       └─ _detect_indicators(title, body)
            ├─ 배포 키워드 포함? → indicators에 "배포 관련 표현 발견"
            ├─ 거래 키워드/패턴 포함? → indicators에 "거래/연락처 정황 발견"
            └─ 둘 중 하나라도 → is_distribution_site = True
```

공식 도메인 + 공식 설치 문맥(런처·스토어·공식 다운로드)이면 `is_distribution_site=False`로 예외 처리. 코드: [url_policy.py](src/agents/url_policy.py)

### 배포 지표 키워드 (`_DISTRIBUTION_KEYWORDS`)

| 언어 | 키워드 |
|---|---|
| 영어 | `download`, `crack`, `hack`, `cheat`, `macro`, `bot` |
| 한국어 | `다운로드`, `크랙`, `핵`, `치트`, `매크로`, `봇` |
| 중국어 간체 | `下载`, `破解`, `外挂`, `辅助` |
| 중국어 번체 | `下載`, `外掛`, `輔助` |

### 거래/연락처 지표 키워드 (`_TRADE_KEYWORDS` + `_TRADE_PATTERNS`)

| 분류 | 키워드·패턴 |
|---|---|
| 한국어 거래 | `가격`, `판매`, `구매`, `문의`, `충전`, `현금` |
| 중국어 거래 | `代儲`, `代充`, `面交`, `蝦皮`, `微信` |
| 영어/범용 | `price`, `paypal`, `kakao`, `line id`, `wechat`, `discord` |
| 금액 정규식 | `숫자,숫자원` 형태 (예: `10,000원`), `숫자원/만원/천원` |

### 메신저 도메인 (fetch 없이 kind=messenger)

`discord.gg`, `discord.com`, `t.me`, `telegram.me`, `open.kakao.com`, `line.me`, `qq.com`

fetch 없이 "비공개 채널 유도(메신저 초대링크)"를 `indicators`에 기록한다. is_distribution_site는 기본값 `False` — 메신저 링크 자체가 배포 사이트임을 의미하지 않으며, 맥락 판단은 Synthesizer(S3)에서 다른 증거와 종합한다.

### 공식 도메인 예외 (`url_policy.py`)

아래 도메인이 **공식 설치/스토어 문맥**(런처, 다운로드, 스토어, 클라이언트 등 키워드 포함)일 때만 `is_distribution_site=False`로 예외 적용. 공식 도메인이라도 설치 문맥이 없으면 예외 없이 정상 판정.

NC/PURPLE: `plaync.com`, `nc.com`, `ncsoft.com`, `ncupdate.com`

스토어/플랫폼: `steampowered.com`, `epicgames.com`, `play.google.com`, `apps.apple.com`

기타 퍼블리셔: `nexon.com`, `netmarble.com`, `kakaogames.com`, `wemade.com`, `pearlabyss.com` 외

환경변수 `OFFICIAL_SERVICE_DOMAIN_SUFFIXES`(콤마 구분)로 목록 확장 가능.

---

## 다음 단계

- [ ] S2a ImageAnalyst + S3 Synthesizer 구현 (Story 3-8)
- [ ] single vs agentic A/B 정확도 비교 + 비용 실측 (Story 3-9)
- [ ] 중국 IP 프록시 경유 LinkTracer 실사 검증
