"""TierRouter — type → Tier 매핑 + multi-label 최상위 Tier (Story 3-3)."""

from __future__ import annotations

import pytest

from detection.src.pipeline.tier_router import TYPE_TO_TIER, TierRouter


@pytest.mark.parametrize("type_value,expected_tier", list(TYPE_TO_TIER.items()))
def test_route_maps_each_known_type(type_value: str, expected_tier: str) -> None:
    assert TierRouter().route(type_value) == expected_tier


def test_unknown_type_falls_back_to_t4() -> None:
    # structured_logger가 stdout에 직접 쓰는 핸들러 + propagate=False라 caplog/capsys 둘 다
    # 캐치 불가. 동작 계약만 검증 — T4 fallback.
    router = TierRouter()
    assert router.route("아직_존재하지_않는_라벨") == "T4"
    assert router.route("") == "T4"


def test_route_multi_picks_highest_priority() -> None:
    router = TierRouter()
    # T3, T1, T2 후보 — T1 선택
    assert router.route_multi(["리세마라", "핵_치트", "계정_거래"]) == "T1"
    # T4만 — T4
    assert router.route_multi(["기타"]) == "T4"
    # 빈 후보 — T4 fallback
    assert router.route_multi([]) == "T4"
