"""
crawl4ai 기반 크롤러 — 다중 사이트 자동 순회 + 포스트별 저장.

저장 구조:
    output/posts/{site_id}/{post_id}/
        post.json   ← 텍스트 + 이미지 메타데이터
        img_000.jpg ← 사용자 업로드 이미지

사용법:
    cd crawler2
    source .venv/bin/activate
    python demo.py              # 활성화된 모든 사이트
    python demo.py tailstar     # 특정 사이트만
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.async_configs import CacheMode

from src.crawler import Crawl4AICrawler
from src.sites.registry import SiteConfig, get_enabled_sites

MAX_POSTS_PER_BOARD = 6     # 게시판당 최대 게시글 수 (2개 게시판 × 2개 사이트 → 총 24개 시도)
OUTPUT_BASE = Path("output/posts")


async def get_post_urls(board_url: str, pattern: str, limit: int) -> list[str]:
    """게시판 목록에서 게시글 URL 추출."""
    cfg = BrowserConfig(headless=True, enable_stealth=True)
    run = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, page_timeout=20_000)

    async with AsyncWebCrawler(config=cfg) as crawler:
        result = await crawler.arun(board_url, config=run)

    if not result.success:
        print(f"  [목록 실패] {board_url}: {result.error_message}")
        return []

    all_links = (result.links.get("internal") or []) + (result.links.get("external") or [])
    seen: set[str] = set()
    post_urls: list[str] = []
    compiled = re.compile(pattern)

    for link in all_links:
        href = link.get("href", "").split("?")[0]
        if compiled.match(href) and href not in seen:
            seen.add(href)
            post_urls.append(href)
        if len(post_urls) >= limit:
            break

    return post_urls


def save_post(
    *,
    site_id: str,
    post_id: str,
    url: str,
    text: str,
    image_metas: list[dict],
    downloaded: list[Path],
) -> Path:
    """포스트 디렉터리에 post.json 저장. 이미지는 이미 해당 디렉터리에 저장됨."""
    post_dir = OUTPUT_BASE / site_id / post_id
    image_records = [
        {
            "filename": path.name,
            "src": meta.get("src", ""),
            "alt": meta.get("alt", ""),
            "score": meta.get("score", 0),
        }
        for meta, path in zip(image_metas, downloaded)
    ]
    data = {
        "post_id": post_id,
        "site": site_id,
        "url": url,
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "images": image_records,
    }
    (post_dir / "post.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return post_dir


async def crawl_site(
    crawler: Crawl4AICrawler,
    site_id: str,
    site: SiteConfig,
) -> list[Path]:
    """사이트 전체 크롤링. 저장된 포스트 디렉터리 목록 반환."""
    print(f"\n{'━'*60}")
    print(f"  [{site.name}]  {site.description}")
    print(f"{'━'*60}")

    saved_dirs: list[Path] = []
    crawled_ids: set[str] = set()   # 사이트 내 중복 크롤링 방지

    for board_url in site.board_urls:
        print(f"\n  게시판: {board_url}")
        post_urls = await get_post_urls(board_url, site.post_url_pattern, MAX_POSTS_PER_BOARD)
        if not post_urls:
            print("  → 게시글을 찾지 못했습니다.")
            continue

        # 이미 크롤링한 포스트 제외
        post_urls = [u for u in post_urls if site.post_id_extractor(u) not in crawled_ids]
        if not post_urls:
            print("  → 모두 이미 크롤링된 포스트입니다.")
            continue

        print(f"  → {len(post_urls)}개 게시글 크롤링\n")

        for i, post_url in enumerate(post_urls, 1):
            post_id = site.post_id_extractor(post_url)
            post_dir = OUTPUT_BASE / site_id / post_id
            post_dir.mkdir(parents=True, exist_ok=True)

            print(f"  [{i:>2}/{len(post_urls)}] post_id={post_id}  {post_url}")

            try:
                result = await crawler.fetch(
                    post_url,
                    download_images=True,
                    output_dir=post_dir,        # 이미지를 포스트 폴더에 직접 저장
                    css_selector=site.css_selector,
                    image_filter=site.image_filter,
                )
            except RuntimeError as exc:
                print(f"         오류: {exc}\n")
                continue

            saved = save_post(
                site_id=site_id,
                post_id=post_id,
                url=post_url,
                text=result.markdown,
                image_metas=result.images,
                downloaded=result.downloaded_images,
            )
            crawled_ids.add(post_id)
            saved_dirs.append(saved)

            text_len = len(result.markdown)
            img_count = len(result.downloaded_images)
            img_sizes = [f"{p.stat().st_size//1024}KB" for p in result.downloaded_images]

            print(f"         텍스트 {text_len:,}자  |  이미지 {img_count}개 {img_sizes}")
            print(f"         저장 → {saved}\n")

    return saved_dirs


async def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    enabled = get_enabled_sites()

    if target:
        if target not in enabled:
            print(f"[오류] '{target}' — 없거나 비활성화 상태.")
            print(f"활성화 사이트: {list(enabled.keys())}")
            return
        sites = {target: enabled[target]}
    else:
        sites = enabled

    print(f"\n크롤링 대상: {list(sites.keys())}  (사이트당 최대 {MAX_POSTS_PER_BOARD}개/게시판)")

    crawler = Crawl4AICrawler(headless=True, output_dir="output/_tmp")
    all_saved: list[Path] = []

    for site_id, site in sites.items():
        dirs = await crawl_site(crawler, site_id, site)
        all_saved.extend(dirs)

    # 최종 요약
    print(f"\n{'━'*60}")
    print(f"  완료: 총 {len(all_saved)}개 포스트 저장됨")
    print(f"{'━'*60}")
    for d in all_saved:
        meta_file = d / "post.json"
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            imgs = meta.get("images", [])
            text_preview = meta.get("text", "")[:60].replace("\n", " ")
            print(f"  {d.relative_to(OUTPUT_BASE)}  |  이미지 {len(imgs)}개  |  {text_preview!r}")


if __name__ == "__main__":
    asyncio.run(main())
