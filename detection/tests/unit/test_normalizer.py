"""S0 Normalizer 단위 테스트 (Story 3-7) — 정규화 + 링크 추출."""

from __future__ import annotations

from pathlib import Path

from detection.src.agents.normalizer import extract_link_candidates, extract_links, normalize

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _read_fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def test_empty_input_returns_empty_result() -> None:
    result = normalize("")
    assert result.text == ""
    assert result.links == []
    assert result.link_candidates == []
    assert result.link_stats == {
        "raw_link_count": 0,
        "raw_unique_link_count": 0,
        "trace_candidate_count": 0,
        "deduped_alias_count": 0,
        "selected_link_count": 0,
        "ranked_link_count": 0,
        "stored_candidate_count": 0,
        "stored_candidate_limit": 50,
        "stored_alias_limit_per_candidate": 50,
    }


def test_zero_width_chars_removed() -> None:
    # 단어 사이 zero-width space 삽입으로 키워드 매칭 우회 시도.
    dirty = "핵​치​트 팝니다"
    result = normalize(dirty)
    assert "​" not in result.text
    assert "핵치트" in result.text


def test_nfkc_normalizes_fullwidth() -> None:
    # 전각 라틴/숫자 → 반각 통일.
    result = normalize("ＨＡＣＫ ０１２")
    assert "HACK" in result.text
    assert "012" in result.text


def test_homoglyph_cyrillic_mapped_to_latin() -> None:
    # 키릴 а/о/с 로 위장한 라틴 문자 복원.
    result = normalize("hасk")  # h + 키릴 а + 라틴 c + k
    assert result.text == "hack"


def test_repeated_chars_collapsed() -> None:
    # NFKC 안정 문자(완성형 음절·구두점)로 3회+ 연속 → 2회 축약 검증.
    result = normalize("대박요요요요요 팝니다!!!!!")
    assert "요요요" not in result.text
    assert "요요" in result.text
    assert "!!!" not in result.text


def test_extract_markdown_link() -> None:
    links = extract_links("다운로드 [여기](https://evil.example/hack.zip) 클릭")
    assert links == ["https://evil.example/hack.zip"]


def test_extract_bare_url() -> None:
    links = extract_links("판매중 https://t.me/secretchannel 연락주세요.")
    # 끝의 마침표는 제외되어야.
    assert links == ["https://t.me/secretchannel"]


def test_extract_links_dedup_preserves_order() -> None:
    text = (
        "첫째 https://a.example/1 "
        "[같은링크](https://a.example/1) "
        "둘째 https://b.example/2"
    )
    assert extract_links(text) == ["https://a.example/1", "https://b.example/2"]


def test_links_extracted_from_raw_before_collapse() -> None:
    # 반복 축약이 URL을 훼손하지 않아야 (예: 경로의 연속 문자).
    result = normalize("받기 https://x.example/aaaa/file 보세요")
    assert result.links == ["https://x.example/aaaa/file"]


def test_mixed_language_text_preserved() -> None:
    result = normalize("外掛 판매 hack for sale 私服")
    assert "外掛" in result.text
    assert "私服" in result.text
    assert "hack" in result.text


def test_removed_char_count_nonzero_when_zero_width_stripped() -> None:
    # U+200B (zero-width space) 1자 삽입 → removed_char_count ≥ 1.
    dirty = "핵​치트"
    result = normalize(dirty)
    assert result.removed_char_count >= 1


def test_removed_char_count_zero_for_clean_text() -> None:
    result = normalize("정상적인 게시글입니다")
    assert result.removed_char_count == 0


def test_extract_links_strips_cjk_trailing_period() -> None:
    # URL 뒤 한중일 마침표(。)는 URL의 일부가 아니므로 제거.
    links = extract_links("다운로드 https://evil.example/hack。")
    assert links == ["https://evil.example/hack"]


def test_extract_links_strips_cjk_trailing_comma() -> None:
    # URL 뒤에 한중일 쉼표(，)가 있고 이후 공백으로 분리되면 쉼표를 제거.
    links = extract_links("링크 https://evil.example/x， 다음 텍스트")
    assert links == ["https://evil.example/x"]


