# syntax=docker/dockerfile:1.7
# Dashboard — Vite static build → nginx:alpine
# Story 5.2: BuildKit multi-stage with registry cache mode=max.

# ---------- builder ----------
# Node 22 LTS — @eslint-react/* (require >=22) 호환. CI(dashboard.yml)도 22로 통일.
FROM node:22-alpine AS builder

WORKDIR /app

COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci

COPY dashboard/ ./
# VITE_USE_MOCK=true 빌드 시 MSW worker가 dist/에 보존되고 main.tsx가 prod에서도 MSW 활성.
# 백엔드(VARCO/RDS) 셋업 전 frontend-only 데모용 (compose.demo.yml + deploy-demo.yml).
ARG VITE_USE_MOCK=false
ENV VITE_USE_MOCK=$VITE_USE_MOCK
# `npm run build` = `tsc -b && vite build` (typecheck + bundle).
RUN npm run build

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
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost/healthz >/dev/null || exit 1
