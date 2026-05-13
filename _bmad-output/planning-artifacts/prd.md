---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete']
completedAt: '2026-04-24'
status: complete
inputDocuments: ['tracker_기획서.md', '_bmad-output/brainstorming/brainstorming-session-2026-04-24-1430.md']
workflowType: 'prd'
classification:
  projectType: web_app
  domain: scientific+general
  complexity: high
  projectContext: brownfield
---

# Product Requirements Document - Tracker

**Author:** Tracker
**Date:** 2026-04-24

## Executive Summary

Tracker는 NC AI 게임 보안 담당자를 위한 자동화된 불법 프로그램 유포 탐지 시스템이다. 한국·중국·대만 커뮤니티 사이트(최대 6개)를 1시간 주기로 자동 크롤링하고, NC AI의 VARCO Translation → LLM → Vision 파이프라인을 통해 다국어 텍스트 및 이미지 우회 게시글을 탐지하여 React 대시보드에 목록화한다. 담당자는 대시보드에서 탐지 게시글 목록을 확인하고 원본 URL로 즉시 이동해 조치를 취한다.

**문제:** 게임 치트 경제 규모 약 85억 달러(Intorqa, 2026) 수준으로 성장하며, PC 게이머 80%가 치터를 경험한다. 기존 anti-piracy 솔루션(MUSO, Irdeto)은 영상·음악 저작권 침해에 특화되어 있고, 게임 불법 프로그램 유포 채널(한·중 커뮤니티)을 실시간으로 커버하는 솔루션은 공백 상태다. 수동 모니터링으로는 다국어 대응과 이미지 우회 탐지가 불가능하다.

**해결:** 크롤러 + 전처리 + VARCO AI 파이프라인의 End-to-End 자동화로, 담당자가 사이트를 직접 순회하지 않고 단일 대시보드에서 불법 게시글 목록을 확인하고 처리할 수 있도록 한다.

### What Makes This Special

기존 솔루션과의 결정적 차이는 세 가지다:

1. **다국어 + 이미지 동시 탐지:** VARCO Translation으로 중국어·대만 번체를 한국어로 번역 후 LLM 분류, VARCO Vision으로 텍스트 우회 이미지 게시글까지 탐지. 단일 파이프라인이 텍스트·이미지·언어 장벽을 동시에 처리한다.

2. **도메인 특화 고정확도:** 게임 불법 프로그램 게시글은 가격 명시, 텔레그램 유도, 매크로·핵 은어(外挂, 破解) 패턴이 명확하여 범용 콘텐츠 모더레이션(OpenAI Moderation API F1 0.77) 대비 높은 정확도(목표 Precision ≥ 0.85)가 현실적으로 달성 가능하다.

3. **조치 중심 워크플로우:** 탐지 결과를 "왜 불법인가" 설명 중심이 아닌 "어떤 게시글이, 어느 사이트에" 목록 중심으로 제공. 원본 URL 직접 링크로 담당자의 조치 흐름을 단절 없이 연결한다.

## Project Classification

| 항목 | 값 |
|------|-----|
| **프로젝트 유형** | Web App (React SPA 대시보드 + Java Spring REST API + Python AI 데이터 파이프라인) |
| **도메인** | 게임 보안 / AI-ML 탐지 시스템 |
| **복잡도** | High — 분산 AWS 인프라(EC2 ×3, S3, RDS, Redis), 다국어 처리, 외부 VARCO API 파이프라인 |
| **프로젝트 컨텍스트** | Brownfield — 기획서 및 기술 결정 사항(아키텍처 옵션 A, Playwright+stealth, NodeMaven 단계별 전략) 완비 |
| **협력 기업** | NC AI (VARCO API 제공) |
| **개발 기간** | 11주 (2026년 4월 기준) |

## Success Criteria

### User Success

- 담당자가 대시보드에서 탐지 목록 확인 → 원본 URL 클릭 → 즉시 조치의 3단계 워크플로우가 단절 없이 완성된다.
- 날짜·사이트·유형 필터를 조합하여 원하는 탐지 게시글을 30초 이내에 검색할 수 있다.
- 탐지 목록에 표시된 게시글의 85% 이상이 실제 불법 게시글이어서 담당자가 결과를 신뢰하고 조치에 활용한다.