def test_normalize_excludes_current_post_url() -> None:
    post_url = "https://www.inven.co.kr/board/lineageclassic/6482/16277"
    result = normalize(
        f"본문 [주소복사](javascript:void\\(0\\);) <{post_url}> "
        "외부 https://evil.example/link",
        exclude_links=[post_url],
    )
    assert result.links == ["https://evil.example/link"]


def test_extract_links_excludes_trailing_slash_variant() -> None:
    links = extract_links(
        "자기 링크 https://example.com/post/1/ 외부 https://evil.example/x",
        exclude_urls=["https://example.com/post/1"],
    )
    assert links == ["https://evil.example/x"]


def test_extract_links_excludes_query_fragment_and_default_port_variants() -> None:
    links = extract_links(
        "자기 링크 https://EXAMPLE.com:443/post/1?utm_source=x#reply "
        "외부 https://evil.example/x",
        exclude_urls=["https://example.com/post/1"],
    )
    assert links == ["https://evil.example/x"]


def test_html_anchor_href_extracted_before_img_src() -> None:
    # <a href="download_url"><img src="image_url"></a> 패턴에서
    # href(실제 다운로드 링크)가 src(이미지)보다 먼저 추출돼야 함.
    html = (
        '<a href="https://github.com/user/repo/releases/download/v1/hack.rar">'
        '<img src="https://github.com/user-attachments/assets/abc123.png">'
        '</a>'
    )
    links = extract_links(html)
    assert links[0] == "https://github.com/user/repo/releases/download/v1/hack.rar"
    assert "user-attachments" in links[1]


def test_html_anchor_href_only_not_img_src_when_same_slot() -> None:
    # img src는 href가 이미 슬롯을 차지하면 뒤로 밀려야 함.
    html = (
        '<a href="https://evil.example/cheat.zip">'
        '<img src="https://cdn.example/button.png">'
        '</a>'
        '<a href="https://evil.example/readme">'
        '<img src="https://cdn.example/badge.svg">'
        '</a>'
    )
    links = extract_links(html)
    # href 2개가 앞에, img src 2개가 뒤에
    assert links[:2] == [
        "https://evil.example/cheat.zip",
        "https://evil.example/readme",
    ]


def test_extract_links_dedup_by_fragment() -> None:
    # fragment만 다른 URL은 HTTP fetch 시 동일 페이지 → 중복으로 처리해야 함.
    text = (
        "[홈](https://hencheats.vercel.app/) "
        "[게임A](https://hencheats.vercel.app/#PPSA01467-01.008.001) "
        "[게임B](https://hencheats.vercel.app/#PPSA17905-01.030.000)"
    )
    links = extract_links(text)
    assert links == ["https://hencheats.vercel.app/"]


def test_extract_linked_image_captures_href_not_img_src() -> None:
    # [![alt](img_url)](href_url) 패턴에서 img_url(배지/이미지)이 아닌 href_url을 추출해야 함.
    text = "[![Download](https://img.shields.io/badge/Download-blueviolet)](https://evil.example/download)"
    links = extract_links(text)
    assert links == ["https://evil.example/download"]
    assert "img.shields.io" not in str(links)


def test_extract_multiple_linked_images_and_plain_links() -> None:
    # README 실제 패턴: 링크드 이미지 2개 + 일반 링크 1개 혼합.
    text = (
        "[![Badge](https://img.shields.io/badge/x)](https://evil.example/dupe)\n"
        "[Visit Site](https://wecheaters.com)\n"
        "[![Img](https://i.ibb.co/img.png)](https://wecheaters.com)"
    )
    links = extract_links(text)
    # img src는 없어야 하고, href들만 중복 제거된 채로.
    assert "https://evil.example/dupe" in links
    assert "https://wecheaters.com" in links
    assert "img.shields.io" not in str(links)
    assert "i.ibb.co" not in str(links)
    # wecheaters.com은 중복 제거로 1번만.
    assert links.count("https://wecheaters.com") == 1


