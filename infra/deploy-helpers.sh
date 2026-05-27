#!/usr/bin/env bash
# 배포 워크플로(.github/workflows/deploy*.yml)의 SSH 스크립트에서 source.
# EC2 /opt/app/ 으로 SCP 후 `source /opt/app/deploy-helpers.sh`로 로드.
#
# 제공 함수:
#   setup_docker          — DOCKER + DCOMPOSE 전역 set, docker 미설치 시 exit 1
#   ghcr_login            — GHCR_USER/GHCR_TOKEN env로 로그인 + EXIT trap으로 자격증명 청소
#   compose_pull_retry F  — `docker compose -f F pull` 3-retry, 실패 시 exit 3

setup_docker() {
  DOCKER="$(command -v docker)" || { echo "::error::docker not found in PATH"; exit 1; }
  DCOMPOSE="$DOCKER compose"
}

# GHCR 자격증명이 ~/.docker/config.json에 영속되지 않도록 EXIT 시 logout.
# unset GHCR_TOKEN으로 /proc/<pid>/environ 노출 창 단축.
ghcr_login() {
  # shellcheck disable=SC2064  # 의도적 즉시 확장 — $DOCKER 값이 trap 등록 시점에 박혀야 함.
  trap "\"$DOCKER\" logout ghcr.io >/dev/null 2>&1 || true" EXIT
  if ! printf '%s' "$GHCR_TOKEN" | "$DOCKER" login ghcr.io -u "$GHCR_USER" --password-stdin; then
    echo "::error::GHCR login failed"
    exit 2
  fi
  unset GHCR_TOKEN
}

# 일시적 GHCR 5xx / rate-limit 대비 3-회 재시도.
compose_pull_retry() {
  local compose_file="$1"
  for i in 1 2 3; do
    if $DCOMPOSE -f "$compose_file" pull; then
      return 0
    fi
    echo "::warning::compose pull attempt $i failed, retrying in 5s..."
    sleep 5
  done
  echo "::error::compose pull failed after 3 attempts"
  exit 3
}