### Business Success

- NC AI 최종 발표 시연에서 명확한 불법 게시글(가격·연락처 명시) 10건 이상을 실시간 탐지하는 데모를 성공시킨다.
- 크롤링 자동화: 1시간 주기 무중단 운영, 발표 기간 포함 24시간 이상 안정 운영을 입증한다.
- 탐지 대상 사이트: MVP 최소 2개 안정 수집 확인, 목표 4개 이상 연결 성공.

### Technical Success

- End-to-End 파이프라인(크롤링 → 전처리 → VARCO Translation → VARCO LLM → RDS → 대시보드)이 수동 개입 없이 자동 실행된다.
- 1회 배치 처리 시간 ≤ 30분.
- 크롤링 완료 후 대시보드 반영 지연 ≤ 5분.
- DLQ 알람 정상 작동: 실패 메시지 3회 재시도 후 `posts:dlq` 격리 및 Grafana 알람 발생 확인.

### Measurable Outcomes

| 지표 | 목표값 | 측정 방법 |
|------|--------|-----------|
| **Precision** | ≥ 0.85 | 수동 라벨링 테스트셋 ≥ 100건 (불법 50 + 정상 50) 기준 |
| **Recall** | ≥ 0.65 | 동일 테스트셋 기준. 이미지 우회·은어 변형 게시글 미탐 감안 |
| **F1** | ≈ 0.74 (참고값) | 단독 목표 아닌 Precision/Recall 결과로 산출 |
| **명확 케이스 정탐율** | ≥ 90% | 가격·텔레그램·매크로 명시 게시글 — 발표 시연 핵심 지표 |
| **배치 처리 시간** | ≤ 30분 | 배치 시작~종료 로그 차이 |
| **대시보드 반영 지연** | ≤ 5분 | 크롤링 완료 시각 → 대시보드 업데이트 시각 |
| **운영 안정성** | 24시간 무중단 | APScheduler 실행 로그 확인 |

## Product Scope

### MVP - Minimum Viable Product

크롤링 → 전처리(HTML 파싱·언어 감지·중복 해시·키워드 필터) → VARCO Translation → VARCO LLM 분류 → RDS 저장 → React 대시보드 표시까지의 End-to-End 텍스트 탐지 파이프라인을 자동 실행한다.

- 크롤링: Playwright + stealth, ProxyBroker(개발), APScheduler 1시간 주기
- 전처리: Crawler EC2 인라인 수행 (옵션 A)
- AI: VARCO Translation(중국어·번체) + VARCO LLM(불법 분류)
- 백엔드: Java Spring REST API + Redis MQ + RDS PostgreSQL
- 대시보드: 탐지 목록 / 상세 / 통계 화면
- 인프라: AWS EC2 ×3, S3, RDS, Redis (t3.medium 기준) <!-- 2026-04-24 PRD freeze 시점 사양. 실 deployment는 2026-05-09 3차 PIVOT으로 **단일 t3.xlarge 16GB**로 회귀 — architecture.md / 기획서 2.1.1.a 참조 -->

### Growth Features (Post-MVP)

- **VARCO Vision 이미지 탐지:** 이미지로만 구성된 텍스트 우회 게시글 탐지. 5~7주차 VARCO LLM F1 실측 후 AI 담당자(일드매) 결정.
- **BERT 2차 필터:** VARCO LLM 호출 전 위험도 사전 스코어링. Vision과 함께 Detection EC2 업사이징(t3.large 또는 g4dn) 검토.
- **프록시 업그레이드:** ProxyBroker → NodeMaven(중국 IP 전문, ~$50~80/월). 중국 사이트 차단율 실측 후 도입 시점 결정.
- **수동 크롤링 트리거:** `POST /crawl/trigger` — 관리자 즉시 실행 API.
- **실시간 알림:** 신뢰도 0.95 이상 고위험 탐지 시 Slack·이메일 즉시 알림.

### Vision (Future)

- **NC 타이틀 전체 적용:** 리니지·블레이드앤소울·쓰론앤리버티 등 타이틀별 탐지 키워드·VARCO LLM 프롬프트 커스터마이징.
- **탐지 채널 확장:** 디스코드 서버, 텔레그램 채널, 레딧 등 신규 유포 채널 추가.
- **Class-RAG 자동 개선:** pgvector 기반 유사 탐지 사례 검색으로 모호 케이스 정확도 지속 개선 (재학습 불필요).

