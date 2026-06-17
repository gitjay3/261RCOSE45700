"""URL 역할 판정 공통 정책.

Normalizer와 LinkTracer가 같은 기준으로 redirect wrapper, 공식 서비스 도메인,
공식 설치/스토어 문맥을 해석하도록 작은 공통 모듈로 둔다.
"""

from __future__ import annotations

import os
from urllib.parse import parse_qs, urlsplit

_DEFAULT_OFFICIAL_SERVICE_SUFFIXES = (
    # NC / PURPLE
    "plaync.com",
    "nc.com",
    "ncsoft.com",
    "ncupdate.com",
    # 주요 퍼블리셔/플랫폼. 공식 설치/스토어 문맥일 때만 감점/예외 처리한다.
    "nexon.com",
    "nexon.co.kr",
    "netmarble.com",
    "kakaogames.com",
    "wemade.com",
    "pearlabyss.com",
    "gravity.co.kr",
    "steampowered.com",
    "epicgames.com",
    "play.google.com",
    "apps.apple.com",
    "playstation.com",
    "xbox.com",
    "nintendo.com",
)

_REDIRECT_WRAPPER_HOSTS = (
    "ref.gamer.com.tw",
)

_OFFICIAL_INSTALL_CONTEXT_HINTS = (
    "download",
    "downloads",
    "install",
    "installer",
    "launcher",
    "client",
    "store",
    "steam",
    "epic games",
    "google play",
    "app store",
    "purple",
    "official",
    "다운로드",
    "설치",
    "런처",
    "클라이언트",
    "스토어",
    "下載",
    "下载",
    "安裝",
    "安装",
    "啟動器",
    "启动器",
    "官方",
)


def _env_suffixes() -> tuple[str, ...]:
    raw = os.environ.get("OFFICIAL_SERVICE_DOMAIN_SUFFIXES", "")
    return tuple(part.strip().lower() for part in raw.split(",") if part.strip())


def official_service_suffixes() -> tuple[str, ...]:
    """기본 공식 도메인 suffix + 환경변수 확장 목록."""
    return _DEFAULT_OFFICIAL_SERVICE_SUFFIXES + _env_suffixes()


def is_http_url(url: str) -> bool:
    return url.lower().startswith(("http://", "https://"))


def unwrap_redirect_url(url: str) -> str:
    """커뮤니티 redirect wrapper URL이면 실제 목적지 URL을 반환한다."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return url
    host = (parsed.hostname or "").lower()
    if host in _REDIRECT_WRAPPER_HOSTS:
        target = (parse_qs(parsed.query).get("url") or [""])[0].strip()
        if is_http_url(target):
            return target
    return url


def is_official_service_url(url: str) -> bool:
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return False
    return any(host == suffix or host.endswith("." + suffix) for suffix in official_service_suffixes())


def has_official_install_context(url: str, *texts: str) -> bool:
    """공식 도메인이더라도 설치/스토어/런처 문맥일 때만 공식 다운로드 예외를 적용한다."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        haystack = url.lower()
    else:
        haystack = f"{parsed.netloc} {parsed.path} {parsed.query}".lower()
    if texts:
        haystack = f"{haystack} {' '.join(texts).lower()}"
    return any(hint.lower() in haystack for hint in _OFFICIAL_INSTALL_CONTEXT_HINTS)


def official_service_reason(url: str, *texts: str) -> str | None:
    if is_official_service_url(url) and has_official_install_context(url, *texts):
        return "official_service_install_link"
    return None
