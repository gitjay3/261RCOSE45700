from __future__ import annotations

import hashlib
import os
from typing import Final
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from crawler.src.sites.base_site import (
    BaseSite,
    ParseError,
    ParseResult,
    PostListItem,
    RateLimitError,
)
from shared.structured_logger import get_logger

_logger = get_logger(__name__)
_SERVICE_NAME: Final[str] = os.environ.get("SERVICE_NAME", "crawler")


class TailstarSite(BaseSite):
    """tailstar.net XpressEngine 게시판 어댑터.

    Story 2.1 spike 관찰: <title>테일스타 - 재밌는 인터넷 놀이터</title>,
    meta[name=Generator][content*=XpressEngine]. 본 어댑터는 XE 표준 셀렉터와
    Open Graph 메타를 우선 사용하여 사이트 마이너 변경에 견고함.
    """

    BASE_URL: Final[str] = "https://tailstar.net"
    LIST_PATH: Final[str] = "/index.php?mid=board_main"

    _RATE_LIMIT_MARKERS: Final[tuple[str, ...]] = (
        "잠시 후 다시 시도",
        "잠시후 다시 시도",
        "too many requests",
        "rate limit exceeded",
        "차단되었습니다",
        "접근이 차단",
    )

    def parse_list(self, html: str) -> list[PostListItem]:
        if not html or not html.strip():
            raise ParseError("parse_list: empty HTML received")

        self._check_rate_limit(html, context="parse_list")
        soup = BeautifulSoup(html, "html.parser")

        items: list[PostListItem] = []
        seen_ids: set[str] = set()
        # XE 게시판 목록 패턴: 제목 링크는 ?document_srl=N 쿼리 또는
        # /article/N 경로 형태. 두 형태 모두 대응.
        for link in soup.select("a[href]"):
            href = link.get("href") or ""
            if not href:
                continue
            absolute = urljoin(self.BASE_URL, href)
            post_id = self._extract_post_id(absolute)
            if post_id is None or post_id in seen_ids:
                continue
            title = link.get_text(strip=True)
            if not title:
                continue
            seen_ids.add(post_id)
            items.append(PostListItem(post_id=post_id, url=absolute, title=title))

        if not items:
            raise ParseError(
                f"parse_list: no post entries found (html_prefix={html[:120]!r})"
            )
        return items

    def parse(self, html: str) -> ParseResult:
        if not html or not html.strip():
            raise ParseError("parse: empty HTML received")

        self._check_rate_limit(html, context="parse")
        soup = BeautifulSoup(html, "html.parser")

        source_url = self._extract_source_url(soup)
        post_id = self._extract_post_id(source_url) if source_url else None

        title = self._extract_title(soup)
        if not title:
            raise ParseError(
                f"parse: title not found (html_prefix={html[:120]!r})"
            )

        body_text = self._extract_body_text(soup)
        if not body_text:
            raise ParseError(
                f"parse: body not found (post_id={post_id} title={title!r})"
            )

        if post_id is None:
            # source_url 누락 시 title 기반 결정적 식별자 — hashlib으로 PYTHONHASHSEED 영향 차단.
            # Story 2.3 dedup 단계에서 본문 SHA-256 해시로 재판별하므로 임시값으로 충분.
            post_id = f"tailstar:{hashlib.md5(title.encode()).hexdigest()[:8]}"

        image_base = source_url if (source_url and source_url.startswith("http")) else self.BASE_URL
        image_urls = self._extract_image_urls(soup, base=image_base)
        posted_at = self._extract_posted_at(soup)

        return ParseResult(
            post_id=post_id,
            title=title,
            body_text=body_text,
            source_url=source_url or "",
            image_urls=image_urls,
            posted_at=posted_at,
        )

    def _check_rate_limit(self, html: str, *, context: str) -> None:
        html_lower = html.lower()
        for marker in self._RATE_LIMIT_MARKERS:
            if marker in html or marker.lower() in html_lower:
                _logger.warning(
                    f"tailstar.{context}.rate_limit marker={marker!r}",
                    extra={"service": _SERVICE_NAME, "correlation_id": None},
                )
                raise RateLimitError(
                    f"tailstar.{context}: rate-limit marker detected ({marker!r})"
                )

    @staticmethod
    def _extract_post_id(url: str | None) -> str | None:
        if not url:
            return None
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "document_srl" in qs and qs["document_srl"]:
            return qs["document_srl"][0]
        # path 기반: /article/123 형태의 순수 숫자 마지막 segment만 인정.
        # 알파벳 segment(/about 등)는 네비게이션으로 간주하고 None 반환.
        segments = [s for s in parsed.path.split("/") if s]
        if segments and segments[-1].isdigit():
            return segments[-1]
        return None

    @staticmethod
    def _extract_source_url(soup: BeautifulSoup) -> str | None:
        og_url = soup.find("meta", property="og:url")
        if og_url and og_url.get("content"):
            return og_url["content"]
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            return canonical["href"]
        return None

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str | None:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)
        title_tag = soup.find("title")
        if title_tag and title_tag.get_text(strip=True):
            return title_tag.get_text(strip=True)
        return None

    @staticmethod
    def _extract_body_text(soup: BeautifulSoup) -> str:
        for selector in (
            "div.document_xe_content",
            "div.xe_content",
            "article",
            "main",
            "div#content",
        ):
            node = soup.select_one(selector)
            if node:
                text = node.get_text(separator="\n", strip=True)
                if text:
                    return text
        body = soup.find("body")
        if body:
            return body.get_text(separator="\n", strip=True)
        return ""

    @staticmethod
    def _extract_image_urls(soup: BeautifulSoup, *, base: str) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            absolute = urljoin(base, og_image["content"])
            urls.append(absolute)
            seen.add(absolute)
        for img in soup.find_all("img"):
            src = img.get("src") or ""
            if not src:
                continue
            absolute = urljoin(base, src)
            if absolute in seen:
                continue
            seen.add(absolute)
            urls.append(absolute)
        return urls

    @staticmethod
    def _extract_posted_at(soup: BeautifulSoup) -> str | None:
        meta_time = soup.find("meta", property="article:published_time")
        if meta_time and meta_time.get("content"):
            return meta_time["content"].strip()
        time_tag = soup.find("time")
        if time_tag:
            return time_tag.get("datetime") or time_tag.get_text(strip=True) or None
        return None
