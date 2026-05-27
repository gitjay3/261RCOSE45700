# Sprint Change Proposal — Epic 2 PIVOT (Crawler 전면 재작성 + 검색엔진형 확장 계획)

> **Date:** 2026-05-19  
> **Author:** Tracker (with BMad Correct Course workflow)  
> **Branch:** `feat/epic-2-crawler-rewrite`  
> **Scope classification:** **Moderate** (백로그 재편 + 문서 retroactive 정합화, 코드 변경 0)  
> **Status:** Drafted — awaiting user approval

---

## Section 1. Issue Summary

### 문제 진술

Epic 2 (자동 크롤링 및 전처리 파이프라인) 의 기존 구현 (`crawler/` 디렉터리, Stories 2-1~2-7 완료분) 이 통합 운영에 부족함이 확인되어, 별도 폴더 `crawler_test/` 에서 더 견고한 신규 구현을 개발해 왔다. 이번 PIVOT에서 `crawler_test/` 의 신규 구현을 `crawler/` 로 통째 승격 (deleted 103 / modified 10 / added 8 — 142 PASS, 외부 네트워크 호출 0건). 동시에 신규 구현이 도입한 능력 (`content_validator`, `url_dedup_checker`, Bahamut NC 8게임 분리, `title_keywords` 사전 필터, inter-site/inter-board delay) 과 향후 확장 계획 (검색엔진형 8개 사이트) 을 BMad 트래킹에 retroactive로 정합화할 필요가 있다.

### 발견 맥락

- **유형:** Failed approach + New requirement emerged (체크리스트 1.2 분류)
- **트리거:** Epic 2 기존 코드가 통합 운영 수준에 미달 → 별도 트랙 (`crawler_test/`) 에서 재작성 → PIVOT으로 통합 승격
- **증거:**
  1. 142 unit + integration tests PASS (외부 네트워크 0건)
  2. deleted 103 / modified 10 / added 8 (브랜치 `feat/epic-2-crawler-rewrite`)
  3. 외부 contract 호환 검증 완료:
     - Redis `posts:queue` 채널 — 그대로
     - `shared.models.CrawlEvent` 필드 — 그대로
     - `crawl:trigger` PubSub (api/CrawlTriggerService 연동) — 그대로
     - Dockerfile entry (`crawler.src.scheduler.crawl_scheduler.__main__`) — 그대로
     - `infra/compose.prod.yml` — 변경 불필요
  4. Cross-system 영향 0:
     - `api/`, `detection/`, `shared/` — 어디서도 crawler import 안 함
     - `shared/` 자체 변경 0
- **향후 신호 (forward-looking, 별도 PIVOT 예정):**
  - Epic 3 재설계 검토 중 — VARCO Translation + language detection 제거, 텍스트 LLM + 이미지 VLM 직결 구조. 본 Epic 2 PIVOT 범위 외, 메모로만 등록.

---

## Section 2. Impact Analysis

### Epic Impact

| Epic | 영향 |
|---|---|
| **Epic 1** (토대 인프라) | ✅ 영향 없음 (CrawlEvent contract 동일성 유지) |
| **Epic 2** (크롤링) | ❗ **`done → in-progress` 회귀**. Stories 2-1~2-7 신규 코드에 흡수 매핑. Stories 2-8~2-12 신규 backlog 추가 (검색엔진 트랙) |
| **Epic 3** (탐지) | ✅ 본 PIVOT 영향 없음 (CrawlEvent contract 호환). 단, 별도 forward-looking 메모: VARCO Translation/language detection 제거 재설계 검토 중 |
| **Epic 4** (대시보드) | ✅ 영향 없음 |
| **Epic 5** (운영) | ✅ 영향 없음 (Dockerfile entry / compose.prod.yml 호환) |

### Story Impact

#### 흡수 매핑 (Stories 2-1 ~ 2-7, 모두 done 유지)

