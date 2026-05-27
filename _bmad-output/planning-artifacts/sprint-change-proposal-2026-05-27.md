---
title: Sprint Change Proposal — Epic 3 LLM 아키텍처 전면 재설계
date: 2026-05-27
author: Tracker (with BMad Correct Course workflow)
status: approved
workflow: bmad-correct-course
related_pivots:
  - 2026-05-19 Epic 2 crawler 전면 재작성 (forward-looking signal: architecture.md L88)
  - 2026-05-13 Story 4-7 모바일 지원 MVP 편입
  - 2026-05-09 단일 EC2 t3.xlarge 회귀
scope_classification: Major (PM/Architect — 본 문서 Section 5 참조)
---

# Sprint Change Proposal — Epic 3 LLM 아키텍처 전면 재설계 (2026-05-27)

## Section 1. Issue Summary

### 트리거
2026-05-27, sprint 진행 중 (`feat/epic3-detection` 브랜치에서 Story 3-2/3-3 review 단계) 다음 문제를 식별:

1. **Translation-Classification 2단 파이프라인의 복잡도** — VARCO Translation(중국어·번체 → 한국어) → VARCO LLM(불법 분류) 의 직렬 호출은 (a) 한 번의 게시글 처리에 2회 외부 API 호출 (b) 번역 품질 손실이 분류 단계로 전파 (c) 단일 vendor 의존이 양쪽 모두에 적용.
2. **이미지 첨부물 미분석** — 핵 UI 스크린샷·사설서버 광고 배너 등은 텍스트만으로 탐지되지 않아 false negative 발생. 기존 PRD에서 VARCO Vision은 Growth 단계로 이월되어 있어 MVP 범위 밖.
3. **카테고리 균등 처리의 사업적 불일치** — 게임 보안 도메인 특성상 핵·치트, 사설서버, 불법 프로그램 배포 같은 크리티컬 카테고리의 Recall이 사업적 가치의 대부분을 차지하나, 단일 임계값(0.70) + 단일 retry 정책(3회)으로는 자원 배분 효율이 낮음.

### 발견 경위
- 2026-05-19 Epic 2 PIVOT 등록 시 `architecture.md` L88에 **forward-looking signal — Epic 3 재설계 예정** 메모로 기 등록됨 (8일 전).
- 2026-05-27 Correct Course 사이클로 형식화하여 본 제안 작성.

### 사용자 결정 (Correct Course 인터뷰 결과)
1. **LLM 백엔드: OpenAI 단일 vendor 확정** — VARCO·DeepSeek 등 다른 백엔드 일체 제거. 옵션 A(GPT-4o/4.1 단일 멀티모달).
2. **PoC 일정: 1일 타임박스** — "최대한 빠르게, 안정성보다는 지금 하루만에 분석이 작동하도록".
3. **Story 번호: 신규 → 3-6** (LLM 백엔드 추상화 별도 스토리는 드롭, 텍스트/이미지 분리 가능성은 Story 3-3 AC에 흡수).
4. **기존 review 코드 처리: 재사용 부품(RetryHandler / TokenBucket / correlation_id) 추출 후 나머지 폐기**.

---

## Section 2. Impact Analysis

### Epic 영향

| Epic | 상태 | 영향 |
|------|------|------|
| Epic 1 | done | 영향 없음 |
| Epic 2 | in-progress | 영향 없음 (CrawlEvent 계약 안정) |
| **Epic 3** | **in-progress (PIVOT 대상)** | **전면 재설계 — 본 제안의 주 범위** |
| Epic 4 | done | 경미 — Story 3-4 follow-up으로 `DetectionResponse` + 목록 필터에 `tier` 필드 추가 (별도 단발 fix) |
| Epic 5 | in-progress | 경미 — Story 5-4 최종 정확도 검증 AC에 Tier별 confusion matrix + 비용 측정 추가 (현 backlog 상태이므로 본 제안 반영 시점에 같이 갱신) |

### Epic 3 스토리별 변경

