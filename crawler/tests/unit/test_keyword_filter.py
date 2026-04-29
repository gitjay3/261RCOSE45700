from __future__ import annotations

from pathlib import Path

from crawler.src.preprocessor.keyword_filter import passes

_CID = "test-kf-001"
_FIXTURE = Path(__file__).parent.parent / "fixtures" / "html" / "sample_illegal_post.html"


class TestKeywordFilter:
    def test_passes_korean_macro_keyword(self):
        assert passes("매크로 판매합니다", correlation_id=_CID) is True

    def test_passes_chinese_keyword(self):
        assert passes("外挂辅助工具 구매", correlation_id=_CID) is True

    def test_passes_case_insensitive_english(self):
        assert passes("This is a HACK tool", correlation_id=_CID) is True

    def test_not_passes_clean_post(self):
        assert passes("오늘 날씨가 참 좋네요. 산책하고 왔어요.", correlation_id=_CID) is False

    def test_not_passes_empty_text(self):
        assert passes("", correlation_id=_CID) is False

    def test_not_passes_whitespace_only(self):
        assert passes("   ", correlation_id=_CID) is False

    def test_passes_sample_illegal_fixture(self):
        content = _FIXTURE.read_text(encoding="utf-8")
        assert passes(content, correlation_id=_CID) is True

    def test_passes_multiple_keywords_any_match(self):
        # 단 하나의 키워드만 있어도 True
        assert passes("자동사냥 관련 문의", correlation_id=_CID) is True
        assert passes("bot 프로그램", correlation_id=_CID) is True
        assert passes("exploit 코드", correlation_id=_CID) is True

    def test_passes_bot_keyword(self):
        assert passes("bot을 이용한 자동화", correlation_id=_CID) is True

    def test_not_passes_normal_game_post(self):
        assert passes("메이플스토리 사냥터 추천해주세요", correlation_id=_CID) is False
