from __future__ import annotations

import asyncio
import base64
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from crawler.src.preprocessor import language_detector
from crawler.src.preprocessor.dedup_checker import DedupChecker
from crawler.src.preprocessor.url_dedup_checker import UrlDedupChecker
from crawler.src.queue.redis_publisher import RedisPublisher
from shared.correlation_id import generate
from shared.models.crawl_event import CrawlEvent
from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "crawler")
_logger = get_logger(__name__)

_API_BASE = "https://api.github.com"
_SEARCH_SCOPE = "in:name,description,readme"
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MAX_README_CHARS = 12_000
_MAX_RELEASE_CHARS = 4_000


@dataclass(frozen=True)
class GitHubSearchQuery:
    terms: tuple[str, ...]
    exact_phrase: bool = False

    def render(self, *, pushed_since: str = "") -> str:
        parts = [_quote_query_term(" ".join(self.terms))] if self.exact_phrase else [
            _quote_query_term(term) for term in self.terms
        ]
        parts.extend([_SEARCH_SCOPE, "archived:false"])
        if pushed_since:
            parts.append(f"pushed:>={pushed_since}")
        return " ".join(parts)


def _exact(phrase: str) -> GitHubSearchQuery:
    return GitHubSearchQuery((phrase,), exact_phrase=True)


def _and(*terms: str) -> GitHubSearchQuery:
    return GitHubSearchQuery(tuple(terms))


_DEFAULT_QUERIES = (
    _exact("lineage macro"),
    _exact("lineage bot"),
    _exact("lineage private server"),
    _and("lineage", "trainer"),
    _and("lineage", "cheat engine"),
    _and("lineage", "loader"),
    _and("lineage", "injector"),
    _exact("aion macro"),
    _and("aion", "bot"),
    _and("aion", "trainer"),
    _and("aion", "loader"),
    _exact("blade and soul cheat"),
    _and("blade and soul", "macro"),
    _and("blade and soul", "trainer"),
    _exact("throne liberty bot"),
    _and("throne liberty", "macro"),
    _and("throne liberty", "trainer"),
    _exact("ncsoft private server"),
    _and("ncsoft", "loader"),
    _and("ncsoft", "bypass"),
    _exact("天堂 外掛"),
    _and("天堂外掛"),
    _and("天堂", "腳本"),
    _and("天堂腳本"),
    _and("天堂", "掛機"),
    _and("天堂掛機"),
    _and("天堂", "修改器"),
    _and("天堂修改器"),
    _exact("天堂M 輔助"),
    _and("天堂M外掛"),
    _and("天堂M", "腳本"),
    _and("天堂M腳本"),
    _and("天堂M", "掛機"),
    _and("天堂M掛機"),
    _and("天堂M", "修改器"),
    _exact("劍靈 外掛"),
    _and("劍靈", "腳本"),
    _and("劍靈腳本"),
    _and("劍靈", "修改器"),
)


@dataclass(frozen=True)
class GitHubRepoDocument:
    full_name: str
    html_url: str
    description: str = ""
    topics: list[str] = field(default_factory=list)
    stars: int = 0
    forks: int = 0
    updated_at: str = ""
    pushed_at: str = ""
    language: str | None = None
    readme: str = ""
    latest_release_name: str = ""
    latest_release_body: str = ""
    latest_release_url: str = ""
    latest_release_assets: list[str] = field(default_factory=list)

    @property
    def post_id(self) -> str:
        return self.full_name.replace("/", "__")

    def to_markdown(self) -> str:
        parts = [
            f"# GitHub Repository: {self.full_name}",
            f"URL: {self.html_url}",
            f"Description: {self.description or '(none)'}",
            f"Topics: {', '.join(self.topics) if self.topics else '(none)'}",
            f"Primary language: {self.language or '(unknown)'}",
            f"Stars/Forks: {self.stars}/{self.forks}",
            f"Updated at: {self.updated_at}",
            f"Pushed at: {self.pushed_at}",
        ]
        if self.readme:
            parts.extend(["", "## README", self.readme[:_MAX_README_CHARS]])
        if self.latest_release_name or self.latest_release_body or self.latest_release_assets:
            parts.extend([
                "",
                "## Latest Release",
                f"Name: {self.latest_release_name or '(none)'}",
                f"URL: {self.latest_release_url or '(none)'}",
                "Assets:",
                "\n".join(f"- {asset}" for asset in self.latest_release_assets) or "- (none)",
                "",
                self.latest_release_body[:_MAX_RELEASE_CHARS],
            ])
        return "\n".join(parts).strip()