| Story | 변경 전 | 변경 후 |
|-------|---------|---------|
| **SPIKE 3.0 (신규)** | — | 1일 타임박스, OpenAI 멀티모달 PoC, ≥30건 라벨셋 검증, 단가·latency·Tier 라우팅 프로토타입 |
| **3.1** | done (Redis 큐 소비자 + Watchdog) | 변경 없음 — LLM backend 무관 |
| **3.2** | review (VARCO Translation 연동) | **폐기.** review 코드 머지하지 않음. RetryHandler / TokenBucket / correlation_id 부품만 신규 3-3 PR에 재활용 |
| **3.3** | review (VARCO LLM 분류) | **전면 재작성.** OpenAI 멀티모달 단일 호출 + Tier 라우팅 + 텍스트/이미지 분리 호출 가능 인터페이스 + Tier 차등 retry + 일일 비용 cap |
| **3.4** | backlog (RDS 저장) | **AC 확장.** `tier` / `image_observed` / `token_usage_json` / `cost_usd` 필드 + Flyway V5 마이그레이션 + `idx_detections_filter` 확장 + `model_version` 포맷 변경 |
| **3.5** | backlog (정확도 사전 측정) | **AC 확장.** 라벨셋 ≥300건(Tier별 ≥75건) + Tier별 confusion matrix + 게시글당 평균 비용 측정 + 라이브 검증 별도 기록 |
| **3.6 (신규)** | — | Tier 기반 알림(T1 즉시 + 사람 리뷰 큐 / T2 다이제스트 / T3 주간 / T4 통계만) + Tier 보존 정책(T1 영구 / T2·T3 90일 / T4 즉시 폐기) + 이미지 PII 토글 |

### 산출물 충돌 및 갱신

#### PRD (`_bmad-output/planning-artifacts/prd.md`)
- **§ AI 탐지 FR 섹션 (L405-422)**: FR11 폐기 / FR12·FR13·FR15·FR16 수정 / FR16-NEW-1/2/3 추가
- **§ Success Criteria (L73-81)**: 단일 Precision/Recall → Tier별 Recall (T1 ≥0.85 / T2 ≥0.70 / T3 ≥0.55) + 게시글당 평균 비용 ≤ $0.005 + 라벨셋 ≥300건
- **§ MVP 정의 (L124, L128)**: VARCO Translation + VARCO LLM → 멀티모달 LLM 분류 + Tier 라우팅
- **§ Growth Features (L135)**: VARCO Vision MVP 편입, BERT 보류
- **§ 탐지 오류 관리 + 데이터 보관 정책 (L213-219)**: 단일 0.70 임계값 → Tier별 차등 임계값; 보관 정책 Tier 기반 갱신
- **§ Risks (L250)**: VARCO 관련 4행 → OpenAI 의존 4행 (단일 vendor / 비용 폭증 / T1 FP / 이미지 PII)
- **§ NFR**: NFR3·NFR5·NFR11·NFR14 갱신 + Executive Summary / What Makes Special / Project Classification / Innovation 등 잔여 VARCO 참조 정리

#### Architecture (`_bmad-output/planning-artifacts/architecture.md`)
- **L88 forward-looking 메모**: "실현됨"으로 갱신 + 결정 사항 (a)~(f) 명시
- **L29 AI 탐지 행 / L41 통합 NFR 행**: OpenAI 멀티모달 + Tier 라우팅 + LLM 토큰 버킷
- **L53-58 Technical Constraints**: VARCO 4행 → OpenAI + 비용 cap, BERT 해소
- **L66 LLM Mock 서버 (이전 VARCO Mock)**: `llm_mock.py` 재구축
- **L72 처리 병목**: Vision 단계 → 멀티모달 LLM 호출 (이미지 토큰 단가 + 비용 cap)
- **L197 / L273 LLM 장애 처리**: VARCO → OpenAI + Tier 차등 retry
- **L220-221**: BERT 보류 / Vision MVP 편입
- **L290 EC2 사이징 Detection**: t4g.medium 유지 (BERT 보류로 업사이징 조건 해소)
- **L577-608 `detection/` 디렉터리 트리**: translate.py 폐기 / llm_client.py · tier_router.py · cost_cap.py · tier_config.py · notification/ · retention/ 신설 / varco_mock.py → llm_mock.py
- **L782-783 파이프라인 도식**: VARCO Translation → VARCO LLM → 단일 멀티모달 호출 + Tier 라우팅
- **L357 / L764 Redis 패턴**: `varco:rate_limit` → `llm:rate_limit`

