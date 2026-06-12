"""Deterministic M&A screen scoring (Bundle D).

All functions are pure: they take already-fetched values and return scores.
No AI, no network, no database access. Any unavailable input yields ``None``
for that component (never a fabricated number); the composite is computed
over available components with weights renormalized, and ``coverage`` reports
the original weight mass present so thin-data pairs are visibly thin.

The screen never produces a deal probability, offer price, target price, or
recommendation. Constants below are fixed and documented — not tunable per
run — so every persisted score is reproducible from its inputs.
"""

from __future__ import annotations

from typing import Any

# Composite weights (Section 4 of the Bundle D scope; locked 2026-06-11).
WEIGHTS: dict[str, float] = {
    "affordability": 0.35,
    "relative_size": 0.15,
    "financial_quality": 0.30,
    "valuation_reasonableness": 0.20,
}

# Affordability constants (provisional per scope Section 9.4; sanity-checked
# against a known historical deal before freezing).
FCF_YEARS = 2.0  # k: years of TTM FCF counted toward capacity
DEBT_HEADROOM_MULTIPLE = 3.0  # × TTM operating income (EBITDA proxy), net of existing debt

# Piecewise scoring bounds. ratio = target EV / denominator.
_AFFORDABILITY_FULL = 0.25  # ratio at or below → 100
_AFFORDABILITY_ZERO = 1.50  # ratio at or above → 0
_SIZE_FULL = 0.02  # target EV / acquirer market cap at or below → 100
_SIZE_ZERO = 0.50  # at or above → 0


