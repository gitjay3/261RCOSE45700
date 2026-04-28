"""
각 대상 사이트의 크롤 가능성을 빠르게 검증하는 스크립트.
- 게시판 목록에서 URL 추출 (최대 3개)
- 첫 번째 게시글 1개 크롤 시도
- 결과/실패 원인 보고

사용법:
    cd crawler
    ./.venv/bin/python test_sites.py
"""
from __future__ import annotations

import asyncio
import re
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.async_configs import CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# 테스트할 사이트 목록 (enabled 여부 무관, 직접 정의)
SITES = [
    {
        "id": "tailstar",
        "name": "테일스타",
        "board_url": "https://tailstar.net/board_issue",
        "post_pattern": r"https://tailstar\.net/\d+$",
        "css_selector": None,
        "cookies": None,
        "headers": None,
        "wait_for": None,
        "page_timeout": 30_000,
    },
    {
        "id": "inven_maple",
        "name": "인벤 (메이플스토리)",
        "board_url": "https://www.inven.co.kr/board/maple/2298",
        "post_pattern": r"https://www\.inven\.co\.kr/board/maple/2298/\d+$",
        "css_selector": ".articleMain",
        "cookies": None,
        "headers": None,
        "wait_for": None,
        "page_timeout": 30_000,
    },
    {
        "id": "inven_lineage_classic",
        "name": "인벤 (리니지 클래식)",
        "board_url": "https://www.inven.co.kr/board/lineageclassic/6482",
        "post_pattern": r"https://www\.inven\.co\.kr/board/lineageclassic/6482/\d+$",
        "css_selector": ".articleMain",
        "cookies": None,
        "headers": None,
        "wait_for": None,
        "page_timeout": 30_000,
    },
    {
        "id": "ptt",
        "name": "PTT (C_Chat)",
        "board_url": "https://www.ptt.cc/bbs/C_Chat/index.html",
        "post_pattern": r"https://www\.ptt\.cc/bbs/C_Chat/M\.\d+",
        "css_selector": "#main-content",
        "cookies": [{"name": "over18", "value": "1", "domain": "www.ptt.cc", "path": "/"}],
        "headers": None,
        "wait_for": None,
        "page_timeout": 30_000,
    },
    {
        "id": "dcard",
        "name": "Dcard (게임)",
        "board_url": "https://www.dcard.tw/f/game",
        "post_pattern": r"https://www\.dcard\.tw/f/game/p/\d+",
        "css_selector": None,
        "cookies": None,
        "headers": None,
        "wait_for": "css:.post-content",
        "page_timeout": 45_000,
    },
    {
        "id": "tieba",
        "name": "바이두 티에바",
        "board_url": "https://tieba.baidu.com/f?kw=游戏外挂",
        "post_pattern": r"https://tieba\.baidu\.com/p/\d+",
        "css_selector": None,
        "cookies": None,
        "headers": None,
        "wait_for": None,
        "page_timeout": 30_000,
    },
    {
        "id": "52pojie",
        "name": "52pojie",
        "board_url": "https://www.52pojie.cn/forum-16-1.html",
        "post_pattern": r"https://www\.52pojie\.cn/thread-\d+-\d+-\d+\.html",
        "css_selector": None,
        "cookies": None,
        "headers": None,
        "wait_for": None,
        "page_timeout": 40_000,
    },
    {
        "id": "nga",
        "name": "NGA BBS",
        "board_url": "https://bbs.nga.cn/thread.php?fid=488",
        "post_pattern": r"https://bbs\.nga\.cn/read\.php\?tid=\d+",
        "css_selector": None,
        "cookies": None,
        "headers": None,
        "wait_for": None,
        "page_timeout": 30_000,
    },
]


@dataclass
class SiteTestResult:
    site_id: str
    site_name: str
    board_ok: bool = False
    post_urls_found: int = 0
    post_crawl_ok: bool = False
    text_length: int = 0
    image_count: int = 0
    error: str = ""
    notes: list[str] = field(default_factory=list)


async def get_post_urls(board_url: str, pattern: str, *, cookies=None, wait_for=None, page_timeout=30_000) -> list[str]:
    cfg = BrowserConfig(headless=True, enable_stealth=True, verbose=False)
    run_kwargs = dict(
        cache_mode=CacheMode.BYPASS,
        page_timeout=page_timeout,
    )
    if wait_for:
        run_kwargs["wait_for"] = wait_for

    run = CrawlerRunConfig(**run_kwargs)

    async with AsyncWebCrawler(config=cfg) as crawler:
        if cookies:
            result = await crawler.arun(board_url, config=run, cookies=cookies)
        else:
            result = await crawler.arun(board_url, config=run)

    if not result.success:
        raise RuntimeError(f"목록 크롤 실패: {result.error_message}")

    all_links = (result.links.get("internal") or []) + (result.links.get("external") or [])
    compiled = re.compile(pattern)
    seen: set[str] = set()
    urls: list[str] = []
    for link in all_links:
        href = link.get("href", "").split("?")[0]
        if compiled.match(href) and href not in seen:
            seen.add(href)
            urls.append(href)
        if len(urls) >= 3:
            break
    return urls


