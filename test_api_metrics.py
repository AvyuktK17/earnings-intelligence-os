"""Test the GET /metrics/{ticker} endpoint.

Read-only against live Supabase: no mutations, no AI calls. Verifies that the
audited operating-metric series is served for all five companies (including
AVGO after the static-dashboard backfill), that valuation-derived rows are
excluded, and that an unknown ticker returns 404.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app
from src.quantitative import PEER_METRIC_FIELDS
from src.static_dashboard_backfill import VALUATION_METRIC_NAMES

TICKERS = ["AMD", "AVGO", "INTC", "NVDA", "QCOM"]


def main() -> None:
    client = TestClient(app)

    for ticker in TICKERS:
        response = client.get(f"/metrics/{ticker}")
        assert response.status_code == 200, (
            f"Expected 200 from /metrics/{ticker}, got {response.status_code}."
        )
        body = response.json()
        assert body["ticker"] == ticker
        assert body["metric_count"] > 0, f"{ticker} has no metrics."
        assert body["period_count"] > 0, f"{ticker} has no periods."
        # Valuation-derived metrics must never appear in the operating series.
        leaked = set(body["metrics"]) & set(VALUATION_METRIC_NAMES)
        assert not leaked, f"{ticker} leaked valuation metrics: {leaked}"
        # Each series point carries a value and a sortable period.
        for points in body["metrics"].values():
            for point in points:
                assert "period" in point and "value" in point
        print(
            f"GET /metrics/{ticker} -> 200, metrics={body['metric_count']}, "
            f"periods={body['period_count']}, latest={body['latest_period']}"
        )

    # AVGO specifically must exist with the full operating metric set.
    avgo = client.get("/metrics/AVGO").json()
    assert "Revenue" in avgo["metrics"], "AVGO Revenue series missing after backfill."
    assert avgo["metric_count"] == len(PEER_METRIC_FIELDS) or avgo["metric_count"] >= 21
    assert avgo["latest_period_summary"].get("Revenue") is not None
    print(f"AVGO operating series present: {avgo['metric_count']} metrics.")

    # Lowercase ticker is normalized.
    assert client.get("/metrics/avgo").json()["ticker"] == "AVGO"

    # metric_name filter narrows to one series.
    filtered = client.get("/metrics/NVDA", params={"metric_name": "Revenue"}).json()
    assert set(filtered["metrics"]) == {"Revenue"}, filtered["metrics"].keys()
    print("metric_name filter returns a single series.")

    # Unknown ticker -> 404.
    assert client.get("/metrics/ZZZZ").status_code == 404
    print("Unknown ticker -> 404.")

    print("\nPASS: /metrics serves audited operating series for all five companies.")


if __name__ == "__main__":
    main()
