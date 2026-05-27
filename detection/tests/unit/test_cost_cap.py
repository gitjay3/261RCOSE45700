"""CostCap — micro-USD INCRBY + check_and_hold (Story 3-3)."""

from __future__ import annotations

from unittest.mock import patch

import fakeredis
import pytest

from detection.src.rate_limit import cost_cap as cost_cap_module
from detection.src.rate_limit.cost_cap import CostCap, estimate_cost_usd


@pytest.fixture
def fake_redis() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture(autouse=True)
def _env_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_DAILY_COST_CAP_USD", "5")


def test_record_accumulates_cost_under_cap(fake_redis: fakeredis.FakeRedis) -> None:
    cap = CostCap(fake_redis)
    # gpt-4o: input $2.5/1M, output $10/1M → 1000 in + 500 out = $0.0025 + $0.005 = $0.0075
    cost = cap.record(input_tokens=1000, output_tokens=500, model="gpt-4o")
    assert cost == pytest.approx(0.0075, rel=1e-3)
    # 누적 비용은 cap 미만 — hold 없음.
    cap.check_and_hold()
    assert cap.cumulative_usd() == pytest.approx(0.0075, rel=1e-3)


def test_check_and_hold_sleeps_when_cap_reached(
    fake_redis: fakeredis.FakeRedis, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Cap을 거의 가득 채워서 직후 check가 hold loop에 진입하도록.
    cap = CostCap(fake_redis)
    # 1회 호출로 $5 초과 — gpt-4o 기준 output 500k 토큰 ≈ $5.
    cap.record(input_tokens=0, output_tokens=500_000, model="gpt-4o")
    assert cap.cumulative_usd() >= 5.0

    sleep_calls: list[float] = []
    monkeypatch.setattr(cost_cap_module.time, "sleep", lambda s: sleep_calls.append(s))

    cap.check_and_hold()
    # hold loop가 sleep을 _HOLD_MAX_RETRIES+1 회 호출했어야 함 (cap 해소 안 되므로).
    assert len(sleep_calls) >= 1


def test_cap_disabled_when_zero(fake_redis: fakeredis.FakeRedis, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_DAILY_COST_CAP_USD", "0")
    cap = CostCap(fake_redis)
    assert cap.enabled is False
    # record는 비용 산출만 반환, INCRBY 없음.
    cost = cap.record(input_tokens=100, output_tokens=50, model="gpt-4o")
    assert cost > 0
    assert cap.cumulative_usd() == 0.0
    # check_and_hold는 즉시 return — sleep 없음.
    with patch("detection.src.rate_limit.cost_cap.time.sleep") as mock_sleep:
        cap.check_and_hold()
    mock_sleep.assert_not_called()


def test_estimate_cost_fallback_to_gpt4o() -> None:
    cost_known = estimate_cost_usd("gpt-4o", 1000, 500)
    cost_unknown = estimate_cost_usd("아직-출시-안된-모델", 1000, 500)
    assert cost_known == pytest.approx(cost_unknown, rel=1e-9)