| Story | 기존 책임 | 신규 구현 매핑 |
|---|---|---|
| 2-1 Cloudflare 우회 검증 | Playwright + stealth | `BrowserConfig(enable_stealth=True)` + SiteConfig 단위 토글 |
| 2-2 ProxyProvider 추상화 | ProxyBroker → NodeMaven 교체 가능 | `SiteConfig.proxy` 필드로 단순화 통합 |
| 2-3 crawl4ai 전처리 | crawl4ai + language/dedup/keyword | `crawl4ai_crawler.py` + `preprocessor/{language_detector, dedup_checker, url_dedup_checker, content_validator, serializer}.py` (html_parser, keyword_filter 제거) |
| 2-4 S3 아카이브 | S3Uploader + 로컬 저장 | `s3_uploader.py` + `storage.py` 분리 |
| 2-5 APScheduler | scheduler + trigger_listener | `scheduler/crawl_scheduler.py` + `scheduler/trigger_listener.py` 분리, inter-site/inter-board delay ±25% jitter 신규 |
| 2-6 PTT·Dcard SiteConfig | 4 보드 | `sites/registry.py` 통합 (ptt + ptt_mobile_game + dcard + dcard_online) |
| 2-7 중국 사이트 SiteConfig | tieba + 52pojie + nga | `sites/registry.py` 통합. Bahamut NC 8게임 분리 신규 |

#### 신규 등록 (Stories 2-8 ~ 2-12, 모두 backlog)

| Story | 대상 사이트 | 비고 |
|---|---|---|
| 2-8 SearchEngineConfig + GitHub | github (글로벌) | 추상화 검증용 첫 도전 |
| 2-9 Reddit | reddit (글로벌) | |
| 2-10 Bing + DuckDuckGo (CN) | bing, duckduckgo_cn | 한국 IP 접근 가능 |
| 2-11 Facebook | facebook (via Bing) | 가장 어려운 케이스 |
| 2-12 중국 검색엔진 | baidu, sogou, bilibili | **중국 residential proxy 선결 필요** |

### Artifact Conflicts

| 산출물 | 변경 |
|---|---|
| **`sprint-status.yaml`** | Epic 2 status 회귀 + Stories 2-1~2-7 흡수 매모 + 2-8~2-12 backlog + 최상단 PIVOT 메모 (forward-looking Epic 3 신호 포함) |
| **`epics.md`** | Epic 2 본문에 2026-05-19 PIVOT 메모 + 신규 능력 컴포넌트 등록 + Epic 2 검색엔진 트랙 서브섹션 (Stories 2.8~2.12) 신설 |
| **`architecture.md`** | `crawler/` 디렉터리 트리 갱신, Decision 항목 10 PIVOT 메모 + 항목 11~13 신규 추가, SearchEngineConfig vs SiteConfig 비교 표 신설, Data Flow 도표 갱신, 항목 14 (Epic 3 forward-looking) 추가 |
| **`prd.md`** | Executive Summary "최대 6개" → "15개 데이터 소스" 갱신, 데이터 소스 우선순위 표 신설 (게시판 7 부모 + 검색 8), MVP 전처리 단계 갱신, Growth Features 에 검색엔진 트랙 추가 |
| **`ux-design-specification.md`** | ✅ 영향 없음 (대시보드 UI 무변경) |
| **인프라** (`infra/compose.prod.yml`, `Dockerfile`, CI/CD) | ✅ 영향 없음 |
| **Code** (api/, detection/, shared/) | ✅ 변경 0 |

---

## Section 3. Recommended Approach

### 선택: **Option 1 (Direct Adjustment) + Hybrid (신규 트랙 추가)**

#### Path Forward Evaluation

| 옵션 | 평가 | 효과 |
|---|---|---|
| ❌ Option 2 (Rollback) | 142 PASS + 외부 contract 호환 검증 완료 → 롤백 가치 없음 | Not viable |
| ❌ Option 3 (MVP Review) | MVP 코어 (탐지 파이프라인) 무영향, Epic 3 진행 중 | Not viable |
| ✅ **Option 1 + Hybrid** | 문서 retroactive 정합화 + 신규 검색엔진 트랙 backlog 등록 | Effort: Medium / Risk: Low |

