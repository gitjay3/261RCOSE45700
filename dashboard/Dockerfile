# syntax=docker/dockerfile:1.7
# Dashboard — Vite static build → nginx:alpine
# Story 5.2: BuildKit multi-stage with registry cache mode=max.

# ---------- builder ----------
FROM node:20.19-alpine AS builder

WORKDIR /app

COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci

COPY dashboard/ ./
# `npm run build` = `tsc -b && vite build` (typecheck + bundle).
RUN npm run build

# ---------- runtime ----------
FROM nginx:1.27-alpine AS runtime

# nginx는 SIGQUIT로 graceful shutdown. compose는 기본 SIGTERM이라 STOPSIGNAL을
# 명시하지 않으면 10s 후 SIGKILL로 강제 종료된다.
STOPSIGNAL SIGQUIT

# Single-page-app fallback + healthcheck endpoint.
RUN printf '%s\n' \
    'server {' \
    '    listen 80 default_server;' \
    '    server_name _;' \
    '    root /usr/share/nginx/html;' \
    '    index index.html;' \
    '    gzip on;' \
    '    gzip_types text/css application/javascript application/json image/svg+xml;' \
    '    location /healthz { return 200 "ok\n"; add_header Content-Type text/plain; }' \
    '    location / { try_files $uri $uri/ /index.html; }' \
    '}' \
    > /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost/healthz >/dev/null || exit 1
