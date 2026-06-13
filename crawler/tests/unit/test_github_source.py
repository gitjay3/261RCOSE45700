from __future__ import annotations

import base64

import httpx
import pytest

from crawler.src.preprocessor.dedup_checker import DedupChecker
from crawler.src.queue.redis_publisher import RedisPublisher
from crawler.src.sources.github_source import GitHubSource
from shared.models.crawl_event import CrawlEvent


class _SetBackedRedis:
    def __init__(self) -> None:
        self.values: set[str] = set()

    def sismember(self, _key: str, value: str) -> int:
        return 1 if value in self.values else 0

    def sadd(self, _key: str, value: str) -> int:
        before = len(self.values)
        self.values.add(value)
        return len(self.values) - before


class _ListBackedRedis:
    def __init__(self) -> None:
        self.items: list[tuple[str, str]] = []

    def lpush(self, key: str, value: str) -> int:
        self.items.insert(0, (key, value))
        return len(self.items)


@pytest.fixture(autouse=True)
def _github_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_SOURCE_ENABLED", "true")
    monkeypatch.setenv("GITHUB_SEARCH_QUERIES", "lineage macro")
    monkeypatch.setenv("GITHUB_SEARCH_PER_QUERY", "1")
    monkeypatch.setenv("GITHUB_MAX_REPOS", "1")
    monkeypatch.setenv("GITHUB_REQUEST_DELAY_SECONDS", "0")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)


async def test_github_source_enqueues_crawl_event(monkeypatch: pytest.MonkeyPatch) -> None:
    original_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/search/repositories":
            return httpx.Response(200, json={
                "items": [{
                    "full_name": "evil/lineage-macro",
                    "html_url": "https://github.com/evil/lineage-macro",
                    "description": "Lineage macro helper",
                    "topics": ["lineage", "macro"],
                    "stargazers_count": 7,
                    "forks_count": 2,
                    "updated_at": "2026-06-13T00:00:00Z",
                    "pushed_at": "2026-06-13T00:00:00Z",
                    "language": "Python",
                }]
            })
        if path == "/repos/evil/lineage-macro/readme":
            encoded = base64.b64encode(b"# Lineage Macro\nAuto hunt bot download").decode("ascii")
            return httpx.Response(200, json={"encoding": "base64", "content": encoded})
        if path == "/repos/evil/lineage-macro/releases/latest":
            return httpx.Response(200, json={
                "name": "v1",
                "tag_name": "v1",
                "html_url": "https://github.com/evil/lineage-macro/releases/tag/v1",
                "body": "Download macro binary",
                "assets": [{"name": "lineage-macro.zip"}],
            })
        return httpx.Response(404, json={})

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs),
    )

    mq = _ListBackedRedis()
    source = GitHubSource(
        publisher=RedisPublisher(mq),
        dedup=DedupChecker(_SetBackedRedis()),
    )

    stats = await source.run()

    assert stats.searches == 1
    assert stats.enqueued == 1
    assert len(mq.items) == 1
    key, payload = mq.items[0]
    assert key == "posts:queue"
    event = CrawlEvent.from_json(payload)
    assert event.source_id == "github"
    assert event.site_name == "GitHub"
    assert event.post_id == "evil__lineage-macro"
    assert event.post_url == "https://github.com/evil/lineage-macro"
    assert "Latest Release" in event.raw_text
    assert "lineage-macro.zip" in event.raw_text


async def test_github_source_stops_on_primary_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    original_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1781319187"},
            json={"message": "API rate limit exceeded"},
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs),
    )

    mq = _ListBackedRedis()
    source = GitHubSource(
        publisher=RedisPublisher(mq),
        dedup=DedupChecker(_SetBackedRedis()),
    )

    stats = await source.run()

    assert stats.searches == 1
    assert stats.enqueued == 0
    assert mq.items == []
