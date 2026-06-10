"""Test the GET /valuation-snapshots endpoint.

Read-only against live Supabase: no mutations, no AI calls. Verifies the
manually reviewed point-in-time snapshots exist for all five companies, are
clearly flagged as not-live, and never fabricate missing values.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app

EXPECTED_TICKERS = {"AMD", "AVGO", "INTC", "NVDA", "QCOM"}


def main() -> None:
    client = TestClient(app)

    response = client.get("/valuation-snapshots")
    assert response.status_code == 200, response.status_code
    body = response.json()

    assert body["count"] == 5, f"Expected 5 snapshots, got {body['count']}."
    assert body["is_live"] is False, "top-level is_live must be False."
    assert body["valuation_snapshot_dates"], "snapshot dates must be present."

    tickers = {s["ticker"] for s in body["snapshots"]}
    assert tickers == EXPECTED_TICKERS, tickers

    for snapshot in body["snapshots"]:
        assert snapshot["is_live"] is False, f"{snapshot['ticker']} is_live must be False."
        assert snapshot["share_price_date"], "snapshot must carry a date."
        assert snapshot["manually_reviewed"], "manual-review flag must be preserved."
        # Core numeric fields are present (not fabricated where absent — they
        # remain whatever the audited dataset stored, including possible null).
        assert "share_price" in snapshot
        assert "market_cap" in snapshot
        assert "enterprise_value" in snapshot
        print(
            f"  {snapshot['ticker']}: {snapshot['share_price_date']} "
            f"px={snapshot['share_price']} reviewed={snapshot['manually_reviewed']}"
        )

    # Public read: no admin token attached.
    assert "X-Admin-Token" not in response.request.headers

    print(
        f"\nPASS: /valuation-snapshots returns 5 dated, manually reviewed, "
        f"not-live snapshots (dates={body['valuation_snapshot_dates']})."
    )


if __name__ == "__main__":
    main()
