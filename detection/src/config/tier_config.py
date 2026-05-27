"""Tier Threshold Config (Story 3-3, 2026-05-27 PIVOT).

threshold는 **대시보드 디스플레이 필터로만** 작동. RDS 저장 분기에는 사용하지 않는다 — 모든 분류 결과는
1:1 저장된다 (Sprint Change Proposal 부록 A-2 전수 저장 정책).
"""

from __future__ import annotations

import os

TIER_THRESHOLDS: dict[str, float] = {
    "T1": float(os.environ.get("TIER_THRESHOLD_T1", "0.65")),
    "T2": float(os.environ.get("TIER_THRESHOLD_T2", "0.75")),
    "T3": float(os.environ.get("TIER_THRESHOLD_T3", "0.85")),
    "T4": float(os.environ.get("TIER_THRESHOLD_T4", "0.90")),
}

# Tier별 retry 시도 횟수 — Story 3-3 AC #5 실용 절충: default는 RETRY_MAX_ATTEMPTS 사용.
# 본 dict는 향후 응답 후 동일 게시글 재시도 시 또는 Story 3-6 알림 보장 로직에서 활용.
TIER_RETRY_ATTEMPTS: dict[str, int] = {
    "T1": int(os.environ.get("TIER_RETRY_T1", "3")),
    "T2": int(os.environ.get("TIER_RETRY_T2", "2")),
    "T3": int(os.environ.get("TIER_RETRY_T3", "1")),
    "T4": int(os.environ.get("TIER_RETRY_T4", "0")),
}


def is_above_threshold(tier: str, confidence: float) -> bool:
    """대시보드 디스플레이 필터용. RDS 저장 여부와 무관."""
    threshold = TIER_THRESHOLDS.get(tier, 1.0)
    return confidence >= threshold