#### Epics (`_bmad-output/planning-artifacts/epics.md`)
- **§ Epic 3 overview (L166)**: 전면 재설계 + Story 변경 요약 + Party Mode 메모 재정렬
- **§ Epic 3 Detail (L537)**: PIVOT 헤더 + 스토리 변경 요약 + SPIKE 3.0 신규 + Story 3.2 폐기 노트 + Story 3.3 재작성 + Story 3.4/3.5 AC 확장 + Story 3.6 신규

#### Sprint Status (`_bmad-output/implementation-artifacts/sprint-status.yaml`)
- last_updated 2026-05-19 → 2026-05-27
- Epic 3 항목 갱신 + 신규 항목 `3-0-spike-openai-멀티모달-poc`, `3-6-tier-기반-알림-및-보존-정책` 추가
- Story 3-2 status `review` → `deprecated`
- Story 3-3 키 이름 `varco-llm-분류-...` → `openai-멀티모달-llm-분류-tier-라우팅`, status `review` → `backlog` (재작성 대기)
- Story 3-5 키 이름 갱신 (Tier 표시)

#### 코드베이스 영향 (참고 — 실 구현은 본 제안 승인 후 별도 sprint 작업)
- `detection/src/pipeline/translate.py` — 삭제
- `detection/src/pipeline/llm_classifier.py` — 재작성
- `detection/src/pipeline/llm_client.py`, `tier_router.py` — 신규
- `detection/src/rate_limit/cost_cap.py` — 신규
- `detection/src/config/tier_config.py` — 신규
- `detection/src/notification/` (t1_notifier.py / digest_scheduler.py / weekly_report.py) — 신규
- `detection/src/retention/tier_retention_job.py` — 신규
- `detection/src/mocks/varco_mock.py` → `llm_mock.py` — rename + 재구현
- `shared/interfaces/varco.py` → `llm.py` — Protocol 갱신
- `tests/fixtures/labels/manual_label_set_v2.csv` — ≥300건 (Tier별 ≥75) 신규 작성, 이미지 첨부 ≥50건
- `tests/fixtures/labels/manual_label_set_spike.csv` — SPIKE 3.0용 ≥30건
- `api/.../Detection.java` + `DetectionResponse.java` — `tier` 필드 추가 (Epic 4 follow-up)
- Flyway: `V5__add_tier_columns.sql`, `V6__add_retention_columns.sql`
- `infra/.env.example` — `OPENAI_API_KEY`, `LLM_MODEL`, `LLM_DAILY_COST_CAP_USD`, `LLM_WORKER_COUNT`, `LLM_SEND_IMAGES`, `LLM_SPLIT_TEXT_IMAGE`, `T1_NOTIFICATION_CHANNEL` 추가

---

## Section 3. Recommended Approach

### 선택된 path: **Direct Adjustment + 부분 Rollback (Hybrid)**

- **Rollback**: Story 3-2 review 코드 (Translator 본체) + Story 3-3 review 코드의 VARCO 직결 부분을 머지하지 않고 폐기. 옛 코드는 git history(브랜치 머지 전 마지막 review commit)로 보존.
- **Direct Adjustment**: SPIKE 3.0 신규 + Story 3-3 전면 재작성 + Story 3-4/3-5 AC 확장 + Story 3-6 신규. Story 3-1, 3-2의 재사용 부품(RetryHandler / TokenBucket / correlation_id 전파)은 유지하여 손실 최소화.

### 정당화
1. **사전 신호된 PIVOT의 형식화** — architecture.md L88 (2026-05-19 등록)에서 이미 동일 재설계가 예고됨. 본 제안은 "Failed approach"라기보다 strategic pivot의 정형화.
2. **사업 가치 정렬** — T1 카테고리 Recall 집중은 게임 보안 도메인의 명확한 우선순위와 일치.
3. **파이프라인 단순화** — 2단(Translation + Classification) + 별도 Vision 단계 3개를 단일 멀티모달 호출로 통합 → 운영·디버깅·테스트 부담 감소.
4. **단일 vendor 의존은 수용 리스크** — 사용자 명시 결정. 비용 cap + 일일 모니터링 + 큐 대기(Hold) fallback이 1차 통제.

### 대안 검토 (모두 기각)
- **Option B (DeepSeek + Vision 분리)**: 사용자가 "OpenAI 하나만" 명시. 기각.
- **Option C (VARCO 유지 + 멀티모달만 추가)**: 사용자가 VARCO 완전 제거 결정. 기각.
- **Full Rollback (Story 3-1까지 회귀)**: 3-1은 LLM backend 무관, 회귀 가치 0. 기각.