## User Journeys

### Journey 1: 보안 담당자 — 일상 모니터링 (Primary Success Path)

**페르소나:** 김민준, NC AI 게임 보안 팀 담당자. 리니지 시리즈 담당으로 매일 오전 한국·중국 불법 프로그램 커뮤니티를 직접 검색해왔다. 중국어는 구글 번역을 써도 게임 은어는 놓치기 일쑤였고, 이미지로만 올라온 판매 게시글은 아예 탐지가 불가능했다.

**Opening — 기존 고통:** 월요일 오전, 민준은 tailstar.net을 열고 수백 개 게시글 중 불법 판매 게시글을 직접 클릭해가며 확인한다. 중국 포럼은 언어 장벽에 막혀 넘어가기가 어렵다. 하루에 2~3시간이 이 작업에 소요된다.

**Rising Action — 첫 사용:** Tracker 대시보드에 접속한다. 오늘 탐지 수, 사이트별 분포 차트가 즉시 보인다. tailstar.net에서 탐지된 게시글 12건, tieba.baidu.com에서 3건. 사이트 필터를 tailstar.net으로 좁히고 "매크로 판매" 유형을 클릭한다.

**Climax — 가치 전달 순간:** 목록에서 게시글 하나를 클릭한다. 원문(한국어), 번역문(원본이 중국어인 경우), 탐지 유형, 신뢰도 0.91이 표시된다. 출처 URL을 클릭하자 tailstar.net 원본 게시글로 바로 이동한다. 민준은 신고 처리를 즉시 완료한다. 직접 검색하던 2~3시간이 15분으로 줄었다.

**Resolution — 새 현실:** 매일 아침 대시보드를 열어 탐지 목록을 확인하고 조치하는 것이 루틴이 됐다. 중국 포럼도 번역된 채로 목록에 올라와 더 이상 언어 장벽이 없다.

**→ 드러나는 요구사항:** 탐지 목록 조회(필터), 탐지 상세(원문·번역·신뢰도), 원본 URL 링크, 대시보드 통계 차트

---

### Journey 2: 보안 담당자 — 긴급 대응 (Edge Case)

**상황:** NC 신작 게임 오픈 베타 당일, 불법 매크로 판매 게시글이 급증하고 있다는 제보가 들어왔다. 다음 자동 크롤링까지 45분이 남아 있다.

**Opening:** 민준은 Tracker 대시보드를 열지만 최신 게시글이 아직 반영되지 않았다.

**Rising Action:** 관리자 메뉴에서 "즉시 크롤링" 버튼을 누른다. `POST /crawl/trigger` 요청이 발송되고 진행 상태가 표시된다.

**Climax:** 8분 후 크롤링이 완료되고 탐지 목록이 업데이트된다. 오늘 날짜 필터로 신규 게시글 23건이 확인된다. 그 중 "매크로 판매" 16건, "계정 거래" 4건.

**Resolution:** 신뢰도 0.90 이상 게시글 16건에 대해 원본 URL을 열어 순차적으로 신고 처리한다. 오픈 베타 첫날 불법 프로그램 게시글 대응을 당일 완료.

**→ 드러나는 요구사항:** 수동 크롤링 트리거 API, 크롤링 진행 상태 표시, 날짜 필터, 신뢰도 정렬

---

### Journey 3: 보안 팀장 — 주간 현황 보고 (Operations User)

**페르소나:** 이수현, 게임 보안 팀장. 주간 회의에서 불법 프로그램 현황을 경영진에게 보고해야 한다. 기존에는 담당자에게 수동으로 집계를 요청했다.

**Opening:** 매주 금요일 오전, 이수현은 Tracker 통계 화면을 연다.

**Rising Action:** 주간 탐지 추이 차트에서 월~금 탐지 수 변화를 확인한다. 사이트별 비교 차트에서 tailstar.net이 전체의 61%를 차지함을 파악한다. 유형별 분포에서 매크로 판매가 급증 추세임을 발견한다.

**Resolution:** 차트 화면을 캡처해 주간 보고서에 첨부한다. 집계 요청 없이 5분 만에 보고 자료 준비 완료.