#### Rationale

1. **코드 측면 안전성 확보**: 신규 구현은 142 tests PASS + 외부 네트워크 0 + cross-system 영향 0. 즉시 운영 가능 상태.
2. **외부 contract 호환**: `posts:queue`, `CrawlEvent`, `crawl:trigger`, Dockerfile entry, compose 모두 그대로 → Epic 3·4·5 무영향.
3. **신규 능력 명시화**: `content_validator` (품질 가드), `url_dedup_checker` (2계층 dedup), `title_keywords` 사전 필터, Bahamut NC 8게임 분리 등이 architecture/PRD에 등록되어 향후 작업 참조 지점 확보.
4. **검색엔진 트랙 분리 등록**: `SearchEngineConfig` 추상화는 board-1-hop vs search-2-hop의 모델 차이를 명시. Epic 2 서브트랙 (Stories 2-8~2-12) 으로 편입 (출력 CrawlEvent 동일성 근거).
5. **Epic 3 forward-looking 신호 보존**: 향후 재설계 (Translation/language detection 제거, LLM/VLM 직결) 가 검토 중임을 메모로 남겨 본 PIVOT의 의사결정이 미래 PIVOT을 차단하지 않도록 함.

#### Effort · Risk · Timeline

- **Effort:** Medium (4개 문서 retroactive 정합화 — 코드 변경 0)
- **Risk:** Low (외부 contract 호환 검증 완료, cross-system 영향 0)
- **Timeline impact:** None on Epic 3 진행 (현재 in-progress, 본 PIVOT과 무관). 신규 검색엔진 트랙은 Epic 3 완료 후 착수.

---

## Section 4. Detailed Change Proposals

### Proposal 1: `sprint-status.yaml`

**Changes:**
- 1A — 최상단 PIVOT 메모 추가 (line 2~3) + forward-looking Epic 3 신호 append
- 1B — Epic 2 status `done → in-progress` 회귀 + PIVOT 메모 (line 135)
- 1C — Stories 2-1~2-7 흡수 매핑 메모 (line 136~142)
- 1D — Stories 2-8~2-12 backlog 신규 등록 + Epic 2 검색엔진 트랙 헤더 (line 143 직전)
- 1E — `last_updated` 헤더 (line 117) PIVOT 메모 prepend

**상세 diff:** 워크플로우 대화 로그 Proposal 1 참조 (Approved).

### Proposal 2: `epics.md`

**Changes:**
- 2A — Epic List Epic 2 엔트리 (line 145~156) 에 2026-05-19 PIVOT 블록 추가
- 2B — Epic 2 본문 (line 292) PIVOT 메모 + 신규 능력 컴포넌트 등록 블록
- 2C — Epic 2 본문에 "Epic 2 검색엔진 트랙 (Stories 2.8~2.12)" 서브섹션 신설 (line 426 직전). 5개 신규 Story 정의 + AC 초안 포함.

**상세 diff:** 워크플로우 대화 로그 Proposal 2 참조 (Approved — Epic 2 서브트랙 편입).

### Proposal 3: `architecture.md` (개정판)

**Changes:**
- 3A — `crawler/` 디렉터리 트리 (line 540~553) 갱신: preprocessor 5개 파일 정합화 (html_parser, keyword_filter 제거 / content_validator, url_dedup_checker, serializer 신규), `search/` 디렉터리 (Stories 2-8~2-12 예정), `scripts/smoke_each_site.py`, `README.md`, `STATUS.md`, 테스트 파일 갱신
- 3B — Decision 항목 10 에 PIVOT 메모 + 항목 11 (URL Dedup 이중화), 12 (Content Validator 8-kind 품질 가드), 13 (Title Keywords 사전 필터), 14 (Epic 3 forward-looking) 신규 추가
- 3C — "FR 카테고리 → 디렉토리 매핑" 표 직후에 `SearchEngineConfig` vs `SiteConfig` 비교 섹션 신설 + 공통 컴포넌트 목록 정합화
- 3D — Data Flow 도표 (line 750~755) 갱신: `title_keywords` 사전 필터 → `url_dedup_checker` 본문 fetch 전 차단 → `crawl4ai_crawler` 본문 fetch → preprocessor (language_detector → dedup_checker → content_validator → serializer) → redis_publisher

