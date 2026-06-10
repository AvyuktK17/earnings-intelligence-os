"""Test the GET /peers and GET /peers/trends endpoints.

Read-only against live Supabase: no mutations, no AI calls. Verifies the
latest-period peer table covers all five companies, that valuation multiples
are computed deterministically from stored values, that snapshot dates are
returned, and that the payload never implies live market data.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app
from src.quantitative import compute_multiples

EXPECTED_TICKERS = {"AMD", "AVGO", "INTC", "NVDA", "QCOM"}


def main() -> None:
    client = TestClient(app)

    response = client.get("/peers")
    assert response.status_code == 200, response.status_code
    body = response.json()

    assert body["count"] == 5, f"Expected 5 peers, got {body['count']}."
    tickers = {row["ticker"] for row in body["peers"]}
    assert tickers == EXPECTED_TICKERS, tickers

    # Never imply live data.
    assert body["valuation_is_live"] is False
    assert "snapshot" in body["valuation_disclaimer"].lower()
    assert body["valuation_snapshot_dates"], "snapshot dates must be present."
    assert body["comparability_notes"], "comparability notes must be present."

    for row in body["peers"]:
        # Every peer carries the operating fields and the valuation fields.
        for field in (
            "revenue",
            "gross_margin",
            "ttm_revenue",
            "ttm_free_cash_flow",
            "market_cap",
            "enterprise_value",
            "valuation_snapshot_date",
        ):
            assert field in row, f"{row['ticker']} missing {field}."
        # Multiples are deterministic: recomputing matches the API output.
        expected = compute_multiples(
            market_cap=row["market_cap"],
            enterprise_value=row["enterprise_value"],
            ttm_revenue=row["ttm_revenue"],
            ttm_operating_income=row["ttm_operating_income"],
            ttm_free_cash_flow=row["ttm_free_cash_flow"],
        )
        for key, value in expected.items():
            assert row[key] == value, f"{row['ticker']} {key}: {row[key]} != {value}"
        # AVGO has a valuation snapshot, so its multiples must be non-null.
        if row["ticker"] == "AVGO":
            assert row["ev_to_ttm_revenue"] is not None
            assert row["free_cash_flow_yield"] is not None
        print(
            f"  {row['ticker']}: EV/TTM-rev={row['ev_to_ttm_revenue']}, "
            f"FCF yield={row['free_cash_flow_yield']}, "
            f"snapshot={row['valuation_snapshot_date']}"
        )

    print(f"GET /peers -> 200, {body['count']} peers, dates={body['valuation_snapshot_dates']}")

    # No admin token required (public read).
    assert "X-Admin-Token" not in response.request.headers

    # --- /peers/trends -------------------------------------------------------
    trends = client.get("/peers/trends", params={"metric_name": "Revenue"})
    assert trends.status_code == 200, trends.status_code
    tbody = trends.json()
    assert tbody["metric_name"] == "Revenue"
    assert {s["ticker"] for s in tbody["series"]} == EXPECTED_TICKERS
    for s in tbody["series"]:
        # Points are chronologically ordered.
        labels = [p["period"] for p in s["points"]]
        assert labels == sorted(labels, key=lambda x: (x.split()[0], x.split()[1]))

    # limit keeps only the most recent N periods.
    limited = client.get(
        "/peers/trends", params={"metric_name": "Revenue", "ticker": "AVGO", "limit": 4}
    ).json()
    assert len(limited["series"]) == 1
    assert len(limited["series"][0]["points"]) == 4
    print(f"GET /peers/trends Revenue -> 200, {len(tbody['series'])} series; limit honored.")

    print("\nPASS: /peers and /peers/trends serve deterministic, dated peer data.")


if __name__ == "__main__":
    main()