**→ 드러나는 요구사항:** 통계 화면(주간·월간 추이 차트, 사이트별·유형별 분포)

---

### Journey Requirements Summary

| 여정 | 드러난 핵심 기능 |
|------|-----------------|
| 일상 모니터링 | 탐지 목록(필터), 탐지 상세(원문·번역·신뢰도), 원본 URL 링크, 대시보드 |
| 긴급 대응 | 수동 크롤링 트리거, 크롤링 진행 상태, 날짜 필터, 신뢰도 정렬 |
| 주간 보고 | 통계 화면(추이·사이트별·유형별 차트) |

## Domain-Specific Requirements

### 크롤링 윤리 및 법적 제약

- 대상 사이트의 `robots.txt` 및 이용약관을 사전 확인하고, 크롤링 속도를 제어하여 대상 서비스에 과도한 부하를 주지 않는다.
- 수집된 게시글 텍스트·이미지는 탐지 목적으로만 사용하며, 제3자 제공 및 외부 공개를 금지한다.

### 탐지 오류(False Positive) 관리

- 탐지 결과는 판단 보조 자료이며, 최종 조치 결정은 담당자 검토를 거친다.
- VARCO LLM 신뢰도 임계값(confidence threshold) 기본값 0.70 이상만 목록 표시. 오탐 노출 최소화.

### 데이터 보관 정책

- 수집 데이터 보관 기간을 정의하고, 기간 초과 데이터에 자동 삭제 정책을 적용한다 (구체 기간은 NC AI와 협의).

## Innovation & Novel Patterns

### 감지된 혁신 영역

**1. 게임 도메인 특화 다단계 AI 탐지 파이프라인**

기존 anti-piracy 솔루션(MUSO, Irdeto)은 영상·음악 저작권 침해에 특화되어 있으며, 게임 불법 프로그램 유포 탐지를 위한 특화 파이프라인은 공백 상태다. Tracker는 VARCO Translation(게임 도메인 번역) → VARCO LLM(게임 불법 분류) → VARCO Vision(이미지 우회 탐지)을 조합하여, 다국어·텍스트·이미지를 단일 파이프라인으로 처리하는 최초의 게임 보안 특화 탐지 시스템을 구현한다.

**2. VLM을 활용한 텍스트 우회 탐지 (VARCO Vision)**

텍스트 탐지를 회피하기 위해 판매 정보를 이미지로만 업로드하는 전략이 게임 불법 프로그램 유포 채널에서 확산되고 있다. VARCO Vision(14B 멀티모달 모델)을 활용해 이미지 속 텍스트를 인식하고 불법 여부를 동시 판단하는 접근은, 이 도메인에서 새로운 방어 use case를 제시한다.

### 경쟁 환경 및 시장 맥락

| 구분 | 기존 솔루션 | Tracker |
|------|------------|---------|
| 대상 | 영상·음악 저작권 | 게임 불법 프로그램 유포 |
| 언어 | 주로 영어권 | 한국어 + 중국어·대만 번체 |
| 탐지 방식 | 텍스트 기반 | 텍스트 + 이미지(VLM) |
| 도메인 이해 | 범용 | 게임 은어·매크로·핵 특화 |

### 검증 접근법

- **LLM 탐지 정확도:** 수동 라벨링 테스트셋 ≥ 100건으로 Precision/Recall 측정. 5~7주차 실측 결과를 기반으로 BERT 2차 필터 도입 여부 결정.
- **Vision 탐지:** 이미지만으로 구성된 불법 게시글 샘플 ≥ 20건 수집 후 VARCO Vision 정탐율 측정. MVP 이후 단계에서 F1 측정.
- **시연 검증:** NC AI 발표 시 명확 케이스(가격·연락처 명시) ≥ 10건 실시간 탐지 데모.

### 리스크 및 완화

| 리스크 | 완화 전략 |
|--------|-----------|
| VARCO LLM이 게임 은어를 오판 | 키워드 1차 필터로 명확 케이스 사전 선별, 신뢰도 임계값 0.70 적용 |
| 중국 사이트 차단율 높아 데이터 부족 | ProxyBroker → NodeMaven 단계별 전략, 대만(PTT·Dcard) GFW 회피 병행 |
| VARCO Vision 이미지 탐지 미도입 시 | MVP에서 텍스트만으로 F1 목표 달성 가능. Vision은 Growth 단계로 이월 |
| BERT 추가 없이 LLM만으로 정확도 부족 | 5~7주차 실측 후 AI 담당자(일드매) 결정. EC2 업사이징 조건 사전 정의 |

