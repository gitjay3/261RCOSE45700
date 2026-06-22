"""Listing candidate priority scoring tests."""
from __future__ import annotations

from crawler.src.scheduler.candidate_scoring import score_listing_candidate


def test_high_risk_distribution_candidate_is_p0():
    result = score_listing_candidate(
        site_id="52pojie",
        board_url="https://example.com/forum",
        title="Valorant undetected cheat loader download Discord",
        keyword_matched=True,
        has_title_keywords=True,
    )

    assert result.priority_bucket == "P0"
    assert result.score >= 70
    assert "high_risk_term" in result.reasons
    assert "contact_or_sales_term" in result.reasons
    assert "download_or_file_term" in result.reasons


def test_source_risk_alone_does_not_promote_to_p2():
    result = score_listing_candidate(
        site_id="52pojie",
        board_url="https://www.52pojie.cn/forum-16-2.html",
        title="普通讨论帖",
        keyword_matched=False,
        has_title_keywords=False,
    )

    assert result.priority_bucket == "P3"
    assert result.score > 0


def test_ascii_terms_do_not_match_inside_words_or_emoticons():
    result = score_listing_candidate(
        site_id="bahamut_lineage",
        board_url="https://forum.gamer.com.tw/B.php?bsn=842",
        title="安裝後出現 the execution arguments are not valid QQ",
        keyword_matched=False,
        has_title_keywords=False,
    )

    assert result.contact_signal == 0
    assert result.download_signal == 0
    assert result.priority_bucket == "P3"


def test_report_or_rule_post_gets_low_intent_penalty():
    result = score_listing_candidate(
        site_id="bahamut_aion",
        board_url="https://forum.gamer.com.tw/B.php?bsn=9856",
        title="【攻略】檢舉外掛的流程",
        keyword_matched=False,
        has_title_keywords=False,
    )

    assert "low_distribution_intent" in result.reasons
    assert result.priority_bucket == "P3"


def test_pojie_intro_navigation_title_is_not_p2():
    result = score_listing_candidate(
        site_id="52pojie",
        board_url="https://www.52pojie.cn/forum-16-2.html",
        title="Windows破解入门",
        keyword_matched=False,
        has_title_keywords=False,
    )

    assert "low_distribution_intent" in result.reasons
    assert result.priority_bucket == "P3"


def test_title_unmatched_mixed_board_is_sampling_candidate_not_drop():
    result = score_listing_candidate(
        site_id="ptt_mobile_game",
        board_url="https://www.ptt.cc/bbs/Mobile-game/index.html",
        title="最近設定分享",
        keyword_matched=False,
        has_title_keywords=True,
    )

    assert result.priority_bucket in {"P2", "P3"}
    assert result.exploration_bonus > 0
    assert "title_unmatched_sampling_candidate" in result.reasons


def test_low_signal_dedicated_board_still_gets_source_score():
    result = score_listing_candidate(
        site_id="bahamut_lineage",
        board_url="https://forum.gamer.com.tw/B.php?bsn=842",
        title="請問每日任務",
        keyword_matched=False,
        has_title_keywords=False,
    )

    assert result.score > 0
    assert result.priority_bucket == "P3"


def test_zero_width_and_spaced_cjk_risk_terms_are_detected():
    result = score_listing_candidate(
        site_id="bahamut_lineage_m",
        board_url="https://forum.gamer.com.tw/B.php?bsn=25908",
        title="分享 外\u200b掛 / 腳 本 設定",
        keyword_matched=False,
        has_title_keywords=False,
    )

    assert result.priority_bucket == "P2"
    assert "high_risk_term" in result.reasons
    assert "dedicated_nc_context" in result.reasons


def test_dedicated_nc_sales_contact_signal_promotes_to_p2():
    result = score_listing_candidate(
        site_id="bahamut_tl",
        board_url="https://forum.gamer.com.tw/B.php?bsn=33317",
        title="代儲 私訊 LINE",
        keyword_matched=False,
        has_title_keywords=False,
    )

    assert result.priority_bucket == "P2"
    assert "contact_or_sales_term" in result.reasons
    assert "dedicated_nc_context" in result.reasons


def test_context_terms_alone_do_not_promote_candidate():
    result = score_listing_candidate(
        site_id="bahamut_lineage",
        board_url="https://forum.gamer.com.tw/B.php?bsn=842",
        title="設定分享工具整理",
        keyword_matched=False,
        has_title_keywords=False,
    )

    assert result.priority_bucket == "P3"
    assert "context_term" not in result.reasons


def test_context_terms_boost_existing_strong_signal_only():
    result = score_listing_candidate(
        site_id="bahamut_lineage_m",
        board_url="https://forum.gamer.com.tw/B.php?bsn=25908",
        title="腳本 工具 設定",
        keyword_matched=False,
        has_title_keywords=False,
    )

    assert result.priority_bucket == "P2"
    assert "high_risk_term" in result.reasons
    assert "context_term" in result.reasons


def test_channel_context_term_alone_is_not_download_signal():
    result = score_listing_candidate(
        site_id="bahamut_aion",
        board_url="https://forum.gamer.com.tw/B.php?bsn=9856",
        title="頻道公告",
        keyword_matched=False,
        has_title_keywords=False,
    )

    assert result.download_signal == 0
    assert result.priority_bucket == "P3"


def test_ce_and_virtual_goods_context_alone_do_not_promote_candidate():
    result = score_listing_candidate(
        site_id="bahamut_lineage",
        board_url="https://forum.gamer.com.tw/B.php?bsn=842",
        title="CE 虛寶 計算機設定",
        keyword_matched=False,
        has_title_keywords=False,
    )

    assert result.priority_bucket == "P3"
    assert "context_term" not in result.reasons


def test_trainer_distribution_terms_promote_high_priority_candidate():
    result = score_listing_candidate(
        site_id="52pojie",
        board_url="https://www.52pojie.cn/forum-16-2.html",
        title="Trainer release download DC群",
        keyword_matched=False,
        has_title_keywords=False,
    )

    assert result.priority_bucket == "P0"
    assert "high_risk_term" in result.reasons
    assert "download_or_file_term" in result.reasons
    assert "contact_or_sales_term" in result.reasons


def test_farming_and_line_contact_terms_promote_dedicated_board_candidate():
    result = score_listing_candidate(
        site_id="bahamut_lineage_m",
        board_url="https://forum.gamer.com.tw/B.php?bsn=25908",
        title="搬磚 虛寶 賴群",
        keyword_matched=False,
        has_title_keywords=False,
    )

    assert result.priority_bucket == "P2"
    assert "contact_or_sales_term" in result.reasons
    assert "context_term" in result.reasons


def test_korean_account_trade_contact_terms_promote_dedicated_board_candidate():
    result = score_listing_candidate(
        site_id="inven_lineage_classic",
        board_url="https://www.inven.co.kr/board/lineage/5944",
        title="계정거래 톡방 입장",
        keyword_matched=False,
        has_title_keywords=False,
    )

    assert result.priority_bucket == "P2"
    assert "contact_or_sales_term" in result.reasons
    assert "context_term" in result.reasons
