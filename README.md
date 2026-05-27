# Tracker

<div align="center">

**한·중·대만 게임 커뮤니티의 불법 프로그램 유포 게시글을 자동으로 탐지하는 사내 운영 도구**

2026.04 - 2026.07 · 11주 · 3인 팀 · 크롤링·AI / 백엔드 / 인프라·프론트엔드

고려대학교 실전SW프로젝트 × NC AI

[![CI](https://github.com/byungju0/261RCOSE45700/actions/workflows/ci.yml/badge.svg)](https://github.com/byungju0/261RCOSE45700/actions/workflows/ci.yml)
[![Deploy](https://github.com/byungju0/261RCOSE45700/actions/workflows/deploy.yml/badge.svg)](https://github.com/byungju0/261RCOSE45700/actions/workflows/deploy.yml)

[Wiki](https://github.com/byungju0/261RCOSE45700/wiki) ·
[Architecture](https://github.com/byungju0/261RCOSE45700/wiki/Architecture-Overview) ·
[Getting Started](https://github.com/byungju0/261RCOSE45700/wiki/Getting-Started) ·
[Sprint Status](https://github.com/byungju0/261RCOSE45700/wiki/Sprint-Status)

</div>

크롤러가 8개 사이트를 1시간 주기로 돌고, OpenAI 멀티모달 LLM 파이프라인이 다국어 게시글을 번역·분류해 불법 여부를 기록합니다. 신뢰도 0.70 이상 후보만 React 대시보드에 노출하며, 담당자는 원문·번역·근거를 한 화면에서 보고 원본 URL로 점프해 신고를 진행합니다. 크롤링부터 대시보드 반영까지의 SLA는 5분입니다.

<br>

## 담당 역할

### 인프라 · 프론트엔드 · 박재성 ([@gitjay3](https://github.com/gitjay3))

- 모노레포 스캐폴딩 + 4 path-filtered GitHub Actions 워크플로 구성 ([#5](https://github.com/byungju0/261RCOSE45700/pull/5), [#10](https://github.com/byungju0/261RCOSE45700/pull/10))
- React 19 + Vite 8 대시보드 데스크톱 5 페이지 + 디자인 시스템 v10 overhaul ([#9](https://github.com/byungju0/261RCOSE45700/pull/9), [#40](https://github.com/byungju0/261RCOSE45700/pull/40))
- Story 4-7 모바일 지원 PIVOT (vaul drawer + DetectionCard + bottom Drawer + 다크 테마) ([#41](https://github.com/byungju0/261RCOSE45700/pull/41))
- Story 5-2 자동 배포: `ci.yml` strict aggregator + `deploy.yml` GHCR build + EC2 SSH 직결 + 60초 healthcheck + 자동 롤백 ([#28](https://github.com/byungju0/261RCOSE45700/pull/28), [#37](https://github.com/byungju0/261RCOSE45700/pull/37))
- Story 5-3 Terraform → 콘솔 ClickOps PIVOT (학생 IAM 자격증명 통로 0개 확인 후 IaC 폐기) ([#18](https://github.com/byungju0/261RCOSE45700/pull/18), [#19](https://github.com/byungju0/261RCOSE45700/pull/19))
- frontend-only 데모 배포 경로: MSW prod 토글 + Caddy auto-TLS ([#42](https://github.com/byungju0/261RCOSE45700/pull/42))
- ADR 0001 시크릿 관리 전략: Docker `secrets:` + EC2 SSH 수동 작성 채택 ([#39](https://github.com/byungju0/261RCOSE45700/pull/39))
- BMad 워크플로 도입 + Epic 4 프론트 회고 ([#4](https://github.com/byungju0/261RCOSE45700/pull/4), [#13](https://github.com/byungju0/261RCOSE45700/pull/13))

### 백엔드 · 최병주 ([@byungju0](https://github.com/byungju0))

- PRD · Epics & Stories 작성 ([#2](https://github.com/byungju0/261RCOSE45700/pull/2), [#3](https://github.com/byungju0/261RCOSE45700/pull/3))
- 로컬 개발 환경 docker-compose + Flyway 초기 스키마 (V1~V5) + PostgreSQL/Redis 통합 기반 ([#11](https://github.com/byungju0/261RCOSE45700/pull/11), [#12](https://github.com/byungju0/261RCOSE45700/pull/12))
- Spring Boot 3.5 REST API: 탐지 목록 + 상세 + 수동 크롤링 트리거 + 통계 (RFC 9457 ProblemDetail, X-Correlation-ID, Redis DB3 캐시) ([#17](https://github.com/byungju0/261RCOSE45700/pull/17), [#20](https://github.com/byungju0/261RCOSE45700/pull/20), [#27](https://github.com/byungju0/261RCOSE45700/pull/27))
- Story 5-1 Prometheus + Grafana 모니터링: RedisQueueMetrics 커스텀, DLQ 알림, APScheduler misfire 로깅 ([#38](https://github.com/byungju0/261RCOSE45700/pull/38))
- Epic 1 · Epic 4 전체 회고 ([#15](https://github.com/byungju0/261RCOSE45700/pull/15), [#29](https://github.com/byungju0/261RCOSE45700/pull/29))

### 크롤링 · AI · 일드매 ([@erdmee](https://github.com/erdmee))

- Day 1 공유 인터페이스 계약 (`correlation_id`, `CrawlEvent`, LLM 인터페이스, Redis 키 상수) + 구조화 로깅 ([#6](https://github.com/byungju0/261RCOSE45700/pull/6))
- Cloudflare 우회 가능성 SPIKE: Playwright + `playwright-stealth` 채택 결정 ([#8](https://github.com/byungju0/261RCOSE45700/pull/8))
- crawl4ai 기반 크롤러 + 8개 SiteConfig 등록 + APScheduler 자동/수동 트리거 + S3 원본 아카이브 ([#14](https://github.com/byungju0/261RCOSE45700/pull/14))
- Epic 3 탐지 파이프라인: Redis BRPOPLPUSH 컨슈머 + Watchdog + OpenAI 멀티모달 LLM + 토큰 버킷 + RetryHandler + DLQ + RDS 저장 ([#16](https://github.com/byungju0/261RCOSE45700/pull/16), [#47](https://github.com/byungju0/261RCOSE45700/pull/47))

<br>

## 기술 스택

### Frontend

![Frontend](https://skillicons.dev/icons?i=react,typescript,vite,tailwind)

### Backend & Database

![Backend](https://skillicons.dev/icons?i=java,spring,gradle,postgresql,redis)

### Crawling · AI

![Crawling](https://skillicons.dev/icons?i=python)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)

### Infrastructure

![Infra](https://skillicons.dev/icons?i=docker,nginx,githubactions,prometheus,grafana,aws)
![Caddy](https://img.shields.io/badge/Caddy-1F88C0?style=for-the-badge&logo=caddy&logoColor=white)

<br>

## 시작하기

Python 3.11+, Java 21 LTS, Node.js 22 LTS, Docker가 필요합니다. Java가 없어도 `./gradlew build` 첫 실행 때 Foojay가 받아옵니다. Windows라면 `bin/` 대신 `Scripts\`, `./gradlew` 대신 `gradlew.bat`을 사용하세요.

```bash
git clone https://github.com/byungju0/261RCOSE45700.git
cd 261RCOSE45700

# Redis + PostgreSQL
cp infra/.env.example infra/.env
docker compose -f infra/docker-compose.yml up -d

# 서브시스템 셋업
python3 -m venv crawler/.venv && crawler/.venv/bin/pip install -r crawler/requirements.txt
crawler/.venv/bin/playwright install chromium
python3 -m venv detection/.venv && detection/.venv/bin/pip install -r detection/requirements.txt
cp detection/.env.example detection/.env
cd api && ./gradlew build && cd ..
cd dashboard && corepack enable && pnpm install && cd ..
```

화면만 빠르게 확인하려면 `cd dashboard && pnpm dev`로 충분합니다. `VITE_API_BASE_URL`이 비어 있으면 MSW v2 mock이 백엔드 응답을 흉내내어, 백엔드 없이도 4개 페이지가 그대로 뜹니다.

자세한 셋업 절차, 환경변수, 흔한 문제는 [Getting Started](https://github.com/byungju0/261RCOSE45700/wiki/Getting-Started)에 정리돼 있습니다.

<br>

## 저장소 구성

```
crawler/      Python · crawl4ai 크롤링 + APScheduler + S3 아카이브
detection/    Python · Redis 컨슈머 + OpenAI 멀티모달 LLM + 토큰 버킷 + DLQ + RDS 저장
api/          Java Spring Boot 3.5 · REST 4종 + Flyway
dashboard/    React 19 + Vite 8 · TanStack Query v5 · MSW v2 mock
shared/       Python 공유 모듈 (correlation_id, CrawlEvent, LLM 인터페이스)
infra/        docker-compose + Caddy + Grafana/Prometheus
docs/         ADR + 배포 runbook
_bmad-output/ PRD · architecture · UX spec · 스토리 · 회고
```

각 서브시스템 내부 구조는 [Wiki](https://github.com/byungju0/261RCOSE45700/wiki) 서브시스템 페이지에서 더 자세히 다룹니다.

<br>

## 검증

```bash
crawler/.venv/bin/python -m pytest crawler/tests/unit -q
detection/.venv/bin/python -m pytest detection/tests/unit -q
cd api && ./gradlew build && cd ..
cd dashboard && pnpm build && pnpm test && cd ..
```

E2E는 Playwright로 데스크톱과 Pixel 7 모바일 viewport 두 프로젝트가 분리돼 있습니다.

```bash
cd dashboard && pnpm exec playwright install --with-deps && pnpm e2e
```

<br>

## 배포

main 브랜치 머지가 GitHub Actions `deploy.yml`을 트리거합니다. GHCR에 이미지를 빌드해 push하고, EC2에 SSH로 직결해서 `docker compose pull` + 60초 healthcheck + 자동 롤백까지 한 번에 처리합니다. OpenAI/RDS 셋업이 끝나기 전 화면만 시연할 때는 `deploy-demo.yml`을 `workflow_dispatch`로 수동 트리거하면 dashboard만 mock 빌드로 띄울 수 있습니다 (`tracker.o-r.kr`, Let's Encrypt 자동 발급).

자세한 사양은 [CI/CD Pipeline](https://github.com/byungju0/261RCOSE45700/wiki/CI-CD-Pipeline), 운영 절차는 [docs/deployment.md](docs/deployment.md), 시크릿 결정은 [ADR 0001](docs/adr/0001-secret-management-strategy.md)에 있습니다.

<br>

## 프로젝트 상태

5개 Epic 중 1, 2는 완료, 3·4·5는 진행 중입니다. 데스크톱 대시보드와 모바일 지원이 머지됐고, 운영 자동 배포 파이프라인도 들어왔습니다. detection은 OpenAI 멀티모달 LLM 분류와 RDS 저장 흐름으로 전환됐습니다.

스토리 단위 현황은 [Sprint Status](https://github.com/byungju0/261RCOSE45700/wiki/Sprint-Status), 원본 SoT는 [`sprint-status.yaml`](_bmad-output/implementation-artifacts/sprint-status.yaml)에 있습니다.