## Web App Specific Requirements

### Project-Type Overview

Tracker는 세 개의 독립 레이어로 구성된 복합 시스템이다. 각 레이어는 AWS EC2 단위로 분리되며, Redis MQ를 통해 비동기 연결된다.

| 레이어 | 기술 | 역할 |
|--------|------|------|
| 크롤링 파이프라인 | Python, Playwright+stealth, APScheduler | 수집 + 전처리 + Redis enqueue |
| AI 탐지 파이프라인 | Python, VARCO API | Redis dequeue + 번역 + LLM 분류 + RDS 저장 |
| 서비스 레이어 | Java Spring + React SPA | REST API + 대시보드 |

### Frontend (React SPA)

- **렌더링 방식:** SPA (Single Page Application)
- **지원 브라우저:** Chrome / Edge 최신 2버전 (내부 운영 도구)
- **SEO:** 불필요 — 인증 없이 외부 노출되지 않는 내부 도구
- **반응형:** 데스크톱 1280px+ 우선 / 모바일 < 768px 지원(Tailwind `md` breakpoint 기준 햄버거 drawer + 카드 뷰 + bottom Drawer 필터). 태블릿 768~1023px은 best-effort. **2026-05-13 PIVOT** — 외부 운영자의 모바일 긴급 조치(원본 URL 점프 + 수동 크롤링 트리거) 요구로 Growth 단계 항목을 MVP로 끌어옴 (Story 4.7)
- **접근성:** 기본 수준 (내부 도구, WCAG 준수 필수 아님)
- **인증:** MVP에서 제외. 내부망(VPC 보안 그룹) + AWS 네트워크 레벨 접근 제어로 대체. 애플리케이션 인증(SSO 등)은 Growth 단계
- **핵심 화면 4종:**
  - 메인 대시보드: 오늘 탐지 수, 전일 대비, 유형별 파이 차트, 사이트별 바 차트
  - 탐지 목록: 날짜·사이트·유형·언어 필터 + 신뢰도 정렬
  - 탐지 상세: 원문·번역문·탐지 유형·신뢰도·출처 URL 링크
  - 통계: 주간·월간 추이 차트, 사이트별·언어별 분포

### Backend API (Java Spring)

