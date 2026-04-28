from __future__ import annotations

from pathlib import Path

import pytest

from crawler.src.sites.base_site import ParseError
from crawler.src.sites.tailstar import TailstarSite

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "html" / "sample_illegal_post.html"


def test_fixture_exists():
    assert _FIXTURE.is_file(), f"missing fixture: {_FIXTURE}"


def test_parse_returns_expected_fields():
    html = _FIXTURE.read_text(encoding="utf-8")
    result = TailstarSite().parse(html)

    assert result.post_id == "987654"
    assert result.title == "매크로 판매합니다"
    assert "매크로 프로그램" in result.body_text
    assert "텔레그램" in result.body_text
    assert (
        result.source_url
        == "https://tailstar.net/index.php?mid=board_main&document_srl=987654"
    )
    assert result.posted_at == "2026-04-28T09:15:00+09:00"
    assert len(result.image_urls) >= 2
    assert any(u.endswith("sample-thumb.jpg") for u in result.image_urls)
    assert any(u.endswith("sample-detail.jpg") for u in result.image_urls)
    for url in result.image_urls:
        assert url.startswith("http"), f"non-absolute image URL: {url}"


def test_parse_list_extracts_post_link():
    listing_html = (
        '<html><body>'
        '<a href="/index.php?mid=board_main&document_srl=987654">매크로 판매합니다</a>'
        '<a href="/index.php?mid=board_main&document_srl=111222">두번째 글</a>'
        '<a href="https://tailstar.net/about">소개</a>'
        '</body></html>'
    )
    items = TailstarSite().parse_list(listing_html)
    ids = {item.post_id for item in items}
    assert "987654" in ids
    assert "111222" in ids


def test_parse_raises_on_empty_html():
    with pytest.raises(ParseError, match="empty HTML"):
        TailstarSite().parse("")


def test_parse_raises_on_skeleton_html_without_title():
    with pytest.raises(ParseError, match="title not found"):
        TailstarSite().parse("<html><body><p>no title here</p></body></html>")


def test_parse_raises_on_html_without_body():
    skeleton = (
        '<html><head>'
        '<meta property="og:title" content="제목만 있음">'
        '<meta property="og:url" content="https://tailstar.net/index.php?document_srl=1">'
        '</head><body></body></html>'
    )
    with pytest.raises(ParseError, match="body not found"):
        TailstarSite().parse(skeleton)


def test_parse_list_raises_on_empty_html():
    with pytest.raises(ParseError, match="empty HTML"):
        TailstarSite().parse_list("")


def test_parse_list_raises_on_html_without_post_links():
    with pytest.raises(ParseError, match="no post entries"):
        TailstarSite().parse_list(
            "<html><body><a href='/about'>소개</a></body></html>"
        )
