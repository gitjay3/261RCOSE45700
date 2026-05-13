# Story 4.7: 대시보드 모바일 지원

Status: in-progress

## Pivot Background

PRD L233 / UX Spec L1503·L1567의 "모바일 out-of-scope, Growth 단계 백로그" 결정을 폐기하는 PIVOT (2026-05-13). 외부 운영자가 모바일 환경에서도 긴급 조치(원본 URL 점프 + 수동 크롤링 트리거)를 수행해야 한다는 운영 요구로 Growth 단계 항목을 MVP로 끌어옴.

Backport 산출물:
- PRD L233: "데스크톱 1280px+ 우선 / 모바일 < 768px 지원" 으로 정정
- PRD L323: "모바일 반응형 대시보드" out-of-scope → "MVP로 편입"
- UX Spec L120·L1503·L1567: 모바일 차단/햄버거 X 결정 폐기, Tailwind `md` 768px breakpoint 정책 추가
- UX Spec Design System: 다크 모드 미적용 결정도 함께 폐기 (디자인 시스템 v10 라이트/다크 양쪽 토큰 정의됨)
- epics.md: UX-DR7 추가, Story 4.7 신설
- architecture.md: Important Decisions에 모바일 / 색 모드 / PWA 결정 추가

## Story

외부 운영자로서,
Tracker 대시보드를 모바일 (< 768px) 환경에서도 사용할 수 있기를 원한다,
그래서 알림을 받았을 때 노트북 없이도 탐지 상세를 확인하고 원본 URL로 점프해 조치할 수 있다.

## Acceptance Criteria

1. **Given** Tailwind `md` (768px) breakpoint 를 모바일 분기로 채택할 때 **When** `< 768px` 뷰포트로 접속하면 **Then** `useIsMobile()` 훅(`window.matchMedia('(max-width: 767px)')`)이 모바일 상태를 반환한다
2. **And** Sidebar 는 `< lg` 뷰포트에서 햄버거 버튼(`aria-label="메뉴 열기"`) 클릭 → vaul drawer 가 슬라이드로 등장한다
3. **And** 라우트 전환 시 drawer 가 자동으로 닫힌다 (translate-x-full 로 viewport 밖 이동)
4. **And** DetectionList 는 `< md` 에서 `<table>` 이 hidden, `DetectionCard` 그리드로 교체된다 — 행 클릭 = 상세 진입
5. **And** 모바일에서 가로 스크롤(horizontal table overflow) 0
6. **And** FilterBar 는 `< md` 에서 "필터" 버튼 → bottom Drawer(vaul) 로 전체 필터 패널(날짜·사이트·유형·언어)이 표시된다
7. **And** Dashboard / Detection Detail / Stats 페이지는 `< 768px` 에서 카드·차트가 단일 컬럼으로 stack 되며 가로 스크롤 없이 표시된다
8. **And** 키보드 단축키(j/k/enter/o/c/esc/g+t/g+d/g+l/g+s)는 데스크톱 전용으로 유지되며, 모바일에서는 비활성화된다 (cheatsheet 도 노출되지 않음)
9. **And** Playwright e2e `e2e/mobile.mobile.spec.ts` 에 Pixel 7 viewport 시나리오 3건이 포함된다 (햄버거 drawer / DetectionList 카드 / FilterBar bottom Drawer)
10. **And** 다크 테마는 `next-themes` + `data-theme` 토글로 활성화되며, FOUC 가드 인라인 스크립트(`index.html`)가 `localStorage('theme') → prefers-color-scheme → light` 우선순위로 동기 적용된다
11. **And** `vite-plugin-pwa` 가 도입되어 manifest + workbox 정적 자산 캐시(이미지/폰트만)를 제공한다 — `navigateFallbackDenylist: [/^\/api/]` 로 API 응답은 캐시 차단
12. **And** Story 4.5/4.6 의 데스크톱 키보드 네비게이션·테이블 레이아웃 회귀가 발생하지 않는다 (기존 데스크톱 e2e PASS 유지)

## Tasks / Subtasks

