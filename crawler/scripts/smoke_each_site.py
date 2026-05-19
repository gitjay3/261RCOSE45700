"""사이트별 실제 크롤 가능성 smoke 테스트.

실제 SITES 레지스트리 + 새 SiteConfig 필드(cookies/wait_for/proxy 등)를 사용해
각 사이트마다 다음을 시도한다:
  1) _fetch_post_urls(board, pattern, limit=3, **site_opts)
  2) 성공 시 첫 게시글에 대해 Crawl4AICrawler.fetch(...)
  3) 결과/오류 보고

사용:
    cd crawler_test
    uv run python scripts/smoke_each_site.py
    uv run python scripts/smoke_each_site.py inven_maple   # 특정 사이트만
"""
from __future__ import annotations

import asyncio
import os
import random
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

# 프로젝트 루트(crawler_test/)를 sys.path 에 추가 — `crawler.*` / `shared.*` import 풀기.
# 아래 import 들이 이 sys.path 조작에 의존하므로 모듈 최상단 import 규칙(E402) 의도적 위반.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import re  # noqa: E402

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig  # noqa: E402
from crawl4ai.async_configs import CacheMode  # noqa: E402

from crawler.src.crawl4ai_crawler import Crawl4AICrawler  # noqa: E402
from crawler.src.preprocessor.content_validator import PostValidation, validate  # noqa: E402
from crawler.src.sites.registry import SITES, SiteConfig  # noqa: E402


async def _diagnose_board(site: SiteConfig) -> dict:
    """게시판 페이지를 직접 fetch 해서 (1) 성공 여부 (2) 페이지에 잡힌 링크 수
    (3) 패턴 매칭 링크 (4) error_message 까지 모두 회수."""
    browser_kwargs = dict(headless=True, enable_stealth=True, verbose=False)
    if site.proxy is not None:
        browser_kwargs["proxy_config"] = site.proxy
    if site.headers is not None:
        browser_kwargs["headers"] = site.headers
    if site.user_agent_mode is not None:
        browser_kwargs["user_agent_mode"] = site.user_agent_mode
    cfg = BrowserConfig(**browser_kwargs)

    run_kwargs: dict = dict(
        cache_mode=CacheMode.BYPASS,
        page_timeout=site.page_timeout or 30_000,
    )
    if site.wait_for:
        run_kwargs["wait_for"] = site.wait_for
    if site.js_code:
        run_kwargs["js_code"] = site.js_code
    if site.delay_before_return_html is not None:
        run_kwargs["delay_before_return_html"] = site.delay_before_return_html
    if site.scan_full_page:
        run_kwargs["scan_full_page"] = True
        if site.scroll_delay is not None:
            run_kwargs["scroll_delay"] = site.scroll_delay
    if site.virtual_scroll_config is not None:
        run_kwargs["virtual_scroll_config"] = site.virtual_scroll_config
    if site.wait_until is not None:
        run_kwargs["wait_until"] = site.wait_until
    if site.simulate_user:
        run_kwargs["simulate_user"] = True
    if site.c4a_script is not None:
        run_kwargs["c4a_script"] = site.c4a_script
    if site.exclude_social_media_links:
        run_kwargs["exclude_social_media_links"] = True
    if site.exclude_external_links is not None:
        run_kwargs["exclude_external_links"] = site.exclude_external_links
    run = CrawlerRunConfig(**run_kwargs)

    arun_kwargs: dict = {"url": site.board_urls[0], "config": run}
    if site.cookies:
        arun_kwargs["cookies"] = site.cookies

    out = {"ok": False, "error": "", "total_links": 0, "matched": [], "samples": [], "html_len": 0}
    try:
        async with AsyncWebCrawler(config=cfg) as cr:
            res = await cr.arun(**arun_kwargs)
    except Exception as exc:
        out["error"] = f"exception: {exc}"
        return out

    if not res.success:
        out["error"] = f"crawl failed: {res.error_message}"
        return out

    out["ok"] = True
    out["html_len"] = len(res.html or "")
    internal = (res.links.get("internal") or []) if res.links else []
    external = (res.links.get("external") or []) if res.links else []
    all_links = internal + external
    out["total_links"] = len(all_links)
    pat = re.compile(site.post_url_pattern)
    keywords_lower = [k.lower() for k in (site.title_keywords or [])]
    matched: list[str] = []
    filtered_by_title = 0
    for link in all_links:
        full = (link.get("href") or "")
        href = full.split("?")[0]
        title = (link.get("text") or link.get("title") or "")
        candidate = full if pat.match(full) else (href if pat.match(href) else None)
        if not candidate:
            continue
        if keywords_lower and not any(k in title.lower() for k in keywords_lower):
            filtered_by_title += 1
            continue
        matched.append(candidate)
    out["matched"] = matched[:5]
    out["title_filtered"] = filtered_by_title
    out["samples"] = [(link.get("href") or "")[:90] for link in all_links[:6]]
    return out


