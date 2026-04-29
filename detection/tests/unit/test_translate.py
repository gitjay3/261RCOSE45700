from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from detection.src.mocks.varco_mock import RateLimitError, VarcoMock
from detection.src.pipeline.translate import Translator
from shared.models.crawl_event import CrawlEvent


def _make_event(language: str, text: str = "我要卖外挂") -> CrawlEvent:
    return CrawlEvent(
        post_id="tieba_001",
        source_id="tieba_freestyle",
        site_name="贴吧 (자유게시판)",
        raw_text=text,
        language=language,
        detected_at="2026-04-29T10:00:00Z",
        correlation_id="cid-translate-001",
    )


def test_translates_zh_cn_via_varco() -> None:
    bucket = MagicMock()
    varco = VarcoMock(mode="clean")
    translator = Translator(varco, bucket)
    result = translator.translate_event(_make_event("zh-CN"))
    assert result  # fixture mock_response_clean.json의 translated_text
    assert isinstance(result, str)
    bucket.acquire.assert_called_once()


def test_translates_zh_tw_via_varco() -> None:
    bucket = MagicMock()
    varco = VarcoMock(mode="clean")
    translator = Translator(varco, bucket)
    result = translator.translate_event(_make_event("zh-TW"))
    assert result
    bucket.acquire.assert_called_once()


def test_skips_translation_for_korean() -> None:
    bucket = MagicMock()
    varco = MagicMock(spec=VarcoMock)
    translator = Translator(varco, bucket)
    event = _make_event("ko", text="매크로 판매합니다")
    result = translator.translate_event(event)
    assert result == "매크로 판매합니다"
    varco.translate.assert_not_called()
    bucket.acquire.assert_not_called()


def test_simulate_latency_p95_200ms() -> None:
    bucket = MagicMock()
    varco = VarcoMock(mode="clean")
    varco.simulate_latency(200)
    translator = Translator(varco, bucket)
    start = time.monotonic()
    translator.translate_event(_make_event("zh-CN"))
    elapsed = time.monotonic() - start
    assert elapsed >= 0.18  # 200ms ± 시스템 jitter 허용


def test_rate_limit_error_triggers_single_retry() -> None:
    bucket = MagicMock()
    varco = MagicMock(spec=VarcoMock)
    varco.translate.side_effect = [RateLimitError(retry_after=30), "translated 한국어"]
    translator = Translator(varco, bucket)
    with patch("detection.src.pipeline.translate.time.sleep") as mock_sleep:
        result = translator.translate_event(_make_event("zh-CN"))
    assert result == "translated 한국어"
    mock_sleep.assert_called_once_with(30)
    assert varco.translate.call_count == 2