- [x] **Task 1: 모바일 감지 훅** (AC: #1)
  - [x] 1.1 `dashboard/src/lib/useIsMobile.ts` 작성 — `window.matchMedia('(max-width: 767px)')` 구독, SSR 가드 불요(Vite SPA)
  - [x] 1.2 매체 변경 이벤트 구독/해제

- [x] **Task 2: Sidebar 햄버거 drawer** (AC: #2, #3)
  - [x] 2.1 `dashboard/src/layouts/Sidebar.tsx` 햄버거 버튼 추가 (`< lg` 에서만 노출)
  - [x] 2.2 `< lg` 에서 translate-x-full 로 viewport 밖 → 클릭 시 슬라이드 인
  - [x] 2.3 라우트 전환 감지 → 자동 닫힘
  - [x] 2.4 `aria-label="주 탐색"` accessible name 부여

- [x] **Task 3: vaul drawer primitive** (AC: #2, #6)
  - [x] 3.1 `dashboard/src/components/ui/drawer.tsx` 신규 (shadcn drawer pattern + vaul)
  - [x] 3.2 bottom variant 지원 (FilterBar 용)

- [x] **Task 4: DetectionList 카드 뷰** (AC: #4, #5)
  - [x] 4.1 `dashboard/src/components/tracker/DetectionCard.tsx` 신규 — 신뢰도 배지 + 제목 + 메타 + 행 클릭
  - [x] 4.2 `dashboard/src/pages/DetectionList/index.tsx` — `< md` 에서 `<table>` 숨김, `DetectionCard` 그리드 노출
  - [x] 4.3 `button` role + `aria-label="탐지 상세 열기"` 부여

- [ ] **Task 5: FilterBar bottom Drawer** (AC: #6)
  - [ ] 5.1 "필터" 트리거 버튼 (< md 에서만 노출)
  - [ ] 5.2 vaul bottom Drawer 에 기존 4종 Select 패널을 stack

- [ ] **Task 6: Dashboard / DetectionDetail / Stats 단일 컬럼 stack** (AC: #7)
  - [ ] 6.1 Dashboard 차트 grid `md:grid-cols-2` → `< md` 1열
  - [ ] 6.2 DetectionDetail 50:50 bilingual → `< md` stack (원문 → 번역)
  - [ ] 6.3 Stats 4 차트 → `< md` 1열 stack
  - [ ] 6.4 PageContainer padding 모바일 16px

- [ ] **Task 7: 키보드 단축키 모바일 비활성** (AC: #8)
  - [ ] 7.1 `GlobalShortcutProvider` 에서 `useIsMobile()` 분기 → 모바일에서 no-op
  - [ ] 7.2 `?` cheatsheet 도 모바일에서 미노출

- [x] **Task 8: Playwright 모바일 e2e** (AC: #9)
  - [x] 8.1 `dashboard/playwright.config.ts` — Pixel 7 device descriptor 추가, `mobile.mobile.spec.ts` glob 매칭
  - [x] 8.2 `dashboard/e2e/mobile.mobile.spec.ts` — 햄버거 drawer / DetectionList 카드 / FilterBar Drawer 3 시나리오

- [x] **Task 9: 다크 테마 활성** (AC: #10)
  - [x] 9.1 `next-themes` 의존성 추가, ThemeProvider 적용
  - [x] 9.2 `index.html` FOUC 가드 인라인 스크립트 — `localStorage('theme') → prefers-color-scheme → light`
  - [x] 9.3 디자인 시스템 v10 라이트/다크 토큰 양쪽 정의 확인 (`--chart-1~5`, `--primary`, `--border`, `--muted-foreground`, brand cyan deep `#0a5273` 등)

- [x] **Task 10: PWA 도입** (AC: #11)
  - [x] 10.1 `vite-plugin-pwa` devDependency 추가
  - [x] 10.2 `vite.config.ts` VitePWA 구성 — `registerType: 'prompt'`, manifest, workbox runtime cache(이미지/폰트만, `navigateFallbackDenylist: [/^\/api/]`), `devOptions.enabled: false` (dev에서는 MSW 우선)

- [ ] **Task 11: 회귀 검증** (AC: #12)
  - [ ] 11.1 데스크톱 단축키 e2e PASS 유지
  - [ ] 11.2 테이블 뷰 `>= md` PASS 유지
  - [ ] 11.3 Vitest 단위 테스트 회귀 0

## Deferred

- Tailscale / Cloudflare Tunnel 등 외부 모바일 접근 SaaS — Story 5.2 PIVOT 결정(`feedback_no_external_services`) 유지. EC2 22번 SSH `0.0.0.0/0` + defense-in-depth로 진행.
- 모바일 / 태블릿 별도 시각 디자인 — 8px 그리드 + zinc + NC AI 브랜드 토큰을 그대로 유지하며 레이아웃 분기만.
- 푸시 알림(Web Push) — Growth 단계 백로그. PWA manifest 도입은 설치성 + 홈스크린만 목적.

## Dev Log

- 2026-05-13: Story 신설, `feat/dashboard-mobile-support` 브랜치 작업 중. Task 1~4 + 8~10 코드 푸시 완료, Task 5~7 + 11 진행 중.