def _num(value: Any) -> float | None:
    """Coerce to float; None for missing/invalid (never raises)."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _linear_score(ratio: float, full: float, zero: float) -> float:
    """100 at/below ``full``, 0 at/above ``zero``, linear in between."""
    if ratio <= full:
        return 100.0
    if ratio >= zero:
        return 0.0
    return 100.0 * (zero - ratio) / (zero - full)


def acquirer_capacity(acquirer: dict) -> float | None:
    """Deterministic acquisition capacity in the acquirer's reporting currency.

    capacity = cash + FCF_YEARS × TTM FCF
             + max(0, DEBT_HEADROOM_MULTIPLE × TTM operating income − total debt)

    Requires ``cash``; FCF and headroom terms are included only when their
    inputs are present (a missing optional term contributes 0, but a missing
    ``cash`` makes the whole capacity None — cash is the floor of the model).
    """
    cash = _num(acquirer.get("cash"))
    if cash is None:
        return None
    capacity = cash
    ttm_fcf = _num(acquirer.get("ttm_free_cash_flow"))
    if ttm_fcf is not None and ttm_fcf > 0:
        capacity += FCF_YEARS * ttm_fcf
    ttm_oi = _num(acquirer.get("ttm_operating_income"))
    total_debt = _num(acquirer.get("total_debt"))
    if ttm_oi is not None and total_debt is not None and ttm_oi > 0:
        capacity += max(0.0, DEBT_HEADROOM_MULTIPLE * ttm_oi - total_debt)
    return capacity


def affordability_score(target_ev: Any, capacity: Any) -> float | None:
    ev = _num(target_ev)
    cap = _num(capacity)
    if ev is None or cap is None or cap <= 0 or ev <= 0:
        return None
    return _linear_score(ev / cap, _AFFORDABILITY_FULL, _AFFORDABILITY_ZERO)


def relative_size_score(target_ev: Any, acquirer_market_cap: Any) -> float | None:
    ev = _num(target_ev)
    mc = _num(acquirer_market_cap)
    if ev is None or mc is None or mc <= 0 or ev <= 0:
        return None
    return _linear_score(ev / mc, _SIZE_FULL, _SIZE_ZERO)


def percentile_rank(value: Any, universe_values: list[Any]) -> float | None:
    """Percentile rank (0–100) of ``value`` among non-null universe values.

    Midrank convention: (count_below + 0.5 × count_equal) / n × 100.
    Returns None when the value is missing or the universe has no usable values.
    """
    v = _num(value)
    if v is None:
        return None
    clean = [c for c in (_num(u) for u in universe_values) if c is not None]
    if not clean:
        return None
    below = sum(1 for c in clean if c < v)
    equal = sum(1 for c in clean if c == v)
    return 100.0 * (below + 0.5 * equal) / len(clean)


# Target metrics entering financial quality, all "higher is better".
_QUALITY_FIELDS = ("gross_margin", "free_cash_flow_margin", "yoy_revenue_growth")


def financial_quality_score(target: dict, universe: list[dict]) -> float | None:
    """Mean percentile rank of the target's quality metrics vs the universe.

    Each metric is ranked independently; metrics missing on the target are
    dropped (not imputed). None when no quality metric is available at all.
    """
    ranks: list[float] = []
    for field in _QUALITY_FIELDS:
        rank = percentile_rank(
            target.get(field), [row.get(field) for row in universe]
        )
        if rank is not None:
            ranks.append(rank)
    if not ranks:
        return None
    return sum(ranks) / len(ranks)


def valuation_reasonableness_score(target: dict, universe: list[dict]) -> float | None:
    """Inverted percentile rank of EV/TTM revenue vs the screened universe.

    Cheaper-than-peers scores higher. This is *relative to the screened
    universe on the snapshot date* — it is never a cheap/expensive verdict.
    """
    rank = percentile_rank(
        target.get("ev_to_ttm_revenue"),
        [row.get("ev_to_ttm_revenue") for row in universe],
    )
    if rank is None:
        return None
    return 100.0 - rank


def composite_score(components: dict[str, float | None]) -> dict:
    """Weighted composite over available components, weights renormalized.

    Returns ``composite`` (None when no component is available), ``coverage``
    (original weight mass present, 0–1), and ``weights_applied`` (the
    renormalized weights actually used, empty when nothing is available).
    """
    present = {
        name: value
        for name, value in components.items()
        if name in WEIGHTS and value is not None
    }
    weight_mass = sum(WEIGHTS[name] for name in present)
    if not present or weight_mass <= 0:
        return {"composite": None, "coverage": 0.0, "weights_applied": {}}
    weights_applied = {name: WEIGHTS[name] / weight_mass for name in present}
    composite = sum(present[name] * weights_applied[name] for name in present)
    return {
        "composite": round(composite, 1),
        "coverage": round(weight_mass, 4),
        "weights_applied": {k: round(v, 4) for k, v in weights_applied.items()},
    }


def score_pair(acquirer: dict, target: dict, universe: list[dict]) -> dict:
    """Score one reviewed (acquirer, target) pair.

    ``acquirer``/``target`` carry the pre-fetched deterministic inputs
    (cash, ttm_free_cash_flow, ttm_operating_income, total_debt, market_cap,
    enterprise_value, gross_margin, free_cash_flow_margin,
    yoy_revenue_growth, ev_to_ttm_revenue); ``universe`` is the full list of
    target input dicts for rank-based components. Returns components,
    composite, coverage, applied weights, and per-component null reasons.
    """
    capacity = acquirer_capacity(acquirer)
    target_ev = target.get("enterprise_value")

    components: dict[str, float | None] = {
        "affordability": affordability_score(target_ev, capacity),
        "relative_size": relative_size_score(target_ev, acquirer.get("market_cap")),
        "financial_quality": financial_quality_score(target, universe),
        "valuation_reasonableness": valuation_reasonableness_score(target, universe),
    }

    null_reasons = {}
    if components["affordability"] is None:
        null_reasons["affordability"] = (
            "Missing or non-positive target EV or acquirer capacity inputs."
        )
    if components["relative_size"] is None:
        null_reasons["relative_size"] = (
            "Missing or non-positive target EV or acquirer market cap."
        )
    if components["financial_quality"] is None:
        null_reasons["financial_quality"] = (
            "No quality metric (gross margin, FCF margin, revenue growth) available."
        )
    if components["valuation_reasonableness"] is None:
        null_reasons["valuation_reasonableness"] = (
            "EV/TTM revenue unavailable for the target or the universe."
        )

    result = composite_score(components)
    return {
        "acquirer_ticker": acquirer.get("ticker"),
        "target_ticker": target.get("ticker"),
        "components": {
            k: (round(v, 1) if v is not None else None) for k, v in components.items()
        },
        "composite": result["composite"],
        "coverage": result["coverage"],
        "weights": WEIGHTS,
        "weights_applied": result["weights_applied"],
        "null_reasons": null_reasons or None,
        "acquirer_capacity": round(capacity, 1) if capacity is not None else None,
    }
