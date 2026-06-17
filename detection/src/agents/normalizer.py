"""S0 Normalizer — 순수 Python 텍스트 정규화 + 링크 추출 (Story 3-7, LLM 없음, $0).

운영자 "텍스트 클린 에이전트" 요청 구현. 변형문자·우회 표기로 LLM 분류를 흐리는 게시글을
정규화하고, 본문에서 외부 링크를 추출해 LinkTracer(S2b) 입력으로 넘긴다.

수행:
  1. NFKC 정규화 — 전각/반각·합자·호환 문자 통일
  2. zero-width 문자 제거 — U+200B~200D, U+FEFF, U+2060 등 (단어 사이 끼워 우회)
  3. 변형문자 정적 매핑 — 라틴/키릴 등으로 위장한 한글 자모를 복원 (ㅎr킹 → 하킹 등)
  4. 반복문자 축약 — 3회 이상 연속 동일 문자를 2회로 (ㅋㅋㅋㅋ → ㅋㅋ)
  5. 링크 추출 — HTML <a href> 우선, markdown [text](url), bare URL 순으로 추출·중복 제거
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

import regex as _regex
from bs4 import BeautifulSoup

from detection.src.agents.contracts import NormalizedPost
from detection.src.agents.url_policy import is_http_url, official_service_reason, unwrap_redirect_url

try:
    from w3lib.html import get_meta_refresh as _w3_get_meta_refresh
    from w3lib.url import canonicalize_url as _w3_canonicalize_url
except ImportError:  # pragma: no cover - dependency is declared; fallback keeps local dev resilient.
    _w3_get_meta_refresh = None
    _w3_canonicalize_url = None

# Unicode Cf (Format) 카테고리 전체 제거 — zero-width, bidi control, variation selector,
# Unicode Tag block(U+E0001, U+E0020-U+E007F) 등 키워드 우회에 쓰이는 모든 포맷 문자를 커버.
# 수동 집합 대신 \p{Cf}를 쓰는 이유: 미래 Unicode 버전 추가분도 자동 포함되고,
# bidi mark(U+200E/F), variation selector(U+FE00-FE0F) 등 기존 집합의 누락분을 보완.
_FORMAT_CHAR_RE = _regex.compile(r"\p{Cf}")

# 변형문자 정적 매핑 — 라틴/키릴/그리스 동형 글리프를 ASCII로 복원.
# NFKC는 호환 동치만 처리하며 크로스-스크립트 confusable(키릴 а vs 라틴 a 등)은 그대로 둔다.
# UTS #39 confusables.txt 기준 확실한 1:1 동형만 등록 — 과도 치환으로 정상 본문을 깨뜨리지 않는다.
_HOMOGLYPH_MAP = {
    # 키릴 소문자 → 라틴
    "а": "a",   # а CYRILLIC SMALL LETTER A
    "е": "e",   # е CYRILLIC SMALL LETTER IE
    "о": "o",   # о CYRILLIC SMALL LETTER O
    "р": "p",   # р CYRILLIC SMALL LETTER ER
    "с": "c",   # с CYRILLIC SMALL LETTER ES
    "х": "x",   # х CYRILLIC SMALL LETTER HA
    "у": "y",   # у CYRILLIC SMALL LETTER U
    # 키릴 대문자 → 라틴 대문자
    "В": "B",   # В CYRILLIC CAPITAL LETTER VE
    "Н": "H",   # Н CYRILLIC CAPITAL LETTER EN
    "М": "M",   # М CYRILLIC CAPITAL LETTER EM
    "Т": "T",   # Т CYRILLIC CAPITAL LETTER TE
    "К": "K",   # К CYRILLIC CAPITAL LETTER KA
    "А": "A",   # А CYRILLIC CAPITAL LETTER A
    "Е": "E",   # Е CYRILLIC CAPITAL LETTER IE
    "О": "O",   # О CYRILLIC CAPITAL LETTER O
    "Р": "P",   # Р CYRILLIC CAPITAL LETTER ER
    "С": "C",   # С CYRILLIC CAPITAL LETTER ES
    "Х": "X",   # Х CYRILLIC CAPITAL LETTER HA
    # 그리스 소문자 → 라틴 (명확한 동형만)
    "ο": "o",   # ο GREEK SMALL LETTER OMICRON
    "α": "a",   # α GREEK SMALL LETTER ALPHA
    "ε": "e",   # ε GREEK SMALL LETTER EPSILON
    "κ": "k",   # κ GREEK SMALL LETTER KAPPA (approximate)
    "ν": "v",   # ν GREEK SMALL LETTER NU
}

# 3회 이상 연속 동일 문자 → 2회로 축약 (의미 보존하며 토큰·노이즈 절감).
_REPEAT_RE = re.compile(r"(.)\1{2,}", re.DOTALL)

# 링크드 이미지: [![alt](img_url)](href_url) — href만 추출 (img_url은 배포 링크가 아님)
_MD_LINKED_IMG_RE = re.compile(
    r"\[!\[([^\]]*)\]\([^)]*\)\]\((https?://[^\s)]+)\)",
    re.IGNORECASE,
)
# markdown 링크: [텍스트](URL)
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^\s)]+)\)", re.IGNORECASE)
# bare URL: http(s):// 로 시작. 끝의 흔한 구두점은 제외.
_BARE_URL_RE = re.compile(r"https?://[^\s<>\"'()\[\]]+", re.IGNORECASE)
_META_REFRESH_URL_RE = re.compile(r"(?:^|;)\s*url\s*=\s*['\"]?([^'\";]+)", re.IGNORECASE)
_JS_LOCATION_URL_RE = re.compile(
    r"""(?:window\.)?location(?:\.href)?\s*=\s*['"](?P<assign>https?://[^'"]+)['"]"""
    r"""|(?:window\.)?location\.(?:replace|assign)\(\s*['"](?P<call>https?://[^'"]+)['"]""",
    re.IGNORECASE,
)
_TRAILING_PUNCT = ".,;:!?。，"  # 영문/한중일 마침표·쉼표

_DOWNLOAD_EXTENSIONS = (
    ".apk",
    ".bat",
    ".bin",
    ".cmd",
    ".dmg",
    ".exe",
    ".dll",
    ".ipa",
    ".jar",
    ".msi",
    ".rar",
    ".scr",
    ".tar",
    ".tar.gz",
    ".zip",
    ".7z",
)
_STATIC_EXTENSIONS = (
    ".avif",
    ".css",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".png",
    ".svg",
    ".webp",
)
_STATIC_HOST_HINTS = (
    "img.shields.io",
    "badge.fury.io",
    "raw.githubusercontent.com",
    "github.com/user-attachments/assets",
)
_DISTRIBUTION_HOST_HINTS = (
    "discord.gg",
    "discord.com/invite",
    "drive.google.com",
    "dropbox.com",
    "gofile.io",
    "mega.nz",
    "mediafire.com",
    "t.me",
    "telegram.me",
    "github.com/user-attachments/files",
)
_DISTRIBUTION_PATH_HINTS = (
    "/download",
    "/downloads",
    "/release",
    "/releases",
    "/releases/download",
    "/invite",
    "/file",
    "/files",
)
_DISTRIBUTION_TEXT_HINTS = (
    "download",
    "release",
    "cheat",
    "hack",
    "다운",
    "다운로드",
    "배포",
    "판매",
    "구매",
    "무료",
    "가입",
    "텔레그램",
    "디스코드",
    "下载",
    "外掛",
)
_METADATA_CANDIDATE_LIMIT = 50
_METADATA_ALIAS_LIMIT = 50


@dataclass(frozen=True)
class LinkCandidate:
    """추적 후보 URL. 외부 계약은 list[str]로 유지하고 내부 정렬에만 사용한다."""

    url: str
    canonical_url: str
    source_kind: str
    priority: int
    order: int
    text: str = ""
    reasons: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()


def _strip_zero_width(text: str) -> str:
    return _FORMAT_CHAR_RE.sub("", text)


def _map_homoglyphs(text: str) -> str:
    return "".join(_HOMOGLYPH_MAP.get(ch, ch) for ch in text)


def _collapse_repeats(text: str) -> str:
    return _REPEAT_RE.sub(r"\1\1", text)


def _canonical_url(url: str, *, keep_query: bool = False) -> str:
    try:
        normalized = (
            _w3_canonicalize_url(url.strip(), keep_fragments=False)
            if _w3_canonicalize_url
            else url.strip()
        )
        parsed = urlsplit(normalized)
    except ValueError:
        return url.strip().rstrip("/")
    if not parsed.scheme or not parsed.netloc:
        return url.strip().rstrip("/")

    hostname = (parsed.hostname or "").lower()
    port = parsed.port
    default_port = (
        (parsed.scheme.lower() == "http" and port == 80)
        or (parsed.scheme.lower() == "https" and port == 443)
    )
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"
    path = parsed.path.rstrip("/") or "/"
    query = parsed.query if keep_query else ""
    return urlunsplit((parsed.scheme.lower(), netloc, path, query, ""))


def _extract_meta_refresh_urls(text: str, soup: BeautifulSoup) -> list[str]:
    urls: list[str] = []
    if _w3_get_meta_refresh:
        _, refresh_url = _w3_get_meta_refresh(text)
        if refresh_url:
            urls.append(refresh_url)

    for tag in soup.find_all("meta"):
        http_equiv = (tag.get("http-equiv") or "").lower()
        if http_equiv != "refresh":
            continue
        content = tag.get("content") or ""
        match = _META_REFRESH_URL_RE.search(content)
        if match:
            urls.append(match.group(1))

    return urls


def _clean_url(url: str) -> str:
    return (url or "").strip().rstrip(_TRAILING_PUNCT)


def _url_text_for_scoring(url: str) -> str:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return url.lower()
    return f"{parsed.netloc}{parsed.path}".lower()


def _distribution_reasons(url: str, text: str = "") -> list[str]:
    lowered = _url_text_for_scoring(url)
    text_lower = text.lower()
    reasons: list[str] = []
    if lowered.endswith(_DOWNLOAD_EXTENSIONS):
        reasons.append("download_file_extension")
    if any(hint in lowered for hint in _DISTRIBUTION_HOST_HINTS):
        reasons.append("distribution_host_hint")
    if any(hint in lowered for hint in _DISTRIBUTION_PATH_HINTS):
        reasons.append("distribution_path_hint")
    if any(hint in text_lower for hint in _DISTRIBUTION_TEXT_HINTS):
        reasons.append("distribution_text_hint")
    return reasons


def _static_reasons(url: str, source_kind: str) -> list[str]:
    lowered = _url_text_for_scoring(url)
    reasons: list[str] = []
    if source_kind in {"image_src", "script_src", "link_href"}:
        reasons.append(f"low_value_{source_kind}")
    if any(hint in lowered for hint in _STATIC_HOST_HINTS):
        reasons.append("static_host_hint")
    if lowered.endswith(_STATIC_EXTENSIONS):
        reasons.append("static_file_extension")
    return reasons


def _score_candidate(source_kind: str, url: str, text: str = "") -> tuple[int, tuple[str, ...]]:
    reasons: list[str] = []
    static_reasons = _static_reasons(url, source_kind)
    if static_reasons:
        reasons.extend(static_reasons)
        return 10, tuple(reasons)

    official_reason = official_service_reason(url, text)
    if official_reason:
        reasons.append(official_reason)
        return 40, tuple(reasons)

    distribution_reasons = _distribution_reasons(url, text)
    if distribution_reasons:
        reasons.extend(distribution_reasons)
        return 100, tuple(reasons)

    if source_kind in {"anchor_href", "markdown_href", "linked_image_href"}:
        reasons.append(f"primary_destination:{source_kind}")
        return 80, tuple(reasons)
    if source_kind in {"meta_refresh", "iframe_src", "frame_src", "js_location"}:
        reasons.append(f"redirect_or_embedded_destination:{source_kind}")
        return 70, tuple(reasons)
    if source_kind == "bare_url":
        reasons.append("generic_bare_url")
        return 60, tuple(reasons)

    reasons.append(f"generic_url:{source_kind}")
    return 50, tuple(reasons)


def _candidate_sort_key(candidate: LinkCandidate) -> tuple[int, int]:
    return (-candidate.priority, candidate.order)


def extract_link_candidates(
    text: str,
    *,
    exclude_urls: list[str] | None = None,
) -> list[LinkCandidate]:
    """본문에서 URL 후보를 만들고, 정규화 URL 단위로 최선 후보만 남긴다."""
    excluded = {_canonical_url(url) for url in (exclude_urls or []) if url}
    best_by_canonical: dict[str, LinkCandidate] = {}
    aliases_by_canonical: dict[str, list[str]] = {}
    order = 0

    def _add(raw_url: str, source_kind: str, context_text: str = "") -> None:
        nonlocal order
        original_url = _clean_url(raw_url)
        url = unwrap_redirect_url(original_url)
        if not url or not is_http_url(url):
            return
        canonical = _canonical_url(url, keep_query=True)
        exclusion_canonical = _canonical_url(url)
        if exclusion_canonical in excluded:
            return
        priority, reasons = _score_candidate(source_kind, url, context_text)
        candidate = LinkCandidate(
            url=url,
            canonical_url=canonical,
            source_kind=source_kind,
            priority=priority,
            order=order,
            text=context_text.strip(),
            reasons=reasons,
        )
        order += 1

        aliases = aliases_by_canonical.setdefault(canonical, [])
        if original_url != url and original_url not in aliases:
            aliases.append(original_url)
        if url not in aliases:
            aliases.append(url)

        previous = best_by_canonical.get(canonical)
        if previous is None or _candidate_sort_key(candidate) < _candidate_sort_key(previous):
            best_by_canonical[canonical] = candidate

    soup = BeautifulSoup(text, "html.parser")

    # HTML의 실제 이동/로딩 지점. 이미지 src는 bare URL 후보로만 낮게 처리된다.
    for tag in soup.find_all("a", href=True):
        label = tag.get_text(" ", strip=True)
        if not label:
            label = " ".join(img.get("alt", "") for img in tag.find_all("img")).strip()
        _add(tag["href"], "anchor_href", label)

    for tag_name in ("iframe", "frame"):
        for tag in soup.find_all(tag_name, src=True):
            label = tag.get("title", "") or tag.get("name", "")
            _add(tag["src"], f"{tag_name}_src", label)

    for tag in soup.find_all("img", src=True):
        _add(tag["src"], "image_src", tag.get("alt", ""))

    for tag in soup.find_all("script", src=True):
        _add(tag["src"], "script_src")

    for tag in soup.find_all("link", href=True):
        rel = " ".join(tag.get("rel", [])) if isinstance(tag.get("rel"), list) else (tag.get("rel") or "")
        _add(tag["href"], "link_href", rel)

    for refresh_url in _extract_meta_refresh_urls(text, soup):
        _add(refresh_url, "meta_refresh")

    for match in _JS_LOCATION_URL_RE.finditer(text):
        _add(match.group("assign") or match.group("call") or "", "js_location")

    # 링크드 이미지는 버튼/배지 이미지가 아니라 감싼 href가 배포 정황이다.
    for match in _MD_LINKED_IMG_RE.finditer(text):
        _add(match.group(2), "linked_image_href", match.group(1))

    img_stripped = _MD_LINKED_IMG_RE.sub(" ", text)
    for match in _MD_LINK_RE.finditer(img_stripped):
        _add(match.group(2), "markdown_href", match.group(1))

    md_stripped = _MD_LINK_RE.sub(" ", img_stripped)
    for match in _BARE_URL_RE.finditer(md_stripped):
        _add(match.group(0), "bare_url")

    candidates = [
        replace(
            candidate,
            aliases=tuple(
                alias for alias in aliases_by_canonical.get(candidate.canonical_url, []) if alias != candidate.url
            ),
        )
        for candidate in best_by_canonical.values()
    ]
    return sorted(candidates, key=_candidate_sort_key)


def extract_links(text: str, *, exclude_urls: list[str] | None = None) -> list[str]:
    """URL 후보를 추출한 뒤 추적 가치가 높은 순서로 반환한다."""
    return [candidate.url for candidate in extract_link_candidates(text, exclude_urls=exclude_urls)]


def _candidate_to_dict(candidate: LinkCandidate) -> dict:
    aliases = list(candidate.aliases[:_METADATA_ALIAS_LIMIT])
    return {
        "url": candidate.url,
        "canonical_url": candidate.canonical_url,
        "source_kind": candidate.source_kind,
        "priority": candidate.priority,
        "text": candidate.text,
        "reasons": list(candidate.reasons),
        "aliases": aliases,
        "aliases_truncated_count": max(0, len(candidate.aliases) - len(aliases)),
    }


def _link_stats(candidates: list[LinkCandidate], links: list[str]) -> dict:
    alias_count = sum(len(candidate.aliases) for candidate in candidates)
    return {
        "raw_link_count": len(candidates) + alias_count,
        "raw_unique_link_count": len(candidates) + alias_count,
        "trace_candidate_count": len(candidates),
        "deduped_alias_count": alias_count,
        "selected_link_count": len(links),
        "ranked_link_count": len(links),
        "stored_candidate_count": min(len(candidates), _METADATA_CANDIDATE_LIMIT),
        "stored_candidate_limit": _METADATA_CANDIDATE_LIMIT,
        "stored_alias_limit_per_candidate": _METADATA_ALIAS_LIMIT,
    }


def normalize(text: str, *, exclude_links: list[str] | None = None) -> NormalizedPost:
    """게시글 본문 정규화 + 링크 추출. 빈 입력은 빈 결과(예외 없음)."""
    raw = text or ""
    # 링크는 원문에서 추출 — 정규화(반복 축약 등)가 URL을 훼손하지 않도록.
    candidates = extract_link_candidates(raw, exclude_urls=exclude_links)
    links = [candidate.url for candidate in candidates]

    step = _strip_zero_width(raw)
    step = unicodedata.normalize("NFKC", step)
    step = _map_homoglyphs(step)
    cleaned = _collapse_repeats(step)

    # 변경된 문자 수 — 길이 차 + 동일 길이 내 글리프 치환분의 근사치(디버깅 신호).
    removed = max(0, len(raw) - len(cleaned))

    return NormalizedPost(
        text=cleaned,
        links=links,
        removed_char_count=removed,
        link_candidates=[
            _candidate_to_dict(candidate)
            for candidate in candidates[:_METADATA_CANDIDATE_LIMIT]
        ],
        link_stats=_link_stats(candidates, links),
    )