### 추정 노력 / 리스크 / 일정 영향
- **SPIKE 3.0**: 1일 (사용자 명시)
- **Story 3-3 재작성**: 3-5일 (재사용 부품 보유 가정)
- **Story 3-4 AC 확장**: 1-2일 (Flyway 마이그레이션 + API 레이어 follow-up)
- **Story 3-5 AC 확장**: 라벨셋 ≥300건 준비 2-3일 + 측정 1일
- **Story 3-6 신규**: 3-5일 (알림 채널 미정 시 토글로 우선 구현)
- **총 추정**: SPIKE 1d + 본 구현 8-14d → 최대 3주 (라벨셋 준비 병행 가능 시 2주)
- **Risk**: Medium-High (OpenAI 비용 cap 운영 안정화 + 이미지 PII 법무 결정 + T1 알림 채널 운영팀 협의 — 3개 모두 외부 의존)

---

## Section 4. Detailed Change Proposals

본 섹션의 모든 편집은 **이미 파일에 반영 완료**되었습니다. 아래는 PIVOT 추적용 요약 목록입니다.

### 4.1 PRD 갱신 (반영 완료)
- AI 탐지 FR (FR11 폐기, FR12·FR13·FR15·FR16 수정, FR16-NEW-1/2/3 추가) + Tier-aware Success Criteria + MVP 정의 + Growth Features + 탐지 오류 관리 + 데이터 보관 정책 + Risks 표 + 잔여 VARCO 참조 sweep (Executive Summary / What Makes Special / Project Classification / Innovation / 경쟁환경 / 검증 접근법 / Project-Type / Redis 역할 / MVP 기능 표 / Post-MVP / Tech Risks / NFR3·5·11·14)

### 4.2 Architecture 갱신 (반영 완료)
- L29 AI 탐지 행, L40-41 신뢰성/통합 행, L53-58 Technical Constraints, L62-66 Redis 역할 + LLM Mock 서버, L72 처리 병목, L88 forward-looking → 실현됨, L103 detection/ 한 줄, L197 / L273 LLM 장애 처리, L220-221 BERT/Vision, L237 시크릿, L290 EC2 사이징 Detection, L311 mocks, L357·L764 Redis 키, L577-608 detection/ 디렉터리 트리, L782-783 파이프라인 도식

### 4.3 Epics 갱신 (반영 완료)
- L166 Epic 3 overview, L537 Epic 3 detail + SPIKE 3.0 신규, Story 3.2 폐기, Story 3.3 재작성, Story 3.4 Tier 확장, Story 3.5 Tier 확장, Story 3.6 신규

### 4.4 Sprint Status 갱신 (반영 완료)
- last_updated 2026-05-27 + Epic 3 메모 헤더 + 항목 키 변경 + 신규 항목

---

## Section 5. Implementation Handoff

### Scope Classification: **Major**
- 근거: PRD 핵심 가정(번역 단계 / 균등 처리) 변경 + 아키텍처 detection 디렉터리 전면 재구성 + 외부 의존성(VARCO → OpenAI) 교체 + NC AI 협력 관계 영향 + reviewed-but-unmerged 코드 폐기

### 라우팅
- **Primary owner**: PM / Solution Architect (본 제안 승인 + NC AI / 법무 / 운영팀 소통)
- **Implementation owners (Developer agents)**:
  - **AI 담당자(일드매)**: SPIKE 3.0 (1일) → Story 3-3 재작성 → Story 3-5 Tier별 측정
  - **백엔드(최병주)**: Story 3-4 Flyway V5 + DetectionResponse `tier` 필드 + Epic 4 follow-up (`/detections` 필터에 `tier` 추가)
  - **인프라/운영(박재성)**: Story 3-6 알림 채널 운영팀 협의 + 이미지 PII 법무 협의 + 비용 cap 모니터링 셋업
- **QA owner**: 라벨셋 ≥300건 준비 (Tier별 ≥75건, 이미지 첨부 ≥50건) — Story 3-5 입력

