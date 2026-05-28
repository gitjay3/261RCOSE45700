# syntax=docker/dockerfile:1.7
# Dashboard — Vite static build → nginx:alpine
# Story 5.2: BuildKit multi-stage with registry cache mode=max.

# ---------- builder ----------
# Node 22 LTS — @eslint-react/* (require >=22) 호환. CI(dashboard.yml)도 22로 통일.
# corepack 활성화로 packageManager 필드의 pnpm 버전 자동 활성. (Node 16.9+)
FROM node:22-alpine AS builder

# pnpm fetch 방식이 아니라 표준 install: lockfile + workspace 설정만 먼저 복사해
# 의존성 레이어 캐시. pnpm-workspace.yaml은 overrides 적용에 필수 (pnpm 11부터
# package.json#pnpm.overrides 무시 — pnpm/pnpm#11536).
WORKDIR /app
COPY dashboard/package.json dashboard/pnpm-lock.yaml dashboard/pnpm-workspace.yaml ./

# corepack은 packageManager 필드(pnpm@11.1.1)를 읽어 자동 활성.
# package.json을 먼저 COPY해야 `corepack prepare --activate`가 현재 디렉토리에서
# packageManager 필드를 찾을 수 있다. 그렇지 않으면 ERR_NO_PROJECT_FOUND.
# 단일 RUN — 동일한 cache invalidation 트리거(앞 COPY 변경)에 묶이므로 분리 무의미.
RUN corepack enable \
  && corepack prepare --activate \
  && pnpm install --frozen-lockfile

COPY dashboard/ ./
# VITE_USE_MOCK=true 빌드 시 MSW worker가 dist/에 보존되고 main.tsx가 prod에서도 MSW 활성.
# 백엔드(OpenAI/RDS) 셋업 전 frontend-only 데모용 (compose.demo.yml + deploy-demo.yml).
ARG VITE_USE_MOCK=false
ENV VITE_USE_MOCK=$VITE_USE_MOCK
# `pnpm build` = `tsc -b && vite build` (typecheck + bundle).
RUN pnpm build

# ---------- runtime ----------
FROM nginx:1.27-alpine AS runtime

# nginx는 SIGQUIT로 graceful shutdown. compose는 기본 SIGTERM이라 STOPSIGNAL을
# 명시하지 않으면 10s 후 SIGKILL로 강제 종료된다.
STOPSIGNAL SIGQUIT

# SPA fallback + healthcheck + /api reverse proxy.
# /api 추가 사유: dashboard/src/api/client.ts baseURL 기본값이 '/api' (VITE_API_BASE_URL
# 미설정 시). API controller는 @RequestMapping("/api")로 /api/detections, /api/stats,
# /api/crawl/trigger를 노출. 같은 docker network `tracker-net` 안의 api 컨테이너로
# proxy_pass — same-origin이라 CORS 불필요. proxy_pass에 trailing slash 없음 →
# request URI(`/api/detections`)가 그대로 forward되어 Spring controller mapping
# 매칭. /api 미정의 시 SPA fallback `location /`이 index.html 반환 → frontend가
# JSON 기대했는데 HTML 받아 데이터 로딩 fail.
RUN printf '%s\n' \
    'server {' \
    '    listen 80 default_server;' \
    '    server_name _;' \
    '    root /usr/share/nginx/html;' \
    '    index index.html;' \
    '    gzip on;' \
    '    gzip_types text/css application/javascript application/json image/svg+xml;' \
    '    # Security headers — 브라우저 클릭재킹·MIME 스니핑·XSS 기본 방어.' \
    '    add_header X-Content-Type-Options "nosniff" always;' \
    '    add_header X-Frame-Options "DENY" always;' \
    '    add_header Referrer-Policy "strict-origin-when-cross-origin" always;' \
    '    # XSS Auditor는 레거시·버그 多 → 0으로 비활성(modern best practice).' \
    '    add_header X-XSS-Protection "0" always;' \
    '    # CSP: Pretendard CDN(jsdelivr) 허용. Vite 빌드가 인라인 스크립트를 주입.' \
    '    add_header Content-Security-Policy "default-src '"'"'self'"'"'; script-src '"'"'self'"'"' '"'"'unsafe-inline'"'"'; style-src '"'"'self'"'"' '"'"'unsafe-inline'"'"' https://cdn.jsdelivr.net; img-src '"'"'self'"'"' data:; connect-src '"'"'self'"'"'; font-src '"'"'self'"'"' data: https://cdn.jsdelivr.net; frame-ancestors '"'"'none'"'"';" always;' \
    '    location /healthz { return 200 "ok\n"; add_header Content-Type text/plain; }' \
    '    # docker network embedded DNS — api 컨테이너 재시작 시 IP 갱신 (10s TTL).' \
    '    # resolver + 변수 기반 proxy_pass 패턴 없으면 nginx가 worker 시작 시 1회만' \
    '    # resolve → api 컨테이너 IP 변경 후 영구 502 Bad Gateway 발생.' \
    '    resolver 127.0.0.11 valid=10s ipv6=off;' \
    '    location /api {' \
    '        set $api_upstream "http://api:8080";' \
    '        proxy_pass $api_upstream;' \
    '        proxy_set_header Host $host;' \
    '        proxy_set_header X-Real-IP $remote_addr;' \
    '        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;' \
    '        proxy_set_header X-Forwarded-Proto $scheme;' \
    '        proxy_read_timeout 30s;' \
    '    }' \
    '    location / { try_files $uri $uri/ /index.html; }' \
    '}' \
    > /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
# `localhost`는 Docker v26+ /etc/hosts에서 IPv6(::1)와 IPv4(127.0.0.1) 양쪽으로
# 매핑되고, BusyBox wget은 getaddrinfo의 첫 주소(::1)만 시도하고 fallback이 없다.
# nginx `listen 80`은 IPv4(0.0.0.0)만 바인딩 → ::1로의 connect는 Connection refused
# → healthcheck가 항상 실패한다 (외부 트래픽은 정상이나 healthcheck만 비대칭 실패).
# 127.0.0.1로 명시해 IPv4 강제. 참조: nginx trac #2400, alpine/aports #10937.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/healthz >/dev/null || exit 1
