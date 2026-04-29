"""
크롤링 대상 사이트 레지스트리.

새 사이트 추가 방법:
  1. 아래 SITES 딕셔너리에 SiteConfig 항목 추가
  2. enabled=True 로 활성화
  3. 필요 시 image_filter 함수 작성

FR1 대상 (epics.md 기준):
  tailstar.net / PTT / Dcard / tieba.baidu.com / 52pojie.cn / bbs.nga.cn
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field  # noqa: F401


@dataclass
class SiteConfig:
    name: str                                           # 표시 이름
    description: str                                    # 사이트 설명
    board_urls: list[str]                               # 크롤링할 게시판 URL 목록
    post_url_pattern: str                               # 게시글 URL 정규식 패턴
    image_filter: Callable[[dict], bool] | None = None  # 사용자 업로드 이미지 필터 (None = score 기준만 사용)
    css_selector: str | None = None                     # 본문 영역 CSS 셀렉터 (이미지 추출 범위도 제한)
    post_id_extractor: Callable[[str], str] = field(
        default=lambda url: url.rstrip("/").split("/")[-1]
    )                                                   # URL → post_id (기본: 마지막 경로 세그먼트)
    enabled: bool = True
    note: str = ""                                      # 접근 제한·특이사항


# ──────────────────────────────────────────────
# 사이트별 이미지 필터 함수
# ──────────────────────────────────────────────

def _inven_image_filter(img: dict) -> bool:
    """인벤: upload2/3.inven.co.kr/upload/.../bbs/ 경로만 허용."""
    src = img.get("src", "")
    return (
        ("upload2.inven.co.kr/upload" in src or "upload3.inven.co.kr/upload" in src)
        and "/bbs/" in src
    )


def _dcard_image_filter(img: dict) -> bool:
    """Dcard: images.dcard.tw 또는 megapx.dcard.tw 도메인만 허용."""
    src = img.get("src", "")
    return "dcard.tw" in src and ("images." in src or "megapx." in src)


def _tieba_image_filter(img: dict) -> bool:
    """바이두 티에바: tiebapic.baidu.com 또는 imgsrc.baidu.com 도메인만 허용."""
    src = img.get("src", "")
    return "tiebapic.baidu.com" in src or "imgsrc.baidu.com" in src


def _pojie_image_filter(img: dict) -> bool:
    """52pojie: attach.52pojie.cn 또는 img.52pojie.cn 도메인만 허용."""
    src = img.get("src", "")
    return "52pojie.cn" in src and ("attach." in src or "img." in src)


def _nga_image_filter(img: dict) -> bool:
    """NGA: img.nga.178.com 또는 img2.nga.178.com 도메인만 허용."""
    src = img.get("src", "")
    return "nga.178.com" in src and "img" in src


# ──────────────────────────────────────────────
# 사이트 레지스트리 (여기서 enabled 를 조정하세요)
# ──────────────────────────────────────────────

SITES: dict[str, SiteConfig] = {

    # ── 한국 ──────────────────────────────────
    "tailstar": SiteConfig(
        name="테일스타",
        description="한국 게임 커뮤니티 — 매크로/핵 게시물 주요 출처",
        board_urls=[
            "https://tailstar.net/board_issue",     # 커뮤니티 게시판
        ],
        post_url_pattern=r"https://tailstar\.net/\d+$",
        css_selector=None,                          # XE 셀렉터가 페이지 타입마다 달라 전체 파싱 후 score 필터 사용
        image_filter=None,                          # 외부 이미지(imgur 등) 사용 → score 기준만 적용
        enabled=False,
    ),

    "inven_maple": SiteConfig(
        name="인벤 (메이플스토리)",
        description="인벤 메이플스토리 자유게시판",
        board_urls=[
            "https://www.inven.co.kr/board/maple/2298",
        ],
        post_url_pattern=r"https://www\.inven\.co\.kr/board/maple/2298/\d+$",
        css_selector=".articleMain",                # 게시글 제목+본문 영역 (nav/sidebar 제외)
        image_filter=_inven_image_filter,
        enabled=True,
    ),

    "inven_lineage_classic": SiteConfig(
        name="인벤 (리니지 클래식)",
        description="인벤 리니지 클래식 자유게시판",
        board_urls=[
            "https://www.inven.co.kr/board/lineageclassic/6482",
        ],
        post_url_pattern=r"https://www\.inven\.co\.kr/board/lineageclassic/6482/\d+$",
        css_selector=".articleMain",
        image_filter=_inven_image_filter,
        enabled=True,
    ),

    # ── 대만 ──────────────────────────────────
    "ptt": SiteConfig(
        name="PTT",
        description="대만 최대 BBS — C_Chat·HatePolitics 게시판",
        board_urls=[
            "https://www.ptt.cc/bbs/C_Chat/index.html",
        ],
        post_url_pattern=r"https://www\.ptt\.cc/bbs/C_Chat/M\.\d+",
        image_filter=None,
        enabled=True,          # 18세 인증 쿠키 필요 → Story 2.6 구현 시 활성화
        note="over18 쿠키 주입 필요. js_code로 처리 예정.",
    ),

    "dcard": SiteConfig(
        name="Dcard",
        description="대만 대학생 커뮤니티 — 게임 게시판",
        board_urls=[
            "https://www.dcard.tw/f/game",
        ],
        post_url_pattern=r"https://www\.dcard\.tw/f/game/p/\d+",
        image_filter=_dcard_image_filter,
        enabled=True,          # JS 렌더링 복잡도 확인 후 활성화
        note="React SPA, 무한스크롤 게시판. wait_for 튜닝 필요.",
    ),

    # ── 중국 ──────────────────────────────────
    "tieba": SiteConfig(
        name="바이두 티에바",
        description="중국 바이두 게임 커뮤니티 — 핵/매크로 게시물 출처",
        board_urls=[
            "https://tieba.baidu.com/f?kw=游戏外挂",
            "https://tieba.baidu.com/f?kw=手游辅助",
        ],
        post_url_pattern=r"https://tieba\.baidu\.com/p/\d+",
        image_filter=_tieba_image_filter,
        enabled=True,          # 중국 IP 차단 가능성 — 프록시 설정 후 활성화
        note="중국 IP 우선 권장. NodeMaven 프록시 연동 후 활성화.",
    ),

    "52pojie": SiteConfig(
        name="52pojie",
        description="중국 최대 크랙/리버싱 커뮤니티",
        board_urls=[
            "https://www.52pojie.cn/forum-16-1.html",   # 游戏辅助 게시판
        ],
        post_url_pattern=r"https://www\.52pojie\.cn/thread-\d+-\d+-\d+\.html",
        image_filter=_pojie_image_filter,
        enabled=True,
        note="Cloudflare 보호. stealth + 프록시 조합 필요.",
    ),

    "nga": SiteConfig(
        name="NGA BBS",
        description="중국 게임 커뮤니티 NGA — 게임 핵 관련 포럼",
        board_urls=[
            "https://bbs.nga.cn/thread.php?fid=488",    # 游戏辅助 관련
        ],
        post_url_pattern=r"https://bbs\.nga\.cn/read\.php\?tid=\d+",
        image_filter=_nga_image_filter,
        enabled=True,
        note="로그인 없이 공개 게시글만 접근 가능.",
    ),
}


def get_enabled_sites() -> dict[str, SiteConfig]:
    """활성화된 사이트만 반환."""
    return {k: v for k, v in SITES.items() if v.enabled}
