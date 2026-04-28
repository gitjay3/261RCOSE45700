from __future__ import annotations

import os

from langdetect import DetectorFactory
from langdetect import detect as langdetect_detect
from langdetect.lang_detect_exception import LangDetectException

from shared.structured_logger import get_logger

DetectorFactory.seed = 0

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "crawler")
_logger = get_logger(__name__)

_LANG_MAP: dict[str, str] = {
    "zh-cn": "zh-CN",
    "zh-tw": "zh-TW",
}


def detect(text: str, *, correlation_id: str) -> str:
    """텍스트 언어 감지. 실패 시 "ko" 반환."""
    if not text or not text.strip():
        _logger.warning(
            "언어 감지 입력 빈 텍스트 — 기본값 ko 반환",
            extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
        )
        return "ko"
    try:
        lang = langdetect_detect(text)
        return _LANG_MAP.get(lang, lang)
    except LangDetectException as exc:
        _logger.warning(
            "언어 감지 실패: %s — 기본값 ko 반환", exc,
            extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
        )
        return "ko"
