from __future__ import annotations

import os

from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "crawler")
_logger = get_logger(__name__)

_KEYWORDS: frozenset[str] = frozenset({
    # 한국어
    "매크로", "핵", "텔레그램", "오토", "자동사냥", "부스팅", "대리",
    # 중국어
    "外挂", "破解", "辅助", "脚本", "挂机",
    # 영어
    "macro", "hack", "cheat", "bot", "exploit",
})


def passes(text: str, *, correlation_id: str) -> bool:
    """불법 프로그램 관련 키워드 포함 여부 반환. 빈 텍스트 → False."""
    if not text or not text.strip():
        return False
    text_lower = text.lower()
    matched = [kw for kw in _KEYWORDS if kw.lower() in text_lower]
    if matched:
        _logger.debug(
            "키워드 매칭: %s", matched,
            extra={"correlation_id": correlation_id, "service": _SERVICE_NAME},
        )
        return True
    return False
