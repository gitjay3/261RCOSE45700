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