**상세 diff:** 워크플로우 대화 로그 Proposal 3 v2 참조 (Approved — crawler_test/ 교차 검증 완료).

### Proposal 4: `prd.md`

**Changes:**
- 4A — Executive Summary (line 21) "최대 6개" → "게시판 7 부모 + 검색 8 = 15개 데이터 소스"
- 4B — `## Product Scope` 와 `### MVP` 사이에 `### 데이터 소스 (2026-05-19 PIVOT 반영)` 섹션 신설. 게시판형 7 부모 + 검색엔진형 8 우선순위 표 + 진행 트랙 4종 (A: 즉시 / B: proxy 선결 / C: Epic 3 완료 후 / D: Known issues)
- 4C — `### MVP` 본문 전처리 단계 갱신: HTML 파싱·키워드 필터 제거, 언어 감지·URL 중복·content 중복·content_validator 품질 가드·serialize 명시
- 4D — `### Growth Features` 에 "검색엔진형 데이터 소스 (Stories 2-8~2-12)" 항목 + 프록시 업그레이드 항목에 PIVOT 메모 append

**상세 diff:** 워크플로우 대화 로그 Proposal 4 참조 (Approved — 부모 사이트 기준 15).

---

## Section 5. Implementation Handoff

### Scope Classification: **Moderate**

- **이유:** 백로그 재편성 (5개 신규 Story + 1개 Epic 상태 회귀) + 4개 문서 retroactive 정합화. 코드 변경 0. PO 합의 (백로그 우선순위) + Tech writer/PM 협조 (문서 작성) 필요.

### Routing

| 역할 | 책임 | 산출물 |
|---|---|---|
| **PM / 기획 (John 에이전트)** | (1) Sprint Change Proposal 최종 승인 (2) Stories 2-8~2-12 우선순위 확정 (Epic 3 완료 후 착수 권고) (3) 중국 residential proxy 인프라 트랙 의사결정 (별도) | 본 문서 승인 sign-off |
| **PO / Tracker (사용자)** | sprint-status.yaml + epics.md + architecture.md + prd.md 실제 파일 편집 적용 (Step 5에서 일괄 수행 가능) | 4 files committed on `feat/epic-2-crawler-rewrite` 또는 별도 docs 브랜치 |
| **Dev (Amelia 에이전트)** | (1) 신규 brunch의 PR 번호 확정 후 메모에 채워넣기 (2) Known issues 단발 fix 트래킹 (dcard_online wait_for / ptt_mobile_game·dcard /f/game 페이지네이션) | Issue / Story 단위 분해 |
| **Test architect (Murat 에이전트)** | 142 PASS 회귀 보호 — Epic 3 진행 중 crawler 회귀 시 즉시 알림 / Story 2.8 (SearchEngineConfig 추상화 검증) 시 ATDD 도움 | 테스트 가드 |

### Success Criteria

1. 4개 문서 파일이 본 PIVOT 메모를 반영하여 git에 commit 됨
2. `sprint-status.yaml` 에서 Epic 2 status = `in-progress`, Stories 2-8~2-12 backlog 등록 확인
3. Epic 3 진행에 영향 없음을 회귀 테스트 (detection 28 tests PASS) 로 확인
4. PR 번호가 메모에 채워짐 (`PR # (채워넣기)` 자리)
5. Forward-looking Epic 3 신호가 sprint-status + architecture 두 위치에 메모됨 (별도 PIVOT 트래킹 가능)

### Deferred / Out of Scope