@dataclass
class GitHubSourceStats:
    searches: int = 0
    discovered: int = 0
    selected: int = 0
    enqueued: int = 0
    skipped_seen_url: int = 0
    skipped_dedup: int = 0
    failed: int = 0


class GitHubSource:
    """GitHub REST API source for public cheat/macro repository candidates."""

    def __init__(
        self,
        *,
        publisher: RedisPublisher,
        dedup: DedupChecker,
        url_dedup: UrlDedupChecker | None = None,
        token: str | None = None,
    ) -> None:
        self._publisher = publisher
        self._dedup = dedup
        self._url_dedup = url_dedup
        self._token = token if token is not None else os.environ.get("GITHUB_TOKEN", "")
        self._enabled = _env_bool("GITHUB_SOURCE_ENABLED", "true")
        self._per_query = max(1, int(os.environ.get("GITHUB_SEARCH_PER_QUERY", "3")))
        self._max_repos = max(1, int(os.environ.get("GITHUB_MAX_REPOS", "12")))
        self._request_delay = max(
            0.0,
            float(os.environ.get("GITHUB_REQUEST_DELAY_SECONDS", "1.0")),
        )
        self._pushed_since = _load_pushed_since()
        self._queries = _load_queries()

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def run(self) -> GitHubSourceStats:
        stats = GitHubSourceStats()
        if not self._enabled:
            return stats

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "tracker-crawler",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        async with httpx.AsyncClient(
            base_url=_API_BASE,
            headers=headers,
            follow_redirects=True,
            timeout=20,
        ) as client:
            repos = await self._search_repositories(client, stats)
            for repo in repos[: self._max_repos]:
                cid = generate()
                html_url = str(repo.get("html_url") or "")
                if not html_url:
                    continue
                if self._url_dedup is not None and self._url_dedup.has_seen(
                    html_url,
                    correlation_id=cid,
                ):
                    stats.skipped_seen_url += 1
                    continue
                try:
                    doc = await self._build_document(client, repo)
                    text = doc.to_markdown()
                    if self._dedup.is_duplicate(text, correlation_id=cid):
                        stats.skipped_dedup += 1
                        continue
                    language = language_detector.detect(text, correlation_id=cid)
                    event = CrawlEvent(
                        post_id=doc.post_id,
                        source_id="github",
                        site_name="GitHub",
                        raw_text=text,
                        image_urls=[],
                        language=language,
                        detected_at=datetime.now(UTC).isoformat(),
                        correlation_id=cid,
                        post_url=doc.html_url,
                    )
                    self._publisher.enqueue(event.to_json(), correlation_id=cid)
                    self._dedup.mark_seen(text, correlation_id=cid)
                    if self._url_dedup is not None:
                        self._url_dedup.mark_seen(html_url, correlation_id=cid)
                    stats.enqueued += 1
                except Exception as exc:
                    stats.failed += 1
                    _logger.warning(
                        "GitHub source repo 처리 실패: %s — %s",
                        html_url,
                        exc,
                        extra={"correlation_id": cid, "service": _SERVICE_NAME},
                        exc_info=True,
                    )
        _logger.info(
            "GitHub source 완료: searches=%d discovered=%d selected=%d queued=%d"
            " url중복=%d 본문중복=%d 실패=%d",
            stats.searches,
            stats.discovered,
            stats.selected,
            stats.enqueued,
            stats.skipped_seen_url,
            stats.skipped_dedup,
            stats.failed,
            extra={"correlation_id": "", "service": _SERVICE_NAME},
        )
        return stats

    async def _search_repositories(
        self,
        client: httpx.AsyncClient,
        stats: GitHubSourceStats,
    ) -> list[dict[str, Any]]:
        repos: list[dict[str, Any]] = []
        seen: set[str] = set()
        for query in self._queries:
            if len(repos) >= self._max_repos:
                break
            stats.searches += 1
            try:
                rendered_query = query.render(pushed_since=self._pushed_since)
                resp = await client.get(
                    "/search/repositories",
                    params={
                        "q": rendered_query,
                        "sort": "updated",
                        "order": "desc",
                        "per_page": self._per_query,
                    },
                )
                if _is_rate_limited(resp):
                    _log_rate_limit(resp, "GitHub repository search")
                    break
                resp.raise_for_status()
                payload = resp.json()
                items = payload.get("items") or []
                _logger.info(
                    "GitHub search query 완료: query=%s total=%s incomplete=%s items=%d"
                    " remaining=%s reset=%s",
                    rendered_query,
                    payload.get("total_count", ""),
                    payload.get("incomplete_results", ""),
                    len(items),
                    resp.headers.get("x-ratelimit-remaining", ""),
                    resp.headers.get("x-ratelimit-reset", ""),
                    extra={"correlation_id": "", "service": _SERVICE_NAME},
                )
            except Exception as exc:
                stats.failed += 1
                _logger.warning(
                    "GitHub search 실패: query=%s — %s",
                    query.render(pushed_since=self._pushed_since),
                    exc,
                    extra={"correlation_id": "", "service": _SERVICE_NAME},
                )
                continue
            stats.discovered += len(items)
            for repo in items:
                full_name = str(repo.get("full_name") or "")
                if not full_name or full_name in seen:
                    continue
                seen.add(full_name)
                repos.append(repo)
                if len(repos) >= self._max_repos:
                    break
            if self._request_delay:
                await _sleep(self._request_delay)
        stats.selected = len(repos)
        return repos

    async def _build_document(
        self,
        client: httpx.AsyncClient,
        repo: dict[str, Any],
    ) -> GitHubRepoDocument:
        full_name = str(repo.get("full_name") or "")
        owner, repo_name = full_name.split("/", 1)
        readme = await self._fetch_readme(client, owner, repo_name)
        release = await self._fetch_latest_release(client, owner, repo_name)
        return GitHubRepoDocument(
            full_name=full_name,
            html_url=str(repo.get("html_url") or ""),
            description=str(repo.get("description") or ""),
            topics=[str(t) for t in (repo.get("topics") or [])],
            stars=int(repo.get("stargazers_count") or 0),
            forks=int(repo.get("forks_count") or 0),
            updated_at=str(repo.get("updated_at") or ""),
            pushed_at=str(repo.get("pushed_at") or ""),
            language=repo.get("language"),
            readme=readme,
            latest_release_name=str(release.get("name") or release.get("tag_name") or ""),
            latest_release_body=str(release.get("body") or ""),
            latest_release_url=str(release.get("html_url") or ""),
            latest_release_assets=[
                str(asset.get("name") or asset.get("browser_download_url") or "")
                for asset in (release.get("assets") or [])
                if asset.get("name") or asset.get("browser_download_url")
            ][:20],
        )

    async def _fetch_readme(self, client: httpx.AsyncClient, owner: str, repo: str) -> str:
        if self._request_delay:
            await _sleep(self._request_delay)
        resp = await client.get(f"/repos/{owner}/{repo}/readme")
        if resp.status_code == 404:
            return ""
        if _is_rate_limited(resp):
            _log_rate_limit(resp, "GitHub README")
            return ""
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content") or ""
        if data.get("encoding") != "base64" or not content:
            return ""
        decoded = base64.b64decode(content).decode("utf-8", errors="replace")
        return decoded[:_MAX_README_CHARS]

    async def _fetch_latest_release(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
    ) -> dict[str, Any]:
        if self._request_delay:
            await _sleep(self._request_delay)
        resp = await client.get(f"/repos/{owner}/{repo}/releases/latest")
        if resp.status_code == 404:
            return {}
        if _is_rate_limited(resp):
            _log_rate_limit(resp, "GitHub release")
            return {}
        resp.raise_for_status()
        return resp.json()