### 외부 의존 / 미해결 항목
1. **OpenAI 계정 + API 키 발급** — SPIKE 3.0 착수 전제. GitHub Secrets + `infra/.env.example` 갱신.
2. **NC AI 보고** — VARCO 의존 제거 통보. 협력 관계는 게임 보안 도메인 자문으로 재정의.
3. **T1 알림 채널** — 운영팀 협의 (Slack / 이메일 / 모바일 푸시 / 사내 대시보드 알림 등). Story 3-6 진입 전 결정 권장. 결정 전에는 환경변수 토글로 비활성화.
4. **이미지 PII OpenAI 전송 컴플라이언스** — 법무 검토 결과에 따라 (a) 그대로 전송 (b) 이미지 마스킹 (c) 텍스트-only fallback. `LLM_SEND_IMAGES` 환경변수 토글로 즉시 차단 가능.
5. **일일 비용 cap 초기값** — SPIKE 3.0 단가 측정 결과로 결정. 예시: $5/day 시작 + 실 운영 데이터로 조정.

### 성공 기준
- SPIKE 3.0: 1일 안에 30건 라벨셋에 대해 동작 검증 + 단가/latency 측정 결과 문서화.
- Story 3-3 본 구현: Tier별 차등 retry + 일일 비용 cap + 텍스트/이미지 분리 호출 가능 인터페이스로 머지.
- Story 3-5: 라벨셋 ≥300건 기반 Tier별 confusion matrix 산출, Precision ≥ 0.80 / T1 Recall ≥ 0.80 통과.
- Story 3-6: T1 알림(채널 미정이면 토글로 비활성화) + Tier 보존 정책 + 이미지 PII 토글 동작.

### 다음 단계
1. 본 제안 승인 → sprint-status.yaml의 `3-0-spike-openai-멀티모달-poc` 항목을 `ready-for-dev`로 이동.
2. SPIKE 3.0 결과 (`docs/llm-spike-2026-05-27.md`)를 입력으로 Story 3-3 본 구현 착수.
3. NC AI / 법무 / 운영팀에 본 제안 사본 공유 (PM 책임).

---

## 부록 A. Checklist (BMad Correct Course)

| Section | Status | Notes |
|---------|--------|-------|
| §1 Trigger context | [x] Done | 트리거 + 발견 경위 + 사용자 결정 명시 |
| §2 Epic impact | [x] Done | Epic 1-5 + Story별 변경 표 |
| §3 Artifact conflicts | [x] Done | PRD / Architecture / Epics / Sprint Status / 코드베이스 영향 |
| §4 Path forward | [x] Done | Direct Adjustment + 부분 Rollback (Hybrid) — 정당화 + 대안 기각 + 노력/리스크/일정 |
| §5 Proposal components | [x] Done | Issue Summary + Impact Analysis + Recommended Approach + Detailed Changes + Handoff |
| §6 Final review | [pending] | 사용자 승인 대기 — 본 문서 작성과 동시에 산출물 편집 적용 완료 |

## 부록 A-1. 추가 명시 (2026-05-27 post-approval)

본 제안 승인 직후, 외국어 게시글의 한국어 번역문 표시 요구가 추가로 명시되었다 (PRD User Journey 1 + Story 4.2 `translatedText` 계약과 정합).

**해결**: FR11을 단순 폐기에서 **"OpenAI 멀티모달 호출 응답 스키마의 `translated_text_ko` 필드로 흡수"**로 재정의. 분류·`reason_ko`·번역을 단일 호출로 동시 산출하여 별도 Translation API 없이 처리.

### 영향 (추가 변경 분)
- **PRD FR11**: 폐기 → 재정의 (`translated_text_ko` 필드로 흡수, 한국어 원문은 null)
- **PRD Risks 표**: "번역 품질 — OpenAI 단독 의존" 행 추가 (SPIKE에서 spot-check, 오역 시 별도 호출 분기 옵션 검토)
- **Epics Story 3-3 AC**: response schema에 `translated_text_ko: str | null` 필드 추가
- **Epics Story 3-4 AC**: `detections.translated_text_ko TEXT` 컬럼 추가, Flyway V5 마이그레이션에 포함, Spring API `DetectionResponse.translatedText` 직접 매핑
- **Architecture L88**: "결정 사항 (b)"에 번역 흡수 명시
- **Architecture L782 파이프라인 도식**: 단일 호출 산출물에 `translated_text_ko` 명시
- **SPIKE 3.0 spot-check**: 외국어 게시글 ≥15건 번역 품질 운영자 확인

