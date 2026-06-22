"""Cheap candidate priority scoring for crawl inventory experiments."""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class CandidateScore:
    score: int
    priority_bucket: str
    reasons: list[str]
    source_risk: int
    keyword_signal: int
    contact_signal: int
    download_signal: int
    game_signal: int
    exploration_bonus: int


_SOURCE_RISK: dict[str, int] = {
    "52pojie": 20,
    "ptt_mobile_game": 8,
}

_DEDICATED_NC_SOURCES = frozenset({
    "inven_lineage_classic",
    "ptt",
    "bahamut_lineage",
    "bahamut_lineage_m",
    "bahamut_lineage_w",
    "bahamut_lineage_classic",
    "bahamut_aion",
    "bahamut_aion2",
    "bahamut_bns",
    "bahamut_tl",
})

_HIGH_RISK_TERMS = (
    "hack", "cheat", "crack", "macro", "bot", "bypass", "injector", "loader",
    "undetected", "hwid", "aimbot", "esp", "wallhack", "keyauth", "trainer",
    "cheat engine",
    "핵", "치트", "매크로", "봇", "우회", "오토", "자동사냥", "사설서버", "프리서버",
    "外掛", "外挂", "輔助", "辅助", "破解", "私服", "自動", "自动",
    "腳本", "脚本", "掛機", "挂机", "巨集", "加速器", "修改器",
)

_CONTACT_TERMS = (
    "telegram", "discord", "wechat", "weixin", "kakao", "openchat",
    "line", "qq号", "qq號", "qq群", "qq 群", "qq:", "dc群", "dc 群",
    "텔레그램", "디스코드", "디코", "카톡", "오픈채팅", "오픈톡", "문의", "판매", "구매",
    "팝니다", "삽니다", "거래", "현거래", "계정거래", "작업장", "대리", "대리육성",
    "톡방",
    "聯絡", "联系", "出售", "购买", "收購", "收购", "代練", "代练",
    "代打", "代肝", "代儲", "代储", "代充", "搬磚", "搬砖", "私訊", "私信", "私聊", "賴",
)

_DOWNLOAD_TERMS = (
    "download", "release", "github", "mediafire", "mega.nz", "drive.google",
    "dropbox", "apk", "exe", "dll", "zip", "rar", "7z",
    "다운로드", "다운", "파일", "첨부", "下載", "下载", "附件",
)

_GAME_TERMS = (
    "lineage", "리니지", "天堂", "maple", "메이플", "楓之谷", "枫之谷",
    "roblox", "로블록스", "valorant", "발로란트", "cs2", "counter-strike",
    "minecraft", "마인크래프트", "aion", "아이온", "blade", "bns",
)

_CONTEXT_TERMS = (
    "tool", "tools", "setting", "settings", "guide", "channel", "ce",
    "설정", "세팅", "공유", "자료", "버전", "방입", "입장", "링크문의",
    "工具", "插件", "分享", "設定", "设置", "教程", "教學", "教学",
    "計算機", "计算器", "科技", "穩定", "稳定", "更新", "版本", "群",
    "頻道", "频道", "頻道連結", "频道链接", "虛寶", "虚宝",
)

_LOW_INTENT_TERMS = (
    "공지", "규정", "신고", "운영자", "공식", "점검", "패치노트",
    "檢舉", "举报", "官方", "規定", "规定", "版規", "版规", "公告", "目錄", "目录",
    "入門", "入门", "新手", "導航", "导航", "索引",
)


def _normalize_for_matching(text: str) -> str:
    """Normalize listing text before cheap keyword matching."""
    normalized = unicodedata.normalize("NFKC", text or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Cf").lower()


def _compact_cjk_text(text: str) -> str:
    """Remove punctuation/separators for non-ASCII phrase matching only."""
    return "".join(
        ch for ch in text
        if not unicodedata.category(ch).startswith(("P", "S", "Z"))
    )


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = _normalize_for_matching(text)
    compact = _compact_cjk_text(lowered)
    for term in terms:
        needle = _normalize_for_matching(term)
        if needle.isascii():
            pattern = rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])"
            if re.search(pattern, lowered):
                return True
        elif needle in lowered or _compact_cjk_text(needle) in compact:
            return True
    return False


def score_listing_candidate(
    *,
    site_id: str,
    board_url: str,
    title: str,
    keyword_matched: bool,
    has_title_keywords: bool,
) -> CandidateScore:
    """Score a listing-stage candidate without fetching the detail page.

    This score is intentionally cheap and explainable. It must not be used as a
    hard drop rule by itself; low-score candidates still need sampling so title
    euphemisms and source-specific slang can be discovered.
    """
    haystack = " ".join([site_id, board_url, title])
    reasons: list[str] = []

    source_risk = _SOURCE_RISK.get(site_id, 4)
    if source_risk >= 10:
        reasons.append(f"source_risk:{site_id}")

    keyword_signal = 25 if keyword_matched else 0
    if keyword_signal:
        reasons.append("title_keyword_match")

    high_risk_signal = 30 if _contains_any(haystack, _HIGH_RISK_TERMS) else 0
    if high_risk_signal:
        reasons.append("high_risk_term")

    contact_signal = 20 if _contains_any(haystack, _CONTACT_TERMS) else 0
    if contact_signal:
        reasons.append("contact_or_sales_term")

    download_signal = 20 if _contains_any(haystack, _DOWNLOAD_TERMS) else 0
    if download_signal:
        reasons.append("download_or_file_term")

    has_context_terms = _contains_any(haystack, _CONTEXT_TERMS)

    game_signal = 10 if _contains_any(haystack, _GAME_TERMS) else 0
    if game_signal:
        reasons.append("game_term")

    source_context_bonus = 0
    if site_id in _DEDICATED_NC_SOURCES and (
        high_risk_signal or contact_signal or download_signal
    ):
        source_context_bonus = 6
        reasons.append("dedicated_nc_context")

    context_signal = 8 if has_context_terms and (
        keyword_signal or high_risk_signal or contact_signal or download_signal
    ) else 0
    if context_signal:
        reasons.append("context_term")

    exploration_bonus = 6 if has_title_keywords and not keyword_matched else 0
    if exploration_bonus:
        reasons.append("title_unmatched_sampling_candidate")

    low_intent_penalty = -15 if _contains_any(haystack, _LOW_INTENT_TERMS) else 0
    if low_intent_penalty:
        reasons.append("low_distribution_intent")

    score = (
        source_risk
        + keyword_signal
        + high_risk_signal
        + contact_signal
        + download_signal
        + game_signal
        + source_context_bonus
        + context_signal
        + exploration_bonus
        + low_intent_penalty
    )
    score = max(0, score)

    strong_signal_count = sum(
        1
        for signal in (keyword_signal + high_risk_signal, contact_signal, download_signal)
        if signal > 0
    )
    has_distribution_combo = strong_signal_count >= 2

    if score >= 70 and has_distribution_combo:
        priority_bucket = "P0"
    elif score >= 45 and has_distribution_combo:
        priority_bucket = "P1"
    elif (
        score >= 25
        and (high_risk_signal or contact_signal or download_signal)
        and not (low_intent_penalty and not (contact_signal or download_signal))
    ):
        priority_bucket = "P2"
    else:
        priority_bucket = "P3"

    return CandidateScore(
        score=score,
        priority_bucket=priority_bucket,
        reasons=reasons,
        source_risk=source_risk,
        keyword_signal=keyword_signal + high_risk_signal,
        contact_signal=contact_signal,
        download_signal=download_signal,
        game_signal=game_signal,
        exploration_bonus=exploration_bonus,
    )