- **Epic 3 재설계** (VARCO Translation + language detection 제거, 텍스트 LLM + 이미지 VLM 직결) — 별도 Correct Course 세션
- **중국 residential proxy 인프라 트랙** — 별도 의사결정 (tieba/NGA/52pojie + baidu/sogou/bilibili 모두 영향 받음)
- **Known issues 단발 fix** (dcard_online wait_for / ptt_mobile_game·dcard /f/game 페이지네이션) — `[QQ] /bmad-quick-dev` 로 별도 처리

---

## Appendix: 워크플로우 실행 로그

- **Step 1 (Initialize):** 변경 트리거 (Tracker 직접 설명) + Incremental 모드 — Complete
- **Step 2 (Checklist):** 6 sections × ~25 items 평가 완료 — Complete
- **Step 3 (Drafts):** Proposal 1~4 incremental 협의 — Complete (1 Approved, 2 Approved, 3 Edit→v2 Approved, 4 Approved)
- **Step 4 (This document):** Generated 2026-05-19
- **Step 5 (Approval & Routing):** Pending user approval
- **Step 6 (Completion):** Pending

---

## Review Findings

> 3-layer adversarial code review (Blind Hunter + Edge Case Hunter + Acceptance Auditor) on PR #46.
> Date: 2026-05-20. Diff: 126 files / +2871 / -1623 / 5,667 diff lines.

### Decision-needed (1)

- [x] [Review][Decision] **tieba/nga `enabled=False` vs PRD P3 트랙 불일치** — **해결 (2026-05-20):** Option C 채택. registry `enabled=False` 유지, PRD §데이터 소스 표를 `P3 (disabled)` 로 격하 + 2026-05-20 Bright Data PoC 실패 사유 명시. 트랙 B 메모도 동기화. — PRD/architecture 문서는 tieba/nga를 P3(proxy 선결) 트랙으로 active 명시하나, registry.py에서는 `enabled=False`로 비활성화. Story 5-1 미스파이어 리스너 제거(아래 Critical-2)와 함께 PIVOT 의도 명확화 필요. **Option A:** 두 사이트를 PRD에서도 "disabled until proxy 검증"으로 격하 / **Option B:** registry `enabled=True`로 복귀 + content_validator로 차단 페이지 식별만 강화 / **Option C:** 현 상태 유지 + PRD에 "Bright Data PoC 실패로 일시 disabled (2026-05-20)" 메모만 추가. [`crawler/src/sites/registry.py:4424, 4456`, `_bmad-output/planning-artifacts/prd.md:333-335`]

### Patch (Critical / High — 즉시 수정 권장)

- [x] [Review][Patch][Critical] **ptt/52pojie/bahamut/nga 모든 포스트가 `_validate_id` ValueError로 silently fail** — **fixed (2026-05-20):** 4개 사이트(ptt, ptt_mobile_game, 52pojie, bahamut_*, nga)에 site별 `post_id_extractor` 추가. PTT: `M\.(\d+)` / 52pojie: `thread-A_B_C` / Bahamut: `bsn<N>_snA<N>` / NGA: tid 추출. 7개 사이트 모두 `_SAFE_ID_RE` 통과 실증, crawler 143 tests PASS. — 4개 사이트에 `post_id_extractor=` override가 없어 기본 lambda(`url.rstrip("/").split("/")[-1]`)가 `M.1700000000.A.ABC.html` / `thread-1234567-1-1.html` / `C.php?bsn=842&snA=12345` / `read.php?tid=12345`를 반환. `storage._SAFE_ID_RE = ^[A-Za-z0-9_\-]+$`에서 거부 → `CrawlPipeline.run`의 broad except에 잡혀 모든 포스트가 `failed`로 계수. 142 unit tests PASS는 storage가 mock되었거나 실제 사이트 통합 테스트가 안 돌아서 본 경로를 못 탔기 때문. **즉시 fix:** 사이트별 `post_id_extractor` lambda 추가 (PTT: regex `M\.(\d+)` / 52pojie: `thread-(\d+)-` / Bahamut: `bsn=(\d+).+snA=(\d+)` → 조합 / NGA: `tid=(\d+)`) [`crawler/src/sites/registry.py:215-371`, `crawler/src/storage.py:22, 35-39, 80-81`]

