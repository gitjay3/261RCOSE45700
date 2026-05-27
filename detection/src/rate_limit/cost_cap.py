"""Daily Cost Cap — OpenAI 일일 비용 추적 + cap 도달 시 Hold (Story 3-3, 2026-05-27 PIVOT).

Redis(DB2, `llm:cost:YYYY-MM-DD` 키, TTL 48h)에 누적 비용을 micro-USD 정수로 INCRBY 한다.
float 누적 오차 회피 + 다중 worker 안전성 보장.

`LLM_DAILY_COST_CAP_USD`(기본 $5) 도달 시 sleep loop로 hold. 자정 KST 넘어가면 키 만료 → 자동 재개.
`LLM_DAILY_COST_CAP_USD=0` 또는 unset이면 cap 비활성.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import redis

from shared.structured_logger import get_logger

_SERVICE_NAME = os.environ.get("SERVICE_NAME", "detection")
_logger = get_logger(__name__)

# SPIKE 3.0 `spike_llm.py::PRICING` 그대로 이식 (USD per 1M tokens, 2026-05 기준).
PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-08-06": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.150, "output": 0.600},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.400, "output": 1.600},
}

_KEY_TTL_SEC = 48 * 3600  # 48시간 — 자정 넘어가도 어제 키 잔존 시 정상 만료
_HOLD_SLEEP_SEC = int(os.environ.get("COST_CAP_HOLD_SLEEP_SEC", "60"))
_HOLD_MAX_RETRIES = int(os.environ.get("COST_CAP_HOLD_MAX_RETRIES", "5"))


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """단가 미등록 모델은 gpt-4o 가격으로 fallback."""
    rate = PRICING.get(model, PRICING["gpt-4o"])
    return (input_tokens * rate["input"] + output_tokens * rate["output"]) / 1_000_000


def _today_key() -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"llm:cost:{today}"


class CostCap:
    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client
        self._cap_usd = float(os.environ.get("LLM_DAILY_COST_CAP_USD", "5"))

    @property
    def enabled(self) -> bool:
        return self._cap_usd > 0

    def cumulative_usd(self) -> float:
        if not self.enabled:
            return 0.0
        raw = self._redis.get(_today_key())
        if raw is None:
            return 0.0
        return int(raw) / 1_000_000.0

    def record(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """OpenAI 호출 직후 호출. 산출 비용을 누적 + 반환."""
        cost_usd = estimate_cost_usd(model, input_tokens, output_tokens)
        if not self.enabled:
            return cost_usd
        micro = int(round(cost_usd * 1_000_000))
        if micro <= 0:
            return cost_usd
        key = _today_key()
        new_total = self._redis.incrby(key, micro)
        self._redis.expire(key, _KEY_TTL_SEC)
        _logger.debug(
            "cost recorded — model=%s cost=$%.5f cumulative=$%.4f",
            model, cost_usd, new_total / 1_000_000.0,
            extra={"correlation_id": "", "service": _SERVICE_NAME},
        )
        return cost_usd

    def check_and_hold(self) -> None:
        """OpenAI 호출 직전 호출. cap 도달 시 sleep loop로 hold."""
        if not self.enabled:
            return
        for _ in range(_HOLD_MAX_RETRIES + 1):
            cumulative = self.cumulative_usd()
            if cumulative < self._cap_usd:
                return
            _logger.warning(
                "일일 비용 cap 도달 — hold cumulative=$%.4f cap=$%.2f sleep=%ds",
                cumulative, self._cap_usd, _HOLD_SLEEP_SEC,
                extra={
                    "correlation_id": "",
                    "service": _SERVICE_NAME,
                    "cumulative_usd": cumulative,
                    "cap_usd": self._cap_usd,
                },
            )
            time.sleep(_HOLD_SLEEP_SEC)
        # max retries 초과 후에도 cap 미해소 — 호출 진행 허용(operations 책임).
        _logger.error(
            "일일 비용 cap hold 한계 초과 — 호출 진행 (운영자 조치 필요)",
            extra={"correlation_id": "", "service": _SERVICE_NAME},
        )