def test_distribution_url_ranked_before_static_images() -> None:
    text = (
        "![badge](https://img.shields.io/badge/download-blue.svg)\n"
        "![shot](https://cdn.example/screenshot.png)\n"
        "다운로드 https://evil.example/files/hack.zip"
    )
    links = extract_links(text)
    assert links[0] == "https://evil.example/files/hack.zip"


def test_meta_refresh_url_is_extracted_as_navigation_candidate() -> None:
    html = '<meta http-equiv="refresh" content="0; url=https://evil.example/download">'
    candidates = extract_link_candidates(html)
    assert candidates[0].url == "https://evil.example/download"
    assert candidates[0].source_kind == "meta_refresh"


def test_iframe_src_is_extracted_as_embedded_destination_candidate() -> None:
    html = '<iframe title="loader" src="https://evil.example/payload"></iframe>'
    candidates = extract_link_candidates(html)
    assert candidates[0].url == "https://evil.example/payload"
    assert candidates[0].source_kind == "iframe_src"


def test_messenger_invite_ranked_before_generic_homepage() -> None:
    text = (
        "[홈페이지](https://example-cheat-site.test)\n"
        "[문의](https://discord.gg/abc123)"
    )
    assert extract_links(text)[0] == "https://discord.gg/abc123"


def test_fragment_aliases_are_preserved_on_selected_candidate() -> None:
    text = (
        "[홈](https://hencheats.vercel.app/) "
        "[게임A](https://hencheats.vercel.app/#PPSA01467-01.008.001) "
        "[게임B](https://hencheats.vercel.app/#PPSA17905-01.030.000)"
    )
    [candidate] = extract_link_candidates(text)
    assert candidate.url == "https://hencheats.vercel.app/"
    assert candidate.aliases == (
        "https://hencheats.vercel.app/#PPSA01467-01.008.001",
        "https://hencheats.vercel.app/#PPSA17905-01.030.000",
    )


def test_query_variants_are_not_collapsed_for_trace_candidates() -> None:
    links = extract_links(
        "A https://files.example/download?id=1 "
        "B https://files.example/download?id=2"
    )
    assert links == [
        "https://files.example/download?id=1",
        "https://files.example/download?id=2",
    ]


def test_js_location_redirect_is_extracted_with_reason() -> None:
    text = "<script>window.location.href = 'https://evil.example/landing';</script>"
    candidates = extract_link_candidates(text)
    assert candidates[0].url == "https://evil.example/landing"
    assert candidates[0].source_kind == "js_location"
    assert "redirect_or_embedded_destination:js_location" in candidates[0].reasons


def test_static_html_resources_are_explicit_low_priority_candidates() -> None:
    html = (
        '<link rel="stylesheet" href="https://cdn.example/app.css">'
        '<script src="https://cdn.example/app.js"></script>'
        '<img alt="badge" src="https://img.shields.io/badge/x.svg">'
        '<a href="https://evil.example/download/hack.rar">Download</a>'
    )
    candidates = extract_link_candidates(html)
    assert candidates[0].url == "https://evil.example/download/hack.rar"
    by_kind = {candidate.source_kind: candidate for candidate in candidates}
    assert by_kind["image_src"].priority == 10
    assert by_kind["script_src"].priority == 10
    assert by_kind["link_href"].priority == 10
    assert "low_value_image_src" in by_kind["image_src"].reasons


def test_distribution_candidate_records_selection_reasons() -> None:
    [candidate] = extract_link_candidates("[무료 핵 다운로드](https://evil.example/files/tool.dll)")
    assert candidate.priority == 100
    assert "download_file_extension" in candidate.reasons
    assert "distribution_path_hint" in candidate.reasons
    assert "distribution_text_hint" in candidate.reasons


