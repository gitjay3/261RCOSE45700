# BMad 사용법

> 막히면 언제든 `/bmad-help` — 현재 상태에 맞춰 다음 스킬을 추천해 줍니다.
> ⚠️ **각 단계를 시작할 때는 항상 새 대화창을 열어서 시작하는 걸 권장합니다.**

---

## 📚 목차

- [BMad 사용법](#bmad-사용법)
  - [📚 목차](#-목차)
  - [Part 1. 단계별 흐름](#part-1-단계별-흐름)
    - [1. 브레인스토밍](#1-브레인스토밍)
    - [2. `[CP]` Create PRD (필수)](#2-cp-create-prd-필수)
    - [3. `[CU]` Create UX](#3-cu-create-ux)
    - [4. Web Design Studio (wds)](#4-web-design-studio-wds)
    - [5. `[CA]` Create Architecture](#5-ca-create-architecture)
    - [6. `[CE]` Create Epics \& Stories](#6-ce-create-epics--stories)
    - [7. `[IR]` Implementation Readiness](#7-ir-implementation-readiness)
    - [8. `[SP]` Sprint Planning](#8-sp-sprint-planning)
    - [9. 반복 사이클 (`CS → VS → DS → CR`)](#9-반복-사이클-cs--vs--ds--cr)
    - [10. `[QA]` QA Automation · `[ER]` Retrospective](#10-qa-qa-automation--er-retrospective)
  - [Part 2. 보조 도구 (anytime)](#part-2-보조-도구-anytime)
  - [Part 3. 역할별 BMad 사용법](#part-3-역할별-bmad-사용법)
    - [🎯 PM / 기획](#-pm--기획)
    - [🕷️ 크롤링 담당](#️-크롤링-담당)
    - [🤖 AI / 탐지 담당](#-ai--탐지-담당)
    - [🖥️ 백엔드](#️-백엔드)
    - [🎨 인프라 / 프론트엔드](#-인프라--프론트엔드)
    - [🧪 QA](#-qa)
  - [Part 4. 역할 ↔ 에픽 매핑](#part-4-역할--에픽-매핑)
  - [부록. 명령어 한 줄 요약표](#부록-명령어-한-줄-요약표)
    - [핵심 워크플로우](#핵심-워크플로우)
    - [테스트 (TEA)](#테스트-tea)
    - [보조 도구](#보조-도구)
    - [에이전트 (페르소나)](#에이전트-페르소나)

---

## Part 1. 단계별 흐름

```
[1] 브레인스토밍 → [2] PRD → [3] UX → [4] wds → [5] Architecture
                                                      ↓
[10] QA / Retro ← [9] CS→VS→DS→CR (반복) ← [8] Sprint Planning ← [7] IR ← [6] Epics & Stories
```

### 1. 브레인스토밍

**언제**: 아이디어 발산·구체화 단계.

| 명령어 | 용도 |
|---|---|
| `/bmad-brainstorming` | 발산 사고 facilitator로 시작 |
| `/bmad-market-research` | 시장·경쟁사·고객 분석 |
| `/bmad-technical-research` | 기술 타당성·아키텍처 옵션 비교 |
| `/bmad-domain-research` | 도메인 지식 조사 |
| `/bmad-party-mode` | 여러 에이전트가 한 자리에서 토론 |

**Creative Method (`/bmad-cis-...`)** — 필요 시 활용:

- **Stakeholder Round Table** — 이해관계자 페르소나 관점 모아 균형 잡힌 요구 도출
- **Expert Panel Review** — 도메인 전문가 패널로 동료 검토 수준 분석
- **Debate Club Showdown** — 찬반 논쟁으로 절충안 탐색
- **User Persona Focus Group** — 사용자 페르소나가 제안에 반응·우선순위 제시
- **Design Thinking** (`/bmad-cis-design-thinking`) — 공감 기반 인간 중심 설계
- **Innovation Strategy** (`/bmad-cis-innovation-strategy`) — 디스럽션 기회·BM 혁신

---

### 2. `[CP]` Create PRD (필수)

**언제**: 만들 게 정해지고 요구사항을 문서화할 때.

| 명령어 | 용도 |
|---|---|
| `/bmad-create-prd` | PRD 처음부터 작성 (John, PM 에이전트) |
| `/bmad-validate-prd` | PRD 표준 준수 검증 |
| `/bmad-edit-prd` | 기존 PRD 수정 |

---

### 3. `[CU]` Create UX

**언제**: Frontend 개발에 필요한 UX 단계 진행 시.

- `/bmad-create-ux-design` — UX 패턴·UI 사양 설계
- 에이전트: **Sally** (UX designer)

---

### 4. Web Design Studio (wds)

**언제**: 대시보드 등 UI 중심 FE 설계가 필요할 때.

- `/bmad-help` 로 wds 사용법 확인 후 단계별 진행

---

### 5. `[CA]` Create Architecture

**언제**: PRD가 있고 "어떻게 만들지"를 정할 때.

- `/bmad-create-architecture` — API·모델·배포 등 FE/BE 경계 정리
- 에이전트: **Winston** (architect)

---

### 6. `[CE]` Create Epics & Stories

**언제**: 요구사항을 에픽/유저스토리로 분해할 때.

- `/bmad-create-epics-and-stories` — FE/BE 작업을 스토리로 분리

---

### 7. `[IR]` Implementation Readiness

**언제**: 구현 들어가기 직전 정합성 검증.

- `/bmad-check-implementation-readiness` — PRD / UX / Architecture / Epics 정합성 체크

---

### 8. `[SP]` Sprint Planning

**언제**: 에픽들을 스프린트 단위로 묶을 때.

| 명령어 | 용도 |
|---|---|
| `/bmad-sprint-planning` | 스프린트 계획 수립 |
| `/bmad-sprint-status` (`[SS]`) | 진행 현황 점검 (anytime) |

---

### 9. 반복 사이클 (`CS → VS → DS → CR`)

**언제**: 스프린트 시작 후 스토리 단위로 구현·리뷰 반복.

| 명령어 | 용도 |
|---|---|
| `/bmad-create-story` | 다음(또는 지정) 스토리 컨텍스트 파일 생성 |
| `/bmad-create-story` (validate 모드) | 스토리 준비도 검증 |
| `/bmad-dev-story` | 스토리 명세대로 코드 구현 (Amelia) |
| `/bmad-code-review` | 멀티 레이어 적대적 코드 리뷰 |
| `/bmad-quick-dev` (`[QQ]`) | 풀 사이클 우회, 작은 단발 작업 빠르게 |
| `/bmad-correct-course` (`[CC]`) | 큰 요구사항 변경 시 코스 재조정 |

**진행 순서**: Sprint Plan 기준으로 **1-1 → 1-2 → 1-3 → epic-1-retrospective → 2-1 …**
**팁**: 중간중간 backend / frontend 올려보며 동작 확인하면서 진행.

---

### 10. `[QA]` QA Automation · `[ER]` Retrospective

**언제**: 기능 구현이 끝나면 자동 테스트, 에픽이 끝나면 회고.

| 명령어 | 용도 |
|---|---|
| `/bmad-qa-generate-e2e-tests` | 구현된 기능에 API/E2E 자동 테스트 생성 |
| `/bmad-retrospective` | 에픽 종료 회고 (선택) |

**TEA 모듈로 테스트 품질을 더 챙기려면**:

| 명령어 | 용도 |
|---|---|
| `/bmad-testarch-framework` (`[TF]`) | 테스트 프레임워크 초기화 |
| `/bmad-testarch-test-design` (`[TD]`) | 리스크 기반 테스트 설계 |
| `/bmad-testarch-atdd` (`[AT]`) | red-phase 인수 테스트 스캐폴드 |
| `/bmad-testarch-automate` (`[TA]`) | 테스트 자동화 확장 |
| `/bmad-testarch-nfr` (`[NR]`) | 비기능(성능·보안·신뢰성) 평가 |
| `/bmad-testarch-test-review` (`[RV]`) | 테스트 품질 감사 (0~100점) |
| `/bmad-testarch-trace` (`[TR]`) | 트레이서빌리티 매트릭스 + 게이트 결정 |
| `/bmad-testarch-ci` (`[CI]`) | CI/CD 품질 파이프라인 구성 |

---

## Part 2. 보조 도구 (anytime)

어느 단계에서든 호출 가능.

| 명령어 | 용도 |
|---|---|
| `/bmad-checkpoint-preview` (`[CK]`) | 변경 사항 사람이 검토하기 전 가이드 워크스루 |
| `/bmad-review-adversarial-general` (`[AR]`) | 산출물 마감 전 냉소적 QA |
| `/bmad-review-edge-case-hunter` (`[ECH]`) | 모든 분기·경계 조건 점검 |
| `/bmad-shard-doc` (`[SD]`) | 큰 문서(>500줄) 섹션별 분할 |
| `/bmad-index-docs` (`[ID]`) | 폴더 안 모든 문서를 index.md로 정리 |
| `/bmad-distillator` (`[DG]`) | 문서 손실 없이 LLM용으로 압축 |
| `/bmad-editorial-review-prose` | 글 품질 리뷰 (3열 표로 수정안) |
| `/bmad-editorial-review-structure` | 문서 구조 리뷰 (재배치·축약 제안) |
| `/bmad-document-project` (`[DP]`) | 기존 코드베이스(brownfield) 정리 |
| `/bmad-generate-project-context` (`[GPC]`) | 코드베이스 → LLM 컨텍스트 추출 |

---

## Part 3. 역할별 BMad 사용법

> 기획서 7.2 역할 분담 기준. 본인 영역 스토리 진행 시 아래 스킬을 우선 사용.

### 🎯 PM / 기획

> 기획서 관리, NC AI 멘토 소통, 일정 조율, BMAD PM 에이전트 운용.

| 명령어 | 언제 |
|---|---|
| `/bmad-agent-pm` | 요구사항 도출·정리 (John) |
| `/bmad-create-prd` → `/bmad-validate-prd` → `/bmad-edit-prd` | PRD 작성·검증·수정 |
| `/bmad-sprint-planning` / `/bmad-sprint-status` | 스프린트 계획·상태 점검 |
| `/bmad-correct-course` | 멘토 피드백·요구사항 큰 변경 시 |
| `/bmad-retrospective` | 에픽 종료 회고 |
| `/bmad-checkpoint-preview` | 주요 변경 검토 |
| `/bmad-help` | 어디서 막혔는지 모를 때 첫 호출 |

---

### 🕷️ 크롤링 담당

> 스텔스 브라우저, FlareSolverr, 프록시, APScheduler, S3 연동, 이미지 수집, (옵션 A 시) 전처리 모듈.

| 명령어 | 언제 |
|---|---|
| `/bmad-technical-research` | Cloudflare 우회 가능성·프록시 비교 검증 (Story 2-1 등) |
| `/bmad-agent-dev` | Amelia(dev)와 페어 코딩 |
| `/bmad-create-story` → `/bmad-dev-story` → `/bmad-code-review` | **Epic 2** 전체 반복 사이클 |
| `/bmad-quick-dev` | 어댑터 추가, 셀렉터 수정 등 단발 작업 |
| `/bmad-testarch-atdd` | 크롤러 동작 인수 테스트 (red-phase) |
| `/bmad-review-edge-case-hunter` | IP 차단·봇 감지·레이아웃 변경 등 경계 케이스 점검 |

---

### 🤖 AI / 탐지 담당

> VARCO LLM·Translation·Vision API 연동, 탐지 파이프라인 구현.

| 명령어 | 언제 |
|---|---|
| `/bmad-technical-research` | BERT 도입 여부·모델 선정 (10.1절 결정 항목) |
| `/bmad-agent-dev` | Amelia와 함께 파이프라인 구현 |
| `/bmad-create-story` → `/bmad-dev-story` → `/bmad-code-review` | **Epic 3** 전체 반복 사이클 |
| `/bmad-testarch-nfr` | VARCO API 응답 시간·rate limit·F1 비기능 평가 |
| `/bmad-cis-problem-solving` | 모호 케이스 분류 전략·프롬프트 설계 막힐 때 |

---

### 🖥️ 백엔드

> Java Spring 서버, RDS 스키마, Prometheus·Grafana 구성.

| 명령어 | 언제 |
|---|---|
| `/bmad-agent-architect` | API 설계 상의 (architecture.md 변경 시에만) |
| `/bmad-agent-dev` | Amelia와 Spring 구현 |
| `/bmad-create-story` → `/bmad-dev-story` → `/bmad-code-review` | **Epic 1**(1-2, 1-4), **Epic 4**(4-1~4-3), **Epic 5**(5-1) |
| `/bmad-qa-generate-e2e-tests` | REST API E2E 테스트 자동 생성 |
| `/bmad-testarch-test-design` | Redis 큐·Watchdog 등 리스크 기반 테스트 설계 |

---

### 🎨 인프라 / 프론트엔드

> GitHub Actions CI/CD, AWS 환경 구성, 대시보드 구현, 화면 설계.

| 명령어 | 언제 |
|---|---|
| `/bmad-agent-ux-designer` | Sally(UX)와 화면 흐름 상의 |
| **Web Design Studio (wds)** | 대시보드 UI 중심 설계 시 (`/bmad-help`로 진입법 확인) |
| `/bmad-create-ux-design` | UX 패턴·컴포넌트 사양 정리 |
| `/bmad-agent-dev` | Amelia와 React 구현 |
| `/bmad-create-story` → `/bmad-dev-story` → `/bmad-code-review` | **Epic 1**(1-1, 1-3, 1-5), **Epic 4**(4-4~4-6), **Epic 5**(5-2, 5-3) |
| `/bmad-testarch-ci` | GitHub Actions 품질 파이프라인 구성 |
| `/bmad-testarch-framework` | 프론트 테스트 프레임워크(Playwright 등) 초기화 |

---

### 🧪 QA

> 수동 라벨링 데이터셋 구축, F1 Score 검증, 통합 테스트, 버그 수정.

| 명령어 | 언제 |
|---|---|
| `/bmad-tea` | Murat(test architect)와 QA 전략 상의 |
| `/bmad-testarch-test-design` | 리스크 기반 통합 테스트 설계 |
| `/bmad-testarch-automate` | 테스트 자동화 커버리지 확장 |
| `/bmad-testarch-nfr` | F1 Score·정확도·성능 비기능 평가 |
| `/bmad-testarch-test-review` | 테스트 품질 감사 (0~100점) |
| `/bmad-testarch-trace` | 요구사항 ↔ 테스트 트레이서빌리티 매트릭스 |
| `/bmad-qa-generate-e2e-tests` | 구현 완료 기능 E2E 자동 테스트 생성 |
| `/bmad-code-review` | 스토리 구현 후 멀티 레이어 코드 리뷰 |
| `/bmad-review-adversarial-general` | 라벨링 데이터셋·F1 보고서 등 산출물 냉소적 검토 |

---

## Part 4. 역할 ↔ 에픽 매핑

| 역할 | 주력 에픽·스토리 | 주요 BMad 에이전트 |
|---|---|---|
| 🎯 PM / 기획 | 전체 | John (`bmad-agent-pm`) |
| 🕷️ 크롤링 | **Epic 2** 전체 | Amelia (`bmad-agent-dev`) |
| 🤖 AI / 탐지 | **Epic 3** 전체 | Amelia (`bmad-agent-dev`) |
| 🖥️ 백엔드 | Epic 1 (1-2, 1-4) · Epic 4 (4-1~4-3) · Epic 5 (5-1) | Winston (`bmad-agent-architect`), Amelia |
| 🎨 인프라 / 프론트 | Epic 1 (1-1, 1-3, 1-5) · Epic 4 (4-4~4-6) · Epic 5 (5-2, 5-3) | Sally (`bmad-agent-ux-designer`), Amelia |
| 🧪 QA | 전 에픽 검증 + Epic 5 (5-4) | Murat (`bmad-tea`) |

---

## 부록. 명령어 한 줄 요약표

### 핵심 워크플로우

| 코드 | 명령어 | 용도 |
|---|---|---|
| `[BH]` | `/bmad-help` | 다음에 뭐 할지 추천 |
| `[CP]` | `/bmad-create-prd` | PRD 작성 |
| `[VP]` | `/bmad-validate-prd` | PRD 검증 |
| `[EP]` | `/bmad-edit-prd` | PRD 수정 |
| `[CU]` | `/bmad-create-ux-design` | UX 설계 |
| `[CA]` | `/bmad-create-architecture` | 아키텍처 |
| `[CE]` | `/bmad-create-epics-and-stories` | 에픽·스토리 분해 |
| `[IR]` | `/bmad-check-implementation-readiness` | 구현 준비도 검증 |
| `[SP]` | `/bmad-sprint-planning` | 스프린트 계획 |
| `[SS]` | `/bmad-sprint-status` | 스프린트 현황 |
| `[CS]` | `/bmad-create-story` | 스토리 생성 |
| `[VS]` | `/bmad-create-story` (validate) | 스토리 검증 |
| `[DS]` | `/bmad-dev-story` | 스토리 구현 |
| `[CR]` | `/bmad-code-review` | 코드 리뷰 |
| `[QQ]` | `/bmad-quick-dev` | 풀 사이클 우회 빠른 구현 |
| `[CC]` | `/bmad-correct-course` | 코스 재조정 |
| `[QA]` | `/bmad-qa-generate-e2e-tests` | E2E 테스트 생성 |
| `[ER]` | `/bmad-retrospective` | 회고 |

### 테스트 (TEA)

| 코드 | 명령어 | 용도 |
|---|---|---|
| `[TF]` | `/bmad-testarch-framework` | 프레임워크 초기화 |
| `[TD]` | `/bmad-testarch-test-design` | 테스트 설계 |
| `[AT]` | `/bmad-testarch-atdd` | red-phase 인수 테스트 |
| `[TA]` | `/bmad-testarch-automate` | 자동화 확장 |
| `[NR]` | `/bmad-testarch-nfr` | 비기능 평가 |
| `[RV]` | `/bmad-testarch-test-review` | 테스트 품질 감사 |
| `[TR]` | `/bmad-testarch-trace` | 트레이서빌리티 |
| `[CI]` | `/bmad-testarch-ci` | CI/CD 파이프라인 |

### 보조 도구

| 코드 | 명령어 | 용도 |
|---|---|---|
| `[CK]` | `/bmad-checkpoint-preview` | 변경 검토 워크스루 |
| `[AR]` | `/bmad-review-adversarial-general` | 냉소적 QA |
| `[ECH]` | `/bmad-review-edge-case-hunter` | 경계 조건 점검 |
| `[SD]` | `/bmad-shard-doc` | 큰 문서 분할 |
| `[ID]` | `/bmad-index-docs` | 폴더 인덱스 생성 |
| `[DG]` | `/bmad-distillator` | 문서 압축 |
| `[DP]` | `/bmad-document-project` | brownfield 정리 |
| `[GPC]` | `/bmad-generate-project-context` | 코드베이스 → LLM 컨텍스트 |

### 에이전트 (페르소나)

| 에이전트 | 명령어 | 역할 |
|---|---|---|
| **John** | `/bmad-agent-pm` | PM |
| **Sally** | `/bmad-agent-ux-designer` | UX 디자이너 |
| **Winston** | `/bmad-agent-architect` | 아키텍트 |
| **Amelia** | `/bmad-agent-dev` | 개발자 |
| **Murat** | `/bmad-tea` | 테스트 아키텍트 |
| **Mary** | `/bmad-agent-analyst` | 비즈니스 분석가 |
| **Paige** | `/bmad-agent-tech-writer` | 테크 라이터 |
