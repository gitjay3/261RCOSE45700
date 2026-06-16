"""Tier Router — type → Tier(T1/T2/T3/T4) 매핑 (Story 3-3, 2026-05-27 PIVOT).

LLM 응답의 `type` enum(9종)을 사업 우선순위 Tier로 변환한다.
"""

from __future__ import annotations

import os

from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
_logger = get_logger(__name__)


# Sprint Change Proposal 2026-05-27 + SPIKE 3.0 검증값.
TYPE_TO_TIER: dict[str, str] = {
    "핵_치트": "T1",
    "불법프로그램_배포": "T1",
    "매크로_판매": "T1",
    "사설서버": "T2",
    "계정_거래": "T2",
    "리세마라": "T3",
    "현금화": "T3",
    "광고_도배": "T3",
    "기타": "T4",
}


class TierRouter:
    def route(self, type_value: str) -> str:
        tier = TYPE_TO_TIER.get(type_value)
        if tier is None:
            _logger.warning(
                "알 수 없는 type — T4 fallback",
                extra={
                    "correlation_id": "",
                    "service": _SERVICE_NAME,
                    "unknown_type": type_value,
                },
            )
            return "T4"
        return tier