- [x] [Review][Patch][Critical] **Story 5-1 `EVENT_JOB_MISSED` 미스파이어 리스너 silently 제거** — **fixed (2026-05-20):** `crawl_scheduler.py` 에 `from apscheduler.events import EVENT_JOB_MISSED` import + `_on_job_missed` 핸들러 (job_id + scheduled_run_time 구조화 로그) + `setup_schedule` 마지막에 `add_listener(self._on_job_missed, EVENT_JOB_MISSED)` 호출 복원. Story 5-1 의 운영 가시성 contract 회복. crawler 143 tests PASS. — Story 5-1(done)의 운영 가시성 contract(`misfire 발생 시 구조화 로그`)가 PIVOT에서 임포트·핸들러·`add_listener` 호출 모두 삭제됨. Sprint Change Proposal Impact Analysis에는 언급 없음. **Fix:** `_on_job_missed` 핸들러 + `add_listener(EVENT_JOB_MISSED)` 복원, 또는 Sprint Change Proposal에 contract regression 명시 + sprint-status에서 Story 5-1 status 갱신. [`crawler/src/scheduler/crawl_scheduler.py` (제거된 라인), `_bmad-output/implementation-artifacts/5-1-prometheus-메트릭-수집-및-grafana-대시보드-구성.md:321-327`]

- [ ] [Review][Patch][High] **`fit_markdown` 빈 문자열 시 정상 크롤이 silently drop** — `crawl4ai_crawler.py:227-231`에서 `md`가 str일 때(MarkdownGenerationResult 아닐 때) `fit_md=""` / `raw_md=str(md)`로 설정. scheduler `crawl_scheduler.py:274`의 `if not (result.fit_markdown or "").strip():` 가드는 `raw_markdown`이 있어도 무조건 skipped_empty. CrawlResult에 정의된 `effective_markdown` property(line 32)를 사용해야 함. **Fix:** scheduler `274` 라인을 `result.effective_markdown`로 교체 + 이후 validator/dedup 호출도 동일하게 통일. [`crawler/src/crawl4ai_crawler.py:225-231`, `crawler/src/scheduler/crawl_scheduler.py:274,284,301`]

- [ ] [Review][Patch][High] **`output/_tmp` 공유 디렉터리에서 이미지 파일명 충돌** — `Crawl4AICrawler`가 단일 인스턴스로 `output_dir="output/_tmp"`를 공유, `dest = dest_dir / f"img_{i:03d}{ext}"`가 사이트·포스트 간 재사용됨. 현재는 순차 실행이라 부분 우회되나, 두 번째 포스트의 storage가 첫 포스트의 잔여 파일을 본인 디렉터리에 옮겨 cross-post 이미지 오염 가능. **Fix:** `output_dir/<correlation_id>/`로 분리하거나 fetch당 임시 디렉터리 생성. [`crawler/src/crawl4ai_crawler.py:241, 290`, `crawler/src/scheduler/crawl_scheduler.py` _output_dir 초기화]

- [ ] [Review][Patch][High] **Bahamut sticky 정렬 깨짐: `_url_sort_key`가 querystring ID 미인식** — `findall(r"/(\d+)", url)` 정규식이 Bahamut `C.php?bsn=842&snA=12345`에 매치 안 됨 → 모든 URL이 sort_key=0으로 떨어져 sticky 포스트가 최신 포스트 위치에 섞임. **Fix:** sort_key 함수를 querystring fallback(예: `(?:\?|&)(?:tid|snA)=(\d+)` 추가)으로 확장. [`crawler/src/scheduler/crawl_scheduler.py:151-153`]

