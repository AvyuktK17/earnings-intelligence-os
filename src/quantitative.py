"""Deterministic quantitative helpers for the research-terminal endpoints.

All functions here are pure: they take already-fetched rows from
``financial_metrics`` / ``valuation_snapshots`` and shape them into
chart-ready series, latest-period summaries, and valuation multiples. No AI,
no network, no database access. Multiples are computed arithmetically from
stored values; any unavailable input yields ``None`` (never a fabricated
number).
"""

from __future__ import annotations

from typing import Any

from src.static_dashboard_backfill import VALUATION_METRIC_NAMES

# Quarter ordering for sorting fiscal periods.
_QUARTER_INDEX = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}

# Operating metric names mapped to the compact field names used by /peers.
PEER_METRIC_FIELDS = {
    "Revenue": "revenue",
    "YoY Revenue Growth": "yoy_revenue_growth",
    "Gross Margin": "gross_margin",
    "Operating Margin": "operating_margin",
    "Free-Cash-Flow Margin": "free_cash_flow_margin",
    "R&D as % of Revenue": "rd_as_pct_of_revenue",
    "TTM Revenue": "ttm_revenue",
    "TTM Operating Income": "ttm_operating_income",
    "TTM Free Cash Flow": "ttm_free_cash_flow",
    "Cash and Cash Equivalents": "cash",
    "Total Debt": "total_debt",
    "Net Cash (Debt)": "net_cash_debt",
}


def period_sort_key(fiscal_year: Any, fiscal_quarter: Any) -> tuple[int, int]:
    """Sortable key for a fiscal period; unknown quarters sort last."""
    try:
        year = int(fiscal_year)
    except (TypeError, ValueError):
        year = 0
    return (year, _QUARTER_INDEX.get(str(fiscal_quarter).strip(), 0))


def period_label(fiscal_year: Any, fiscal_quarter: Any) -> str:
    """Human-readable period label, e.g. ``"2025 Q1"``."""
    return f"{fiscal_year} {fiscal_quarter}"


def is_operating_row(row: dict) -> bool:
    """True for a quarterly operating metric (not a valuation-derived row)."""
    if row.get("metric_name") in VALUATION_METRIC_NAMES:
        return False
    return bool(row.get("fiscal_year")) and bool(row.get("fiscal_quarter"))


def operating_rows(rows: list[dict]) -> list[dict]:
    """Filter to operating rows with a valid fiscal period."""
    return [row for row in rows if is_operating_row(row)]


def sorted_periods(rows: list[dict]) -> list[dict]:
    """Distinct fiscal periods present in ``rows``, oldest first."""
    seen: dict[tuple, dict] = {}
    for row in rows:
        key = (row["fiscal_year"], row["fiscal_quarter"])
        if key not in seen:
            seen[key] = {
                "fiscal_year": row["fiscal_year"],
                "fiscal_quarter": row["fiscal_quarter"],
                "period": period_label(row["fiscal_year"], row["fiscal_quarter"]),
            }
    return sorted(
        seen.values(),
        key=lambda p: period_sort_key(p["fiscal_year"], p["fiscal_quarter"]),
    )


def build_metric_series(rows: list[dict]) -> dict[str, list[dict]]:
    """Group operating rows into per-metric time series, oldest first."""
    series: dict[str, list[dict]] = {}
    for row in operating_rows(rows):
        point = {
            "fiscal_year": row["fiscal_year"],
            "fiscal_quarter": row["fiscal_quarter"],
            "period": period_label(row["fiscal_year"], row["fiscal_quarter"]),
            "value": row.get("value"),
            "unit": row.get("unit"),
        }
        series.setdefault(row["metric_name"], []).append(point)
    for points in series.values():
        points.sort(key=lambda p: period_sort_key(p["fiscal_year"], p["fiscal_quarter"]))
    return series


def latest_period(rows: list[dict]) -> tuple | None:
    """The newest ``(fiscal_year, fiscal_quarter)`` among operating rows."""
    periods = [(r["fiscal_year"], r["fiscal_quarter"]) for r in operating_rows(rows)]
    if not periods:
        return None
    return max(periods, key=lambda p: period_sort_key(*p))


def latest_metric_values(rows: list[dict]) -> dict[str, Any]:
    """Map metric name -> value at the newest operating period."""
    period = latest_period(rows)
    if period is None:
        return {}
    return {
        row["metric_name"]: row.get("value")
        for row in operating_rows(rows)
        if (row["fiscal_year"], row["fiscal_quarter"]) == period
    }


def _safe_div(numerator: Any, denominator: Any) -> float | None:
    """Divide, returning None when either side is missing or the denom is 0."""
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def compute_multiples(
    market_cap: Any,
    enterprise_value: Any,
    ttm_revenue: Any,
    ttm_operating_income: Any,
    ttm_free_cash_flow: Any,
) -> dict[str, float | None]:
    """Deterministic valuation multiples; missing inputs yield None."""
    return {
        "ev_to_ttm_revenue": _safe_div(enterprise_value, ttm_revenue),
        "ev_to_ttm_operating_income": _safe_div(
            enterprise_value, ttm_operating_income
        ),
        "price_to_ttm_fcf": _safe_div(market_cap, ttm_free_cash_flow),
        "free_cash_flow_yield": _safe_div(ttm_free_cash_flow, market_cap),
    }
