#!/bin/sh
# Story 5.2 — Docker secrets → process env bridge.
#
# compose.prod.yml mounts secret files at /run/secrets/<name>. Application code
# reads `os.environ["OPENAI_API_KEY"]`, `os.environ["DB_PASSWORD"]`, etc.,
# so this shim exports each file's
# contents as the upper-case env var of the file's basename, then exec's CMD.
#
# Convention: file `openai_api_key` → env `OPENAI_API_KEY`.
# Dots/dashes in filenames are normalized to underscores.
# Secret files MUST be single-line ASCII. Multi-line / non-ASCII names are
# rejected with a warning (multi-line secrets should be base64-encoded by the
# operator and decoded by the application).
set -e

if [ -d /run/secrets ]; then
    for f in /run/secrets/*; do
        [ -f "$f" ] || continue
        if [ ! -r "$f" ]; then
            echo "secret-shim: WARNING: $f is not readable by $(id -u), skipping" >&2
            continue
        fi
        name=$(basename "$f")
        # 비-ASCII / 비-허용문자 secret 이름은 거부 — 알파벳/숫자/점/대시/언더스코어만.
        case "$name" in
            *[!a-zA-Z0-9._-]*)
                echo "secret-shim: WARNING: rejecting secret with non-portable name: $name" >&2
                continue
                ;;
        esac
        # POSIX locale 강제로 Turkish 등 locale별 대소문자 매핑 차이 회피.
        var=$(LC_ALL=C printf '%s' "$name" | LC_ALL=C tr 'a-z' 'A-Z' | LC_ALL=C tr '.-' '_')
        # CRLF / 후행 newline 제거 후 본문 추출. tr -d '\r\n'로 모든 줄바꿈 제거 —
        # 운영자가 Windows 클립보드에서 paste한 시크릿(\r 포함)도 안전하게 처리.
        value=$(LC_ALL=C tr -d '\r\n' < "$f")
        # shellcheck disable=SC2163
        export "${var}=${value}"
    done
fi

exec "$@"
