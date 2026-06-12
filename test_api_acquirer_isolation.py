"""Regression tests: public endpoints expose only the five acquirer-tier
companies even when target rows coexist in the companies table.

These tests inject a mixed acquirer+target dataset into a Supabase mock that
actually applies eq() filters. If the coverage_tier filter is ever removed
from any of the four company-listing endpoints, the assertion `count == 5`
will fail because the mock returns all 7 rows instead.

No network. No database. No AI.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app

# ── Fixture data ──────────────────────────────────────────────────────────────

ACQUIRER_COMPANIES: list[dict] = [
    {
        "ticker": "AMD",
        "company_name": "Advanced Micro Devices, Inc.",
        "cik": "0000002488",
        "business_model": "Fabless CPU/GPU",
        "coverage_tier": "acquirer",
    },
    {
        "ticker": "AVGO",
        "company_name": "Broadcom Inc.",
        "cik": "0001730168",
        "business_model": "Diversified semiconductor",
        "coverage_tier": "acquirer",
    },
    {
        "ticker": "INTC",
        "company_name": "Intel Corporation",
        "cik": "0000050863",
        "business_model": "IDM CPU/GPU/foundry",
        "coverage_tier": "acquirer",
    },
    {
        "ticker": "NVDA",
        "company_name": "NVIDIA Corporation",
        "cik": "0001045810",
        "business_model": "Fabless GPU/accelerator",
        "coverage_tier": "acquirer",
    },
    {
        "ticker": "QCOM",
        "company_name": "Qualcomm Incorporated",
        "cik": "0000804328",
        "business_model": "Fabless mobile/RF SoC",
        "coverage_tier": "acquirer",
    },
]

TARGET_COMPANIES: list[dict] = [
    {
        "ticker": "LSCC",
        "company_name": "Lattice Semiconductor Corporation",
        "cik": "0000855658",
        "business_model": "Fabless low-power FPGA",
        "coverage_tier": "target",
    },
    {
        "ticker": "AMBA",
        "company_name": "Ambarella, Inc.",
        "cik": "0001580394",
        "business_model": "Fabless edge-AI vision SoC",
        "coverage_tier": "target",
    },
]

# Companies table has 7 rows: 5 acquirers + 2 targets.
ALL_COMPANIES = ACQUIRER_COMPANIES + TARGET_COMPANIES
EXPECTED_TICKERS = ["AMD", "AVGO", "INTC", "NVDA", "QCOM"]

# ── Minimal Supabase query-builder mock ───────────────────────────────────────


class _NotProxy:
    """Proxy for .not_.<method>() chains; forwards to the parent builder."""

    def __init__(self, qb: "_QB") -> None:
        self._qb = qb

    def is_(self, col: str, val: str) -> "_QB":
        # "not_.is_(col, 'null')" means exclude null rows; safe to skip for
        # tables that return empty rows (filings, claims, etc.).
        return self._qb

    def in_(self, col: str, vals: list) -> "_QB":
        return self._qb


class _QB:
    """Query builder that applies eq() filters on execute().

    Only eq() filtering is implemented — that is the one predicate the
    coverage_tier isolation depends on. All other predicates (not_, in_,
    order, limit) are accepted but not applied, because the non-companies
    table stubs return empty row lists anyway.
    """

    def __init__(self, rows: list[dict]) -> None:
        self._rows = list(rows)
        self._eq_filters: dict[str, object] = {}
        self._order_col: str | None = None
        self._order_desc: bool = False
        self._limit_n: int | None = None
        self._count_mode: str | None = None

    # ── builder methods ──────────────────────────────────────────────────────

    def select(self, columns: str = "*", count: str | None = None) -> "_QB":
        self._count_mode = count
        return self

    def eq(self, col: str, val: object) -> "_QB":
        self._eq_filters[col] = val
        return self

    @property
    def not_(self) -> _NotProxy:
        return _NotProxy(self)

    def order(self, col: str, desc: bool = False) -> "_QB":
        self._order_col = col
        self._order_desc = desc
        return self

    def limit(self, n: int) -> "_QB":
        self._limit_n = n
        return self

    def in_(self, col: str, vals: list) -> "_QB":
        return self

    def not_in(self, col: str, vals: list) -> "_QB":
        return self

    def like(self, col: str, pattern: str) -> "_QB":
        return self

    # ── terminal ─────────────────────────────────────────────────────────────

    def execute(self) -> MagicMock:
        result = list(self._rows)
        for col, val in self._eq_filters.items():
            result = [r for r in result if r.get(col) == val]
        if self._order_col:
            result.sort(
                key=lambda r: (r.get(self._order_col) or ""),
                reverse=self._order_desc,
            )
        if self._limit_n is not None:
            result = result[: self._limit_n]
        mock_result = MagicMock()
        mock_result.data = result
        mock_result.count = len(result) if self._count_mode == "exact" else None
        return mock_result


def _make_supabase() -> MagicMock:
    """Return a mock Supabase client with a filtering-capable companies table.

    All other tables (filings, briefs, claims, metrics, snapshots) return
    empty row lists so endpoint helpers don't crash while we focus purely on
    whether the companies query applies the coverage_tier filter.
    """
    client = MagicMock()

    def table(name: str) -> _QB:
        if name == "companies":
            return _QB(ALL_COMPANIES)
        return _QB([])  # empty for every other table

    client.table.side_effect = table
    return client


# ── Tests ─────────────────────────────────────────────────────────────────────

CLIENT = TestClient(app)


def _patched(fn):
    """Decorator: run fn with app.main._supabase returning _make_supabase()."""

    def wrapper():
        mock = _make_supabase()
        with patch("app.main._supabase", return_value=mock):
            fn(CLIENT)

    wrapper.__name__ = fn.__name__
    return wrapper


@_patched
def test_companies_only_returns_acquirers(client: TestClient) -> None:
    response = client.get("/companies")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 5, (
        f"Expected 5 acquirers, got {body['count']}. "
        "coverage_tier filter may be missing from GET /companies."
    )
    tickers = [c["ticker"] for c in body["companies"]]
    assert tickers == EXPECTED_TICKERS, (
        f"Wrong tickers: {tickers}. Targets must not appear in GET /companies."
    )
    print(f"PASS GET /companies → count={body['count']}, tickers={tickers}")


@_patched
def test_overview_companies_count_excludes_targets(client: TestClient) -> None:
    response = client.get("/overview")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["companies_count"] == 5, (
        f"Expected 5 in overview, got {body['companies_count']}. "
        "coverage_tier filter may be missing from GET /overview."
    )
    overview_tickers = [row["ticker"] for row in body["companies"]]
    for t in overview_tickers:
        assert t in EXPECTED_TICKERS, (
            f"Target ticker {t!r} leaked into GET /overview."
        )
    print(
        f"PASS GET /overview → companies_count={body['companies_count']}, "
        f"tickers={overview_tickers}"
    )


@_patched
def test_peers_only_returns_acquirers(client: TestClient) -> None:
    response = client.get("/peers")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 5, (
        f"Expected 5 peers, got {body['count']}. "
        "coverage_tier filter may be missing from GET /peers."
    )
    peer_tickers = {row["ticker"] for row in body["peers"]}
    assert peer_tickers == set(EXPECTED_TICKERS), (
        f"Unexpected tickers in GET /peers: {peer_tickers}."
    )
    print(f"PASS GET /peers → count={body['count']}, tickers={sorted(peer_tickers)}")


@_patched
def test_peer_trends_only_returns_acquirers(client: TestClient) -> None:
    response = client.get("/peers/trends?metric_name=TTM+Revenue")
    assert response.status_code == 200, response.text
    body = response.json()
    series_tickers = [s["ticker"] for s in body["series"]]
    for t in series_tickers:
        assert t in EXPECTED_TICKERS, (
            f"Target ticker {t!r} leaked into GET /peers/trends."
        )
    assert len(series_tickers) == 5, (
        f"Expected 5 series entries, got {len(series_tickers)}. "
        "coverage_tier filter may be missing from GET /peers/trends."
    )
    print(f"PASS GET /peers/trends → series count={len(series_tickers)}, tickers={series_tickers}")


def main() -> None:
    for fn in [
        test_companies_only_returns_acquirers,
        test_overview_companies_count_excludes_targets,
        test_peers_only_returns_acquirers,
        test_peer_trends_only_returns_acquirers,
    ]:
        fn()
    print("\nAll acquirer-isolation regression tests passed.")


if __name__ == "__main__":
    main()