- [ ] [Review][Patch][High] **`_validate_id` 실패가 "기타 전송 실패"와 한 통계에 묶임** — 위 Critical-1과 결합 시 운영 알람·메트릭으로 "사이트 X 100% 실패"를 식별 불가. 일시 timeout과 영구 schema 실패가 같은 `failed` 카운터 사용. **Fix:** `_validate_id` ValueError를 별도 카운터(`stats.skipped_invalid_id`)로 분리 + WARN 로그에 사이트별 집계. [`crawler/src/scheduler/crawl_scheduler.py:325-332`, `crawler/src/storage.py:35-39`]

- [ ] [Review][Patch][High] **`UrlDedupChecker.cleanup_older_than` 호출 지점 없음 — ZSET 무한 증가** — 7일 TTL이 docstring·architecture에 약속되어 있으나 어떤 스케줄러도 cleanup을 호출하지 않음. **Fix:** APScheduler에 일일 cleanup job(`age_seconds=7*86400`) 등록. [`crawler/src/preprocessor/url_dedup_checker.py:67-77`, `crawler/src/scheduler/crawl_scheduler.py:382`]

- [ ] [Review][Patch][High] **tieba 홈페이지 redirect 탐지 임계값 500자가 nav/footer 포함 시 통과** — `content_validator.py:233`에서 `len(markdown) < 500` 만 검사 → 긴 nav가 있는 홈페이지가 통과 후 `回复/楼主/来自/签到` 매칭에 의해 `real`로 분류. **Fix:** URL 패턴 검사(`tieba.baidu.com/$` 또는 `tieba.baidu.com/f`)로 short-circuit. [`crawler/src/preprocessor/content_validator.py:233`]

- [ ] [Review][Patch][Medium] **`test_language_detector.py` / `test_serializer.py` 부재 (Story 2-3 미해결 review patch)** — Story 2-3 미해결 deferred 항목. PIVOT이 `serializer.to_crawl_event`에 `s3_text_path/s3_image_paths` kwarg를 추가했으나 dedicated 테스트 없음. **Fix:** 두 모듈에 unit test 추가 (language: `_LANG_MAP` 정규화 + seed 고정 / serializer: 모든 CrawlEvent 필드 매핑). [`_bmad-output/implementation-artifacts/2-3-콘텐츠-전처리-파이프라인-구현.md:156-157`]

- [ ] [Review][Patch][Medium] **`content_validator` PREFIX dispatcher가 `startswith`로 over-match** — `("ptt", validate_ptt)`가 `"pttsearch"` 같은 미래 site_id를 의도치 않게 잡음. **Fix:** PREFIX 매칭을 `site_id == prefix or site_id.startswith(prefix + "_")`로 제한. [`crawler/src/preprocessor/content_validator.py:3532-3540`]

- [ ] [Review][Patch][Medium] **`_brightdata_cn_proxy()`가 import-time 평가 — 환경변수 변경 무효** — 모듈 로드 시점에 한 번만 호출되어 freeze. 운영 중 secret rotation·대시보드 변경이 반영 안 됨. **Fix:** SiteConfig에 `proxy: Callable[[], dict | None] | dict | None`로 받고 fetch 시점에 평가. [`crawler/src/sites/registry.py:25-39, 334, 362`]

- [ ] [Review][Patch][Medium] **트리거 재진입 silently 폐기 — 대시보드 "trigger now" 무반응** — 진행 중 run이 있으면 `_run_locked`가 trigger를 단순 폐기. 사용자는 수동 트리거가 작동했다고 오해. **Fix:** 한 개의 pending trigger를 큐잉(boolean flag)하거나 응답 로그를 caller에게 노출. [`crawler/src/scheduler/crawl_scheduler.py:389-398`]

- [ ] [Review][Patch][Medium] **Bahamut/52pojie sticky 마커가 인용 본문 첫 800-1200자 안에 있으면 false positive** — 사용자가 공지/이벤트 텍스트를 본인 글 상단에 copy-paste하면 sticky로 오인식. **Fix:** sticky 판별 시 site별 selector(예: `.fixed-thread`) 검사 또는 본문 헤더와의 위치 관계 확인. [`crawler/src/preprocessor/content_validator.py:176-179, 192-208`]