def test_regression_1807_fragment_links_collapse_to_real_destination() -> None:
    text = _read_fixture("link_ranker_1807.md")
    candidates = extract_link_candidates(
        text,
        exclude_urls=["https://github.com/TeeKay87/HEN-Cheats-Collection"],
    )
    links = [candidate.url for candidate in candidates]

    assert links[0] == "https://hencheats.vercel.app/"
    assert "https://github.com/TeeKay87/HEN-Cheats-Collection" not in links
    assert len([url for url in links if url.startswith("https://hencheats.vercel.app/")]) == 1
    assert len(candidates[0].aliases) >= 5
    assert "distribution_text_hint" in candidates[0].reasons


def test_regression_1928_linked_images_select_href_not_badge_or_screenshot() -> None:
    text = _read_fixture("link_ranker_1928.md")
    links = extract_links(
        text,
        exclude_urls=["https://github.com/yh88-Lineage-2-Item-Dupe/.github"],
    )

    assert links[:2] == [
        "https://yh88-Lineage-2-Item-Dupe.github.io/.github",
        "https://wecheaters.com",
    ]
    assert all("img.shields.io" not in url for url in links[:3])
    assert all("i.ibb.co" not in url for url in links[:3])


def test_regression_1928_records_duplicate_site_alias() -> None:
    text = _read_fixture("link_ranker_1928.md")
    candidates = extract_link_candidates(
        text,
        exclude_urls=["https://github.com/yh88-Lineage-2-Item-Dupe/.github"],
    )
    wecheaters = next(candidate for candidate in candidates if candidate.url == "https://wecheaters.com")

    assert wecheaters.source_kind == "markdown_href"
    assert wecheaters.aliases == ()
    assert wecheaters.priority == 100
    assert "distribution_text_hint" in wecheaters.reasons


def test_normalize_stores_link_ranker_metadata() -> None:
    result = normalize(
        "[홈](https://hencheats.vercel.app/) "
        "[게임](https://hencheats.vercel.app/#GAME-1) "
        "다운로드 https://evil.example/files/tool.zip"
    )

    assert result.links[:2] == [
        "https://evil.example/files/tool.zip",
        "https://hencheats.vercel.app/",
    ]
    assert result.link_stats == {
        "raw_link_count": 3,
        "raw_unique_link_count": 3,
        "trace_candidate_count": 2,
        "deduped_alias_count": 1,
        "selected_link_count": 2,
        "ranked_link_count": 2,
        "stored_candidate_count": 2,
        "stored_candidate_limit": 50,
        "stored_alias_limit_per_candidate": 50,
    }
    assert result.link_candidates[0]["url"] == "https://evil.example/files/tool.zip"
    assert "download_file_extension" in result.link_candidates[0]["reasons"]
    assert result.link_candidates[1]["aliases"] == ["https://hencheats.vercel.app/#GAME-1"]
    assert result.link_candidates[1]["aliases_truncated_count"] == 0


def test_normalize_caps_stored_candidates_but_keeps_total_stats() -> None:
    text = " ".join(f"https://example{i}.test/download/tool.zip" for i in range(60))
    result = normalize(text)

    assert result.link_stats["trace_candidate_count"] == 60
    assert result.link_stats["stored_candidate_count"] == 50
    assert len(result.link_candidates) == 50
    assert len(result.links) == 60


def test_bahamut_redirect_wrapper_unwrapped_to_official_destination() -> None:
    text = (
        "[下載NC的PURPLE主程式]"
        "(https://ref.gamer.com.tw/redir.php?url=https%3A%2F%2Ftl.plaync.com%2Fko-kr%2Fdownload%2Findex)"
    )
    [candidate] = extract_link_candidates(text)

    assert candidate.url == "https://tl.plaync.com/ko-kr/download/index"
    assert candidate.priority == 40
    assert "official_service_install_link" in candidate.reasons
    assert candidate.aliases == (
        "https://ref.gamer.com.tw/redir.php?url=https%3A%2F%2Ftl.plaync.com%2Fko-kr%2Fdownload%2Findex",
    )


def test_official_store_domain_with_install_context_is_deprioritized() -> None:
    [candidate] = extract_link_candidates("[Steam 다운로드](https://store.steampowered.com/app/123456)")

    assert candidate.url == "https://store.steampowered.com/app/123456"
    assert candidate.priority == 40
    assert "official_service_install_link" in candidate.reasons