@dataclass
class PostProbe:
    url: str
    text_len: int = 0
    image_count: int = 0
    error: str = ""
    validation: PostValidation | None = None


@dataclass
class SiteResult:
    site_id: str
    name: str
    board_ok: bool = False
    post_urls_found: int = 0
    probes: list[PostProbe] = field(default_factory=list)
    elapsed_s: float = 0.0
    error: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def post_attempts(self) -> int:
        return len(self.probes)

    @property
    def real_count(self) -> int:
        return sum(1 for p in self.probes if p.validation and p.validation.is_real_user_post)

    def kind_breakdown(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in self.probes:
            k = "fetch_error" if p.error else (p.validation.kind if p.validation else "no_validation")
            out[k] = out.get(k, 0) + 1
        return out


async def _crawl_one(crawler: Crawl4AICrawler, site_id: str, site: SiteConfig, url: str) -> PostProbe:
    """1회 재시도 포함 — 일시적 anti-bot/timeout 회복용."""
    probe = PostProbe(url=url)
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            result = await crawler.fetch(
                url,
                correlation_id=f"smoke-{site_id}-post",
                download_images=False,
                css_selector=site.css_selector,
                image_filter=site.image_filter,
                cookies=site.cookies,
                wait_for=site.wait_for,
                headers=site.headers,
                page_timeout=site.page_timeout,
                proxy=site.proxy,
                js_code=site.js_code,
                delay_before_return_html=site.delay_before_return_html,
                scan_full_page=site.scan_full_page,
                scroll_delay=site.scroll_delay,
                virtual_scroll_config=site.virtual_scroll_config,
                wait_until=site.wait_until,
                simulate_user=site.simulate_user,
                user_agent_mode=site.user_agent_mode,
                c4a_script=site.c4a_script,
                exclude_social_media_links=site.exclude_social_media_links,
                exclude_external_links=site.exclude_external_links,
            )
            probe.text_len = len(result.markdown)
            probe.image_count = len(result.images)
            probe.validation = validate(site_id, result.markdown, url)
            return probe
        except Exception as exc:
            last_exc = exc
            if attempt == 0:
                await asyncio.sleep(2.0)
    probe.error = str(last_exc)[:80] if last_exc else "unknown"
    return probe


async def smoke_site(
    site_id: str,
    site: SiteConfig,
    *,
    posts_per_site: int = 5,
) -> SiteResult:
    """N개 게시글을 크롤하고 각각 검증해서 real/sticky/auth_wall/… 분류 집계."""
    r = SiteResult(site_id=site_id, name=site.name)
    t0 = time.monotonic()
    bar = "─" * 60
    print(
        f"\n{bar}\n[{site_id}] {site.name}\n"
        f"  board_urls[0] = {site.board_urls[0]}\n"
        f"  cookies={'YES' if site.cookies else '—'}  "
        f"js_code={'YES' if site.js_code else '—'}  "
        f"wait_for={site.wait_for or '—'}  "
        f"selector={(site.css_selector or '—')[:40]}\n{bar}"
    )

    # 1) 게시판 페이지 → 매칭 URL N개 회수
    diag = await _diagnose_board(site)
    if not diag["ok"]:
        r.error = diag["error"]
        print(f"  ✗ 게시판 fetch 실패: {diag['error']}")
        r.elapsed_s = time.monotonic() - t0
        return r

    r.board_ok = True
    matched = diag["matched"]
    r.post_urls_found = len(matched)
    tf = diag.get("title_filtered", 0)
    tf_msg = f", 제목필터 거름 {tf}건" if tf else ""
    print(f"  페이지 OK (html {diag['html_len']:,}자, 링크 {diag['total_links']}개 중 패턴 매칭 {len(matched)}건{tf_msg})")
    if not matched:
        print("  ⚠ 패턴 미스 — 첫 6개 링크 샘플:")
        for s in diag["samples"]:
            print(f"      · {s}")
        r.notes.append("post_url_pattern 매칭 0건")
        r.elapsed_s = time.monotonic() - t0
        return r

    targets = matched[:posts_per_site]
    print(f"  → 게시글 {len(targets)}개 검증 시도 (공지 핀 회피 위해 다회 sampling)")

    # 2) 각 게시글 크롤 + 검증
    crawler = Crawl4AICrawler(headless=True, output_dir="output/_smoke_tmp")
    for i, url in enumerate(targets, 1):
        probe = await _crawl_one(crawler, site_id, site, url)
        r.probes.append(probe)
        if probe.error:
            print(f"    [{i}] ✗ fetch error: {probe.error}")
            continue
        v = probe.validation
        icon = "✅" if v and v.is_real_user_post else "⚠️"
        kind = v.kind if v else "?"
        reason = v.reason if v else ""
        short_url = url.replace("https://", "")[:70]
        print(f"    [{i}] {icon} {kind:<10} text={probe.text_len:>6,}자  {short_url}")
        if v and not v.is_real_user_post:
            print(f"         사유: {reason}")

    r.elapsed_s = time.monotonic() - t0
    return r


_SKIP_DEFAULT = {"tieba", "nga"}    # 중국 본토 IP 필수 — 프록시 없이 의미 X

# 사이트 간 휴식 — anti-bot rate limit(Bahamut ACS-GOTO 등) 회피.
_INTER_SITE_DELAY = float(os.environ.get("SMOKE_INTER_SITE_DELAY", "12"))


def _jittered(base: float, jitter_ratio: float = 0.3) -> float:
    if base <= 0:
        return 0.0
    return base * (1.0 + random.uniform(-jitter_ratio, jitter_ratio))


async def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target and target not in SITES:
        print(f"[!] 알 수 없는 사이트: {target}")
        print(f"    사용 가능: {list(SITES.keys())}")
        return
    if target:
        sites_to_run = {target: SITES[target]}
    else:
        sites_to_run = {k: v for k, v in SITES.items() if k not in _SKIP_DEFAULT}
        print(f"  (기본 제외: {sorted(_SKIP_DEFAULT)} — 중국 IP 필요)")

    print(f"\n대상 사이트: {list(sites_to_run.keys())}")

    results: list[SiteResult] = []
    site_items = list(sites_to_run.items())
    for idx, (site_id, site) in enumerate(site_items):
        if idx > 0:
            delay = _jittered(_INTER_SITE_DELAY)
            print(f"\n... 사이트 간 휴식 {delay:.1f}s ({site_id} 시작 전, anti-bot 회피) ...")
            await asyncio.sleep(delay)
        try:
            r = await smoke_site(site_id, site)
        except Exception as exc:
            r = SiteResult(site_id=site_id, name=site.name, error=f"unexpected: {exc}")
            traceback.print_exc(limit=2)
        results.append(r)

    # 요약: 진짜 사용자 게시글 수 vs 시도 수 + kind breakdown
    print("\n" + "=" * 95)
    print(f"{'site':<22} {'board':^6} {'real/N':^8} {'kinds':<35} {'sec':>6}  notes")
    print("-" * 95)
    for r in results:
        board = "OK" if r.board_ok else "FAIL"
        if r.board_ok and r.post_attempts > 0:
            ratio = f"{r.real_count}/{r.post_attempts}"
            kinds = r.kind_breakdown()
            kinds_str = " ".join(f"{k}:{v}" for k, v in sorted(kinds.items(), key=lambda x: -x[1]))[:35]
        else:
            ratio = "—"
            kinds_str = "—"
        note = (r.error or "")[:25]
        print(f"{r.site_id:<22} {board:^6} {ratio:^8} {kinds_str:<35} {r.elapsed_s:>6.1f}  {note}")
    print("=" * 95)
    # 한눈 판정 라인
    fully_ok = [r.site_id for r in results if r.board_ok and r.real_count >= 1]
    partial  = [r.site_id for r in results if r.board_ok and r.post_attempts > 0 and r.real_count == 0]
    blocked  = [r.site_id for r in results if not r.board_ok]
    print(f"\n  ✅ 실사용자 게시글 회수 성공: {fully_ok}")
    print(f"  ⚠️  페이지는 받았으나 real 0건 (공지·검증 실패): {partial}")
    print(f"  ❌ 게시판 자체 차단: {blocked}")


if __name__ == "__main__":
    asyncio.run(main())