- [ ] [Review][Patch][Low] **환경변수 `INTER_SITE_DELAY_SECONDS` / `MAX_POSTS_PER_BOARD` 파싱 try/except 없음** — 잘못된 값(`"15s"`, 빈 문자열) 시 import-time ValueError로 컨테이너 부팅 실패. **Fix:** try/except + 기본값 fallback + WARN 로그. [`crawler/src/scheduler/crawl_scheduler.py:30, 32, 34`]

- [ ] [Review][Patch][Low] **`bahamut_image_filter` 가 substring `"i.imgur.com"` 매칭 — `evil.com/i.imgur.com.thing.jpg` 통과** — 보안 영향은 낮지만 URL parsing 일관성 결여. **Fix:** `urllib.parse.urlparse(src).netloc == "i.imgur.com"`로 변경. [`crawler/src/sites/registry.py:4170-4173`]

- [ ] [Review][Patch][Low] **smoke_each_site.py가 폐기된 `crawler_test/` 경로 docstring 참조** — PIVOT으로 `crawler_test/`→`crawler/` 이름 변경 후 잔재. **Fix:** docstring 갱신. [`crawler/scripts/smoke_each_site.py:2577,2592`]

### Defer (사전 존재 이슈 / 본 PIVOT과 무관)

- [x] [Review][Defer] **`dedup_checker` whitespace-only difference로 해시 변동** — 본 PIVOT 도입 이전 동작. 별도 정규화 스토리에서 처리. [`crawler/src/preprocessor/dedup_checker.py:22-23`]
- [x] [Review][Defer] **trigger_listener reconnect storm (5s fixed)** — 본 PIVOT 외 안정화 항목. exponential backoff + jitter 별도 처리. [`crawler/src/scheduler/trigger_listener.py:66-71`]
- [x] [Review][Defer] **`urllib`로 image extension 결정 (Content-Type 무시)** — 본 PIVOT 외 storage 정밀도 항목. [`crawler/src/crawl4ai_crawler.py:289`]
- [x] [Review][Defer] **PTT/Dcard validator marker 조정 (False positive 가능성)** — 운영 데이터 수집 후 튜닝. [`crawler/src/preprocessor/content_validator.py:126-148`]

### Dismissed (10건)

스펙·맥락 일치하지 않거나 false positive로 판정 — `mark_seen` skip 경로(의도된 동작 ✓), `bahamut_image_filter` keyword 중복(영향 없음), pubsub `decode_responses` 가정(현 컨피그 일관), `output_dir` symlink loop(운영 외 경계 케이스), `_NC_GAME_KEYWORDS` 중복 항목(no-op), `headers=_TW_HEADERS` 공유 dict(아무도 mutate 안 함), `_url_dedup` decode_responses(현 컨피그 일관), `_run_lock` HA 가정(단일 인스턴스 명시), `language` 빈 문자열(downstream 처리 책임), `exclude_social_media_links` 기본값 차이(pipeline에서 SiteConfig가 source of truth).

### Summary

| Severity | Patch | Decision | Defer | Dismiss |
|---|---|---|---|---|
| Critical | 2 | 0 | 0 | - |
| High | 6 | 1 (Bahamut sticky 정렬 등 포함) | 0 | - |
| Medium | 5 | 0 | 1 | - |
| Low | 4 | 0 | 3 | - |
| **합계** | **17** | **1** | **4** | **10** |

**주요 위험:** Critical-1(`post_id_extractor` 미설정)은 운영 배포 시 4개 사이트(ptt/52pojie/bahamut/nga)의 모든 포스트가 silently fail. 142 PASS는 storage layer integration이 충분히 못 돌았기 때문으로 추정. PR 머지 전 반드시 fix 권장.
