"""Tests for the deterministic M&A screen scoring core (Bundle D).

Synthetic fixtures only — no network, no database, no LLM.
Run: python test_ma_screen.py
"""

from __future__ import annotations

from src.ma_screen import (
    WEIGHTS,
    acquirer_capacity,
    affordability_score,
    composite_score,
    financial_quality_score,
    percentile_rank,
    relative_size_score,
    score_pair,
    valuation_reasonableness_score,
)

ACQUIRER = {
    "ticker": "BIGCO",
    "cash": 10_000.0,
    "ttm_free_cash_flow": 5_000.0,
    "ttm_operating_income": 8_000.0,
    "total_debt": 4_000.0,
    "market_cap": 200_000.0,
}

UNIVERSE = [
    {
        "ticker": "CHEAP",
        "enterprise_value": 3_000.0,
        "gross_margin": 0.60,
        "free_cash_flow_margin": 0.25,
        "yoy_revenue_growth": 0.20,
        "ev_to_ttm_revenue": 4.0,
    },
    {
        "ticker": "RICH",
        "enterprise_value": 20_000.0,
        "gross_margin": 0.70,
        "free_cash_flow_margin": 0.30,
        "yoy_revenue_growth": 0.40,
        "ev_to_ttm_revenue": 20.0,
    },
    {
        "ticker": "THIN",
        "enterprise_value": None,
        "gross_margin": None,
        "free_cash_flow_margin": None,
        "yoy_revenue_growth": None,
        "ev_to_ttm_revenue": None,
    },
]


def test_capacity() -> None:
    # 10000 cash + 2*5000 FCF + max(0, 3*8000 - 4000) = 40000
    assert acquirer_capacity(ACQUIRER) == 40_000.0
    # Missing cash → None (cash is the floor of the model)
    assert acquirer_capacity({"ttm_free_cash_flow": 1.0}) is None
    # Negative FCF and negative operating income contribute nothing
    assert acquirer_capacity(
        {"cash": 100.0, "ttm_free_cash_flow": -50.0,
         "ttm_operating_income": -10.0, "total_debt": 5.0}
    ) == 100.0
    print("ok capacity")


def test_piecewise_bounds() -> None:
    assert affordability_score(10_000.0, 40_000.0) == 100.0  # ratio 0.25
    assert affordability_score(60_000.0, 40_000.0) == 0.0  # ratio 1.5
    mid = affordability_score(35_000.0, 40_000.0)  # ratio 0.875, inside band
    assert mid is not None and 0.0 < mid < 100.0
    assert affordability_score(None, 40_000.0) is None
    assert affordability_score(10_000.0, 0.0) is None  # non-positive capacity
    assert relative_size_score(4_000.0, 200_000.0) == 100.0  # ratio 0.02
    assert relative_size_score(100_000.0, 200_000.0) == 0.0  # ratio 0.5
    assert relative_size_score(4_000.0, None) is None
    print("ok piecewise bounds")


def test_percentile_rank() -> None:
    assert percentile_rank(4.0, [4.0, 20.0]) == 25.0  # midrank of a tie
    assert percentile_rank(20.0, [4.0, 20.0]) == 75.0
    assert percentile_rank(None, [1.0, 2.0]) is None
    assert percentile_rank(1.0, [None, None]) is None
    print("ok percentile rank")


def test_rank_components() -> None:
    cheap, rich, thin = UNIVERSE
    # CHEAP is cheaper → higher valuation-reasonableness than RICH
    v_cheap = valuation_reasonableness_score(cheap, UNIVERSE)
    v_rich = valuation_reasonableness_score(rich, UNIVERSE)
    assert v_cheap is not None and v_rich is not None and v_cheap > v_rich
    # RICH has better quality metrics across the board
    q_cheap = financial_quality_score(cheap, UNIVERSE)
    q_rich = financial_quality_score(rich, UNIVERSE)
    assert q_cheap is not None and q_rich is not None and q_rich > q_cheap
    # THIN has nothing → honest None, never a fabricated rank
    assert financial_quality_score(thin, UNIVERSE) is None
    assert valuation_reasonableness_score(thin, UNIVERSE) is None
    print("ok rank components")


def test_composite_renormalization() -> None:
    full = composite_score(
        {"affordability": 80.0, "relative_size": 80.0,
         "financial_quality": 80.0, "valuation_reasonableness": 80.0}
    )
    assert full["composite"] == 80.0 and full["coverage"] == 1.0
    assert abs(sum(full["weights_applied"].values()) - 1.0) < 1e-9

    partial = composite_score(
        {"affordability": 100.0, "relative_size": None,
         "financial_quality": None, "valuation_reasonableness": 0.0}
    )
    # weights renormalize over 0.35 + 0.20 = 0.55 → 100*(35/55) ≈ 63.6
    assert partial["coverage"] == 0.55
    assert partial["composite"] == 63.6
    assert abs(sum(partial["weights_applied"].values()) - 1.0) < 1e-9

    empty = composite_score(
        {k: None for k in WEIGHTS}
    )
    assert empty["composite"] is None and empty["coverage"] == 0.0
    print("ok composite renormalization")


def test_score_pair_deterministic_and_null_safe() -> None:
    cheap, _, thin = UNIVERSE
    first = score_pair(ACQUIRER, cheap, UNIVERSE)
    second = score_pair(ACQUIRER, cheap, UNIVERSE)
    assert first == second  # deterministic across reruns
    assert first["composite"] is not None
    assert first["coverage"] == 1.0
    assert first["null_reasons"] is None
    assert first["weights"] == WEIGHTS

    sparse = score_pair(ACQUIRER, thin, UNIVERSE)
    assert sparse["composite"] is None
    assert sparse["coverage"] == 0.0
    assert set(sparse["null_reasons"]) == set(WEIGHTS)
    print("ok score_pair determinism + null safety")


if __name__ == "__main__":
    test_capacity()
    test_piecewise_bounds()
    test_percentile_rank()
    test_rank_components()
    test_composite_renormalization()
    test_score_pair_deterministic_and_null_safe()
    print("All ma_screen tests passed.")