- **API 스타일:** REST (JSON)
- **문서화:** Swagger(OpenAPI) 자동 생성
- **주요 엔드포인트:**

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/detections` | 탐지 목록 조회 (필터: date, site, type, lang, page) |
| GET | `/detections/{id}` | 탐지 상세 조회 |
| GET | `/stats` | 통계 조회 (총 탐지 수, 유형별·사이트별 분포) |
| POST | `/crawl/trigger` | 수동 크롤링 즉시 실행 |

- **모니터링:** Prometheus 메트릭 수집 + Grafana 대시보드 (API 응답 시간, 에러율, 큐 길이, DLQ 알람)
- **Redis 역할:** MQ(`posts:queue`/`posts:processing`/`posts:dlq`) + 중복 해시 SET(`posts:dedup`) + VARCO rate limit 토큰 버킷(`varco:rate_limit`) + 대시보드 캐시

### 성능 목표

| 지표 | 목표값 |
|------|--------|
| API 응답 시간 (GET /detections) | ≤ 500ms (p95) |
| 대시보드 초기 로드 | ≤ 3초 |
| 1회 배치 처리 시간 | ≤ 30분 |
| 크롤링 완료 → 대시보드 반영 | ≤ 5분 |

### Infrastructure (AWS)

> ⚠️ **2026-04-24 PRD freeze 시점 사양.** 실 deployment는 2026-05-04~2026-05-09 학생 IAM SCP 제약 발견으로 다단계 PIVOT 적용 (1차: 3대 t3.medium x86_64 강제 다운그레이드, 2차: 2 EC2 분리 시도, 3차 최종: 단일 t3.xlarge 16GB 회귀). 최신 사양은 [architecture.md](architecture.md) Infrastructure & Deployment 섹션 + [tracker_기획서.md](../../tracker_기획서.md) 2.1.1.a 참조.

| 리소스 | 사양 | 역할 |
|--------|------|------|
| Crawler EC2 | t3.medium | Playwright + APScheduler + 전처리 인라인 (옵션 A) |
| Detection EC2 | t3.medium (BERT 도입 시 t3.large 또는 g4dn 업사이징) | VARCO API 호출 전담 |
| API EC2 | t3.medium | Spring + Redis(docker-compose) + Grafana |
| RDS | PostgreSQL (t3.micro~small) | sources / posts / post_images / detections 4개 테이블 |
| S3 | 표준 | 크롤링 원본 텍스트 + 이미지 아카이브 |
| CI/CD | GitHub Actions | 코드 푸시 시 자동 빌드·배포 |

### Implementation Considerations

- `detections.type` 허용값(enum) 사전 정의 필요: `매크로_판매`, `핵_배포`, `계정_거래`, `리세마라`, `기타`
- ProxyProvider 인터페이스 추상화 — ProxyBroker(개발) → NodeMaven(운영) 교체 시 코드 변경 최소화
- APScheduler interval을 환경변수(`CRAWL_INTERVAL_MINUTES`)로 외부화 — 재배포 없이 1시간 ↔ 15분 전환 가능

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP 접근법:** Problem-solving MVP. 핵심 질문 — "크롤링 → AI 탐지 → 대시보드 파이프라인이 수동 개입 없이 자동으로 동작하고, 명확한 불법 게시글을 Precision ≥ 0.85로 탐지할 수 있는가?"

**팀 구성:** 3인 (크롤링·AI 담당 일드매 / 백엔드 최병주 / 인프라·프론트 박재성), 11주

**MVP 최소 조건:** 담당자가 대시보드에서 탐지 목록을 보고 원본 URL로 이동해 조치할 수 있으면 MVP 완성.

### MVP Feature Set (Phase 1 — 1~9주)

**지원 핵심 여정:**
- Journey 1: 일상 모니터링 (탐지 목록 확인 → URL 조치)
- Journey 2: 긴급 대응 (수동 크롤링 트리거)

**Must-Have 기능:**

| 영역 | 기능 |
|------|------|
| 크롤링 | Playwright+stealth + ProxyBroker, APScheduler 1시간 주기, 이미지 수집, S3 적재. 대상: tailstar.net(한국), PTT·Dcard(대만), tieba.baidu.com·52pojie.cn·bbs.nga.cn(중국, 연결 성공 확인 시) |
| 전처리 | HTML 파싱, 언어 감지, 중복 해시(Redis), 키워드 1차 필터 (Crawler EC2 인라인) |
| AI 탐지 | VARCO Translation(중국어·번체) + VARCO LLM 분류, Redis MQ(queue/processing/dlq) |
| 백엔드 | Java Spring REST API 4종 (`GET /detections`, `GET /detections/{id}`, `GET /stats`, `POST /crawl/trigger`) |
| 수동 크롤링 | `POST /crawl/trigger` — 즉시 크롤링 실행 (긴급 대응용) |
| 대시보드 | 메인 대시보드, 탐지 목록(필터), 탐지 상세, 통계 화면 |
| 인프라 | AWS EC2 ×3, S3, RDS(PostgreSQL), Redis, GitHub Actions CI/CD |
| QA | 수동 라벨링 테스트셋 ≥ 100건, Precision/Recall 측정 |

### Post-MVP Features

**Phase 2 — Growth (MVP 이후, 실측 데이터 기반 결정):**
- VARCO Vision 이미지 탐지 (텍스트 우회 게시글)
- BERT 2차 필터 (5~7주차 LLM Precision 실측 후 AI 담당자 결정)
- 프록시 업그레이드: NodeMaven (~$50~80/월, GFW 우회)
- 애플리케이션 레벨 인증 (SSO 또는 ID/PW)
- 실시간 알림 (신뢰도 ≥ 0.95 탐지 시 Slack/이메일)
- ~~모바일 반응형 대시보드~~ → **MVP로 편입 (2026-05-13 PIVOT, Story 4.7)**

**Phase 3 — Expansion:**
- NC 타이틀 전체 적용 (리니지·블소·쓰론앤리버티 키워드·프롬프트 커스터마이징)
- 탐지 채널 확장 (디스코드, 텔레그램, 레딧)
- Class-RAG 자동 개선 (pgvector 기반 유사 사례 검색)

### Risk Mitigation Strategy

**기술 리스크:**

| 리스크 | 가능성 | 완화 전략 |
|--------|--------|-----------|
| 크롤링 차단 (Cloudflare/GFW) | 높음 | FlareSolverr 병행, 대만(PTT·Dcard) GFW 우회 선행 확보, 차단 사이트 이월 |
| VARCO API rate limit 초과 | 중간 | Redis 토큰 버킷, 키워드 필터로 호출량 ~10%로 사전 감축 |
| BERT 도입 시 EC2 부족 | 낮음 | t3.medium 시작 → g4dn 업사이징 조건 사전 정의 |

**리소스 리스크:**

| 리스크 | 완화 전략 |
|--------|-----------|
| 11주 일정 부족 | Vision/BERT를 Growth 단계로 명확히 이월. MVP는 텍스트 탐지만으로 완성 가능 |
| 중국 사이트 탐지 데이터 부족 | 대만 사이트(GFW 없음)로 다국어 탐지 검증. 중국은 NodeMaven 도입 후 확장 |

## Functional Requirements

### 콘텐츠 수집 (Content Collection)

- **FR1:** 시스템은 지정된 커뮤니티 사이트(tailstar.net, PTT, Dcard, tieba.baidu.com, 52pojie.cn, bbs.nga.cn — 최대 6개, 연결 성공 확인 분)를 1시간 주기로 자동 크롤링할 수 있다
- **FR2:** 시스템은 bot 탐지 우회 기술을 사용하여 대상 사이트의 차단 없이 게시글을 수집할 수 있다
- **FR3:** 시스템은 Cloudflare JS 챌린지가 적용된 사이트를 우회하여 수집할 수 있다
- **FR4:** 시스템은 게시글 본문 텍스트와 첨부 이미지를 함께 수집할 수 있다
- **FR5:** 시스템은 수집한 원본 데이터(텍스트+이미지)를 아카이브 스토리지에 보관할 수 있다
- **FR6:** 담당자는 특정 사이트에 대해 즉시 크롤링을 수동으로 실행할 수 있다

### 콘텐츠 전처리 (Content Preprocessing)

- **FR7:** 시스템은 수집된 HTML에서 광고·네비게이션을 제거하고 본문·제목·이미지 URL을 추출할 수 있다
- **FR8:** 시스템은 게시글의 언어(한국어/중국어/번체)를 자동으로 감지할 수 있다
- **FR9:** 시스템은 이미 처리된 게시글을 해시 기반으로 식별하여 중복 처리를 방지할 수 있다
- **FR10:** 시스템은 불법 프로그램 관련 키워드 사전으로 관련 게시글 후보를 1차 선별할 수 있다

### AI 탐지 (AI Detection)

- **FR11:** 시스템은 중국어·번체 게시글을 한국어로 자동 번역할 수 있다
- **FR12:** 시스템은 게시글의 불법 여부와 유형(매크로 판매/핵 배포/계정 거래/리세마라/기타)을 자동 분류할 수 있다
- **FR13:** 시스템은 각 탐지 결과에 신뢰도 점수(0~1)를 산출할 수 있다
- **FR14:** 시스템은 탐지 결과와 함께 불법 판단 근거 텍스트를 생성할 수 있다
- **FR15:** 시스템은 탐지 처리 실패 시 자동 재시도하고, 3회 실패 시 격리 큐로 이동시킬 수 있다
- **FR16:** 시스템은 외부 AI API 호출량을 제어하여 할당량 초과를 방지할 수 있다

### 탐지 결과 조회 (Detection Browsing)

- **FR17:** 담당자는 탐지된 게시글 목록을 조회할 수 있다
- **FR18:** 담당자는 탐지 목록을 날짜·사이트·탐지 유형·언어로 필터링할 수 있다
- **FR19:** 담당자는 탐지 목록을 신뢰도 기준으로 정렬할 수 있다
- **FR20:** 담당자는 특정 탐지 게시글의 원문·번역문·탐지 유형·신뢰도·판단 근거를 상세 조회할 수 있다
- **FR21:** 담당자는 탐지 상세 화면에서 원본 게시글 URL로 직접 이동할 수 있다
- **FR22:** 시스템은 설정된 신뢰도 임계값 이상의 탐지 결과만 목록에 노출할 수 있다

### 통계 및 분석 (Statistics & Analytics)

- **FR23:** 담당자는 오늘의 총 탐지 수와 전일 대비 증감을 조회할 수 있다
- **FR24:** 담당자는 탐지 유형별 분포를 조회할 수 있다
- **FR25:** 담당자는 사이트별 탐지 건수 분포를 조회할 수 있다
- **FR26:** 담당자는 주간·월간 탐지 추이 차트를 조회할 수 있다
- **FR27:** 담당자는 언어별 탐지 분포를 조회할 수 있다

### 시스템 운영 (System Operations)

- **FR28:** 시스템은 크롤링 파이프라인을 지정된 시간 간격으로 자동 실행하며, 간격을 재배포 없이 변경할 수 있다
- **FR29:** 시스템은 크롤링 및 탐지 파이프라인의 실행 상태를 모니터링할 수 있다
- **FR30:** 시스템은 처리 실패한 메시지를 격리하고 운영자에게 알람을 발송할 수 있다
- **FR31:** QA 담당자는 수동 라벨링 테스트셋으로 탐지 정확도(Precision/Recall)를 측정할 수 있다
- **FR32:** 시스템은 크롤링 완료 후 5분 이내에 탐지 결과를 대시보드에 반영할 수 있다

## Non-Functional Requirements

### Performance

- **NFR1:** `GET /detections` API 응답 시간 ≤ 500ms (p95 기준, RDS 인덱스 정상 상태)
- **NFR2:** 대시보드 초기 로드 시간 ≤ 3초 (Chrome 데스크톱, 사내망 기준)
- **NFR3:** 1회 배치(크롤링 → 전처리 → VARCO 탐지 → RDS 저장) 완료 시간 ≤ 30분
- **NFR4:** 크롤링 완료 후 대시보드 탐지 결과 반영 지연 ≤ 5분

### Security

- **NFR5:** VARCO API 키·AWS 자격증명은 환경 변수로 관리하며 코드 저장소에 노출 금지
- **NFR6:** AWS 자격증명은 EC2 IAM Role 기반으로 관리하며 Access Key 하드코딩 금지
- **NFR7:** RDS 및 Redis는 VPC 내부망에서만 접근 가능하도록 보안 그룹 구성
- **NFR8:** S3 버킷은 퍼블릭 접근을 차단하고 VPC 내 EC2만 접근 허용
- **NFR9:** 수집된 게시글 데이터는 탐지 목적으로만 사용하며 외부 공개 금지

### Reliability

- **NFR10:** 크롤링 파이프라인은 24시간 무중단 자동 실행을 유지한다 (APScheduler 프로세스 재시작 시 다음 주기에 자동 복구)
- **NFR11:** VARCO API 호출 실패 시 자동으로 최대 3회 재시도하며, 3회 초과 시 DLQ로 격리한다
- **NFR12:** DLQ 메시지 누적 시 Grafana 알람이 발생하여 운영자가 5분 이내에 인지할 수 있다
- **NFR13:** EC2 단일 인스턴스 재시작 후 데이터 유실 없이 파이프라인이 재개된다 (S3 원본 아카이브 + Redis AOF 활용)

### Integration

- **NFR14:** VARCO API rate limit 초과 시 Redis 토큰 버킷으로 자동 대기하며 수동 개입 없이 처리를 재개한다
- **NFR15:** 프록시 프로바이더(ProxyBroker → NodeMaven) 교체 시 `ProxyProvider` 인터페이스 구현체 변경만으로 완료되며 크롤러 핵심 로직 수정이 불필요하다
- **NFR16:** Redis 큐 연산(`BRPOPLPUSH`)은 원자적으로 실행되어 Worker 크래시 시 메시지 유실이 발생하지 않는다
- **NFR17:** 크롤링 스케줄 간격(`CRAWL_INTERVAL_MINUTES`)은 환경 변수 변경만으로 적용되며 재배포가 불필요하다
