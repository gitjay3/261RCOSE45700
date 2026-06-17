# Tracker

<div align="center">

**한·중·대만 게임 커뮤니티의 불법 프로그램 유포 게시글을 자동으로 탐지하는 운영 도구**

2026.04 - 2026.07 · 고려대학교 실전SW프로젝트 × NC AI · 3인 팀

[Wiki](https://github.com/byungju0/261RCOSE45700/wiki) ·
[Architecture](https://github.com/byungju0/261RCOSE45700/wiki/Architecture-Overview) ·
[Getting Started](https://github.com/byungju0/261RCOSE45700/wiki/Getting-Started) ·
[Sprint Status](https://github.com/byungju0/261RCOSE45700/wiki/Sprint-Status)

</div>

Tracker는 게임 커뮤니티에 올라오는 핵·치트, 사설서버, 불법 프로그램 배포, 계정 거래, 매크로 판매 등 약관 위반 가능성이 높은 게시글을 자동으로 수집·분류하고 운영자가 빠르게 확인할 수 있게 하는 모노레포 프로젝트입니다.

크롤러가 12개 enabled 커뮤니티 사이트와 GitHub API를 주기적으로 순회하고, OpenAI 멀티모달 LLM 기반 탐지 파이프라인이 다국어 게시글을 번역·분류해 RDS에 저장합니다. React 대시보드는 신뢰도 0.70 이상 탐지 결과, 기간별 Hotspots, 상세 근거, 알림 연동을 제공합니다.

## 주요 기능

- 한국·중국·대만 게임 커뮤니티 12개 enabled 사이트 + GitHub API 크롤링
- OpenAI gpt-4o 멀티모달 LLM 기반 불법 게시글 분류와 근거 생성 (single / agentic 2모드)
- agentic 모드: S0 정규화 → S1 트리아지(gpt-4o-mini) → S2b 외부 링크 1-hop 추적, 단계별 AI 검증 과정 기록
- 조치 우선순위와 최신 탐지 기준의 탐지 목록/상세 화면
- 최근 7일/30일 기준 Hotspots, Quick filters, 탐지 추이
- 수동 크롤링 트리거와 Discord/Slack/Google Chat/Teams webhook 알림 연동

## 아키텍처

<img src="docs/architecture.png" width="1000"/>

운영 환경은 단일 EC2에서 Redis, Tor, crawler, detection, API, dashboard, Caddy 7개 컨테이너를 Docker Compose로 실행합니다. 자세한 구조와 운영 결정은 [Architecture](https://github.com/byungju0/261RCOSE45700/wiki/Architecture-Overview)와 [docs/deployment.md](docs/deployment.md)를 참고하세요.

## 기술 스택

![skills](https://skillicons.dev/icons?i=react,vite,ts,tailwind,java,spring,python,postgres,redis,docker)

| 영역 | 기술 |
|---|---|
| Frontend | React 19, Vite 8, TypeScript 6, Tailwind CSS v4, TanStack Query v5, Recharts, MSW v2 |
| Backend | Java 21, Spring Boot 3.5, Spring Data JPA, Spring Data Redis, Springdoc OpenAPI |
| Database / Queue | PostgreSQL/RDS, Redis |
| Crawling | Python 3.11, crawl4ai, Playwright, APScheduler, Tor |
| Detection | Python 3.11, OpenAI multimodal LLM, token bucket, retry/DLQ |
| Infrastructure | Docker Compose, GitHub Actions, GHCR, Caddy, Prometheus, Grafana, AWS EC2/RDS |

## 시작하기

필요한 런타임:

- Python 3.11+
- Java 21 LTS
- Node.js 22 LTS
- Docker / Docker Compose

Windows에서는 `bin/` 대신 `Scripts\`, `./gradlew` 대신 `gradlew.bat`을 사용하세요.

```bash
git clone https://github.com/byungju0/261RCOSE45700.git
cd 261RCOSE45700

# Redis + PostgreSQL
# infra/.env.example은 gitignore 대상입니다. 팀에서 별도 공유하는 파일을 infra/.env로 복사하세요.
cp infra/.env.example infra/.env
docker compose -f infra/docker-compose.yml up -d

# crawler
python3 -m venv crawler/.venv
crawler/.venv/bin/pip install -r crawler/requirements.txt
crawler/.venv/bin/playwright install chromium

# detection
python3 -m venv detection/.venv
detection/.venv/bin/pip install -r detection/requirements.txt

# api
cd api && ./gradlew build && cd ..

# dashboard
cd dashboard && corepack enable && pnpm install && cd ..
```

대시보드 화면만 빠르게 확인하려면 백엔드 없이도 실행할 수 있습니다. `VITE_API_BASE_URL`이 비어 있으면 MSW v2 mock이 API 응답을 흉내냅니다.

```bash
cd dashboard
pnpm dev
```

자세한 로컬 셋업과 환경변수는 [Getting Started](https://github.com/byungju0/261RCOSE45700/wiki/Getting-Started)를 참고하세요.

## 저장소 구성

| 디렉터리 | 설명 |
|---|---|
| [crawler/](crawler/README.md) | Python · crawl4ai 크롤링 + APScheduler + S3 아카이브 · 186 tests |
| [detection/](detection/README.md) | Python · Redis 컨슈머 + OpenAI gpt-4o 멀티모달 LLM + single/agentic 모드 · 185 tests |
| [api/](api/README.md) | Java 21 + Spring Boot 3.5 · 탐지/통계/크롤/활동 로그/알림 REST API + Flyway V11 |
| [dashboard/](dashboard/README.md) | React 19 + Vite 8 · TanStack Query v5 · MSW v2 mock |
| [shared/](shared/README.md) | Python 공유 모듈 (correlation_id, CrawlEvent, LLM 인터페이스) |
| [infra/](infra/) | docker-compose (7컨테이너) + Caddy + Grafana/Prometheus |
| [docs/](docs/) | ADR + 배포 runbook + [agentic-pipeline.md](docs/agentic-pipeline.md) (AI 검증 과정 운영 가이드) |
| [_bmad-output/](_bmad-output/) | PRD · architecture · UX spec · 프로젝트 산출물 |

각 서브시스템의 상세 구조는 해당 디렉터리 README와 [Wiki](https://github.com/byungju0/261RCOSE45700/wiki)를 참고하세요.

## API 개요

Spring Boot API는 탐지 목록/상세, 기간별 통계, 크롤링 트리거/상태, 활동 로그, 알림 채널/규칙/전송 이력 엔드포인트를 제공합니다. 탐지 목록은 사이트, 유형, 언어, 날짜, 최근 7일/30일 필터를 지원합니다. 전체 엔드포인트 목록은 [api/README.md](api/README.md)를 참고하세요.

## 검증

```bash
crawler/.venv/bin/python -m pytest crawler/tests/unit -q
detection/.venv/bin/python -m pytest detection/tests/unit -q
cd api && ./gradlew build && cd ..
cd dashboard && pnpm build && pnpm test && cd ..
```

대시보드 E2E는 데스크톱과 Pixel 7 모바일 viewport로 분리돼 있습니다.

```bash
cd dashboard
pnpm exec playwright install --with-deps
pnpm e2e
```

## 배포

`main` 브랜치 push가 GitHub Actions `deploy.yml`을 트리거합니다. 워크플로는 각 서브시스템 테스트, GHCR 이미지 빌드, EC2 SSH 배포, healthcheck, 자동 롤백을 순서대로 수행합니다.

자세한 사양은 [CI/CD Pipeline](https://github.com/byungju0/261RCOSE45700/wiki/CI-CD-Pipeline), 운영 절차는 [docs/deployment.md](docs/deployment.md)에 있습니다.

## 문서

- [Wiki](https://github.com/byungju0/261RCOSE45700/wiki)
- [Architecture Overview](https://github.com/byungju0/261RCOSE45700/wiki/Architecture-Overview)
- [Getting Started](https://github.com/byungju0/261RCOSE45700/wiki/Getting-Started)
- [docs/deployment.md](docs/deployment.md)
- [docs/agentic-pipeline.md](docs/agentic-pipeline.md)
- [Sprint Status](https://github.com/byungju0/261RCOSE45700/wiki/Sprint-Status)

## Team

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/gitjay3">
        <img src="https://github.com/gitjay3.png" width="80px;" alt="박재성"/>
        <br /><sub><b>박재성</b></sub>
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/byungju0">
        <img src="https://github.com/byungju0.png" width="80px;" alt="최병주"/>
        <br /><sub><b>최병주</b></sub>
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/erdmee">
        <img src="https://github.com/erdmee.png" width="80px;" alt="일드매"/>
        <br /><sub><b>일드매</b></sub>
      </a>
    </td>
  </tr>
</table>