### 동작 요약
| 원문 언어 | translated_text_ko 동작 |
|---|---|
| 한국어 | `null` (번역 스킵) |
| 중국어 간체 (zh-CN) | OpenAI가 한국어 번역 산출 |
| 중국어 번체 (zh-TW) | OpenAI가 한국어 번역 산출 |
| 영어·기타 | OpenAI가 한국어 번역 산출 |
| 이미지 속 외국어 텍스트 | 본문 번역에 통합 또는 별도 단락으로 포함 (프롬프트 명시) |

대시보드 표시: Story 4-5에서 이미 구현된 `BilingualPanel`(C7) 컴포넌트가 원문·번역문 동시 표시를 지원하므로 frontend 변경 없음.

---

## 부록 A-2. 전수 저장 정책 (2026-05-27 post-approval, 2회차)

크롤 볼륨이 낮으므로 임계값 미달·T4·`is_illegal=false`까지 모두 RDS에 저장하는 구조로 변경.

### 동기
- 크롤 7개 활성 사이트 × 시간당 수십~수백 건 → 11주 누적 수만~수십만 건 (저장 비용 무시 가능)
- 전수 저장 가치: 디버깅 / 라벨셋 확장 / 오탐 분석 / Recall 측정 분모

### 변경 사항
| 항목 | 기존 (PIVOT 1차) | 변경 (post-approval 2차) |
|---|---|---|
| 임계값 미만 분류 결과 | RDS 저장 스킵 + 통계만 | **전수 저장**. 임계값은 대시보드 디스플레이 필터로만 작동 |
| T4 Low 보존 | 즉시 폐기 | **90일 보존 후 archive** (T2·T3와 동일) |
| `is_illegal=false` 분류 | 명시 안 됨 | **저장 (모든 Tier 동일 보존 기간)** |
| API 임계값 미만 조회 | 불가 | `?show_below_threshold=true` 또는 동등 파라미터로 QA 리뷰 모드 노출 |
| 비용 cap (`LLM_DAILY_COST_CAP_USD`) | 안전장치 | **더 중요해짐** — 모든 게시글에 LLM 호출 |

### 영향 산출물
- **PRD FR13 / FR22 / FR16-NEW-3 / 데이터 보관 정책**: 전수 저장 + T4 90일 보존 명시
- **Epics Story 3-3 AC**: "tier_low_confidence 통계만 남기고 RDS 저장 스킵" 행 제거, `posts`/`detections` 1:1 전수 저장 명시
- **Epics Story 3-6 AC**: T4 즉시 폐기 → T4 90일 archive, `is_illegal=false` 보존 명시, T4 대시보드 미노출 (QA 리뷰만)

### 유지되는 사전 필터 (변경 없음)
- `content_validator` 8-kind 가드 (sticky/auth_wall/captcha/empty/short/error/unknown) — 진짜 게시글이 아니므로 차단 유지
- `url_dedup_checker` + `dedup_checker` — 동일 게시글 중복 제거 유지

### 미해결 / 향후 재검토
- T4 90일 보존이 운영 데이터 누적 시 비용·관리 부담을 일으키면 폐기 주기 재조정 가능
- QA 리뷰 모드 API 파라미터 정확한 형태는 Story 3-4 follow-up + Epic 4 후속에서 결정

---

## 부록 B. 관련 PIVOT 메모 체인

| 날짜 | PIVOT | 본 PIVOT과의 관계 |
|------|-------|-----------------|
| 2026-04-28 | crawl4ai 라이브러리 전환 | Epic 2 — 무관 |
| 2026-05-06 | Terraform IaC 폐기 → ClickOps | Epic 5 인프라 — 무관 |
| 2026-05-09 | 단일 t3.xlarge 16GB 회귀 | 인프라 — Detection EC2 t4g.medium 결정값 영향 없음 |
| 2026-05-13 | Story 4-7 모바일 지원 MVP 편입 | Epic 4 — 무관 |
| 2026-05-19 | Epic 2 crawler 전면 재작성 | Epic 2 — 본 PIVOT의 forward-looking signal (architecture.md L88) 등록 |
| 2026-05-20 | tieba/nga "P3 (disabled)" 격하 (Bright Data CN PoC 실패) | Epic 2 — 입력 corpus 축소 영향 인지, Epic 3 LLM 변경과 직접 무관 |
| **2026-05-27** | **Epic 3 LLM 아키텍처 전면 재설계 (본 제안)** | **현재** |