async def crawl_post(url: str, *, css_selector=None, cookies=None, wait_for=None, page_timeout=30_000) -> tuple[str, list]:
    cfg = BrowserConfig(headless=True, enable_stealth=True, verbose=False, ignore_https_errors=True)

    run_kwargs = dict(
        cache_mode=CacheMode.BYPASS,
        magic=True,
        page_timeout=page_timeout,
        remove_consent_popups=True,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.5, threshold_type="fixed")
        ),
    )
    if css_selector:
        run_kwargs["css_selector"] = css_selector
    if wait_for:
        run_kwargs["wait_for"] = wait_for

    run = CrawlerRunConfig(**run_kwargs)

    async with AsyncWebCrawler(config=cfg) as crawler:
        if cookies:
            result = await crawler.arun(url, config=run, cookies=cookies)
        else:
            result = await crawler.arun(url, config=run)

    if not result.success:
        raise RuntimeError(f"게시글 크롤 실패: {result.error_message}")

    md = result.markdown
    if hasattr(md, "fit_markdown"):
        text = md.fit_markdown or md.raw_markdown or ""
    else:
        text = str(md) if md else ""

    images = (result.media or {}).get("images") or []
    return text, images


async def test_site(site: dict) -> SiteTestResult:
    r = SiteTestResult(site_id=site["id"], site_name=site["name"])
    sep = "─" * 55

    print(f"\n{sep}")
    print(f"  [{site['name']}]  {site['board_url']}")
    print(sep)

    # 1. 게시판 목록
    try:
        urls = await get_post_urls(
            site["board_url"],
            site["post_pattern"],
            cookies=site["cookies"],
            wait_for=site["wait_for"],
            page_timeout=site["page_timeout"],
        )
        r.board_ok = True
        r.post_urls_found = len(urls)
        print(f"  ✅ 게시판 목록 성공 — 게시글 URL {len(urls)}개 추출")
        for u in urls:
            print(f"     {u}")
    except Exception as exc:
        r.error = f"게시판: {exc}"
        print(f"  ❌ 게시판 목록 실패: {exc}")
        return r

    if not urls:
        r.error = "게시글 URL 0개 (패턴 불일치 가능성)"
        print("  ⚠️  게시글 URL 추출 0개 — post_url_pattern 확인 필요")
        return r

    # 2. 첫 번째 게시글 크롤
    target_url = urls[0]
    print(f"\n  게시글 크롤 시도: {target_url}")
    try:
        text, images = await crawl_post(
            target_url,
            css_selector=site["css_selector"],
            cookies=site["cookies"],
            wait_for=site["wait_for"],
            page_timeout=site["page_timeout"],
        )
        r.post_crawl_ok = True
        r.text_length = len(text)
        r.image_count = len(images)
        preview = text[:120].replace("\n", " ").strip()
        print(f"  ✅ 게시글 크롤 성공")
        print(f"     텍스트 {r.text_length:,}자  |  이미지 {r.image_count}개")
        print(f"     미리보기: {preview!r}")
    except Exception as exc:
        r.error = f"게시글: {exc}"
        print(f"  ❌ 게시글 크롤 실패: {exc}")

    return r


async def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    sites = [s for s in SITES if target is None or s["id"] == target]

    if not sites:
        print(f"[오류] '{target}' 사이트를 찾을 수 없습니다.")
        print(f"사용 가능: {[s['id'] for s in SITES]}")
        return

    print(f"\n{'━'*55}")
    print(f"  사이트 크롤 가능성 테스트  ({datetime.now().strftime('%H:%M:%S')})")
    print(f"  대상: {[s['id'] for s in sites]}")
    print(f"{'━'*55}")

    results: list[SiteTestResult] = []
    for site in sites:
        r = await test_site(site)
        results.append(r)

    # 최종 요약
    print(f"\n\n{'━'*55}")
    print("  최종 결과 요약")
    print(f"{'━'*55}")
    print(f"  {'사이트':<20} {'목록':^6} {'게시글':^6} {'텍스트':>8} {'이미지':>6}  비고")
    print(f"  {'─'*20} {'─'*6} {'─'*6} {'─'*8} {'─'*6}  {'─'*20}")
    for r in results:
        board = "✅" if r.board_ok else "❌"
        post  = "✅" if r.post_crawl_ok else ("⚠️" if r.board_ok else "─")
        note  = r.error[:40] if r.error else "OK"
        print(f"  {r.site_name:<20} {board:^6} {post:^6} {r.text_length:>8,} {r.image_count:>6}  {note}")
    print(f"{'━'*55}\n")


if __name__ == "__main__":
    asyncio.run(main())