def _load_queries() -> list[GitHubSearchQuery]:
    raw = os.environ.get("GITHUB_SEARCH_QUERIES", "")
    if not raw:
        return list(_DEFAULT_QUERIES)
    return [_exact(item.strip()) for item in raw.split(",") if item.strip()]


def _load_pushed_since() -> str:
    pushed_since = os.environ.get("GITHUB_SEARCH_PUSHED_SINCE", "").strip()
    if not pushed_since:
        return ""
    if _DATE_PATTERN.match(pushed_since):
        return pushed_since
    _logger.warning(
        "GITHUB_SEARCH_PUSHED_SINCE 값이 YYYY-MM-DD 형식이 아니어서 무시합니다: %s",
        pushed_since,
        extra={"correlation_id": "", "service": _SERVICE_NAME},
    )
    return ""


def _quote_query_term(term: str) -> str:
    cleaned = " ".join(term.strip().split())
    if not cleaned:
        return ""
    escaped = cleaned.replace('"', r'\"')
    return f'"{escaped}"' if any(ch.isspace() for ch in cleaned) else escaped


def _env_bool(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _is_rate_limited(resp: httpx.Response) -> bool:
    return resp.status_code in (403, 429) and resp.headers.get("x-ratelimit-remaining") == "0"


def _log_rate_limit(resp: httpx.Response, context: str) -> None:
    _logger.warning(
        "%s rate limited: remaining=%s reset=%s status=%d",
        context,
        resp.headers.get("x-ratelimit-remaining", ""),
        resp.headers.get("x-ratelimit-reset", ""),
        resp.status_code,
        extra={"correlation_id": "", "service": _SERVICE_NAME},
    )


async def _sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)
