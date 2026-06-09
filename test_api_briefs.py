"""Test the /briefs/latest/{ticker} endpoint.

Uses FastAPI TestClient against live Supabase data. Read-only: no AI calls,
no row mutations.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app

TICKER_WITH_BRIEF = "AVGO"
TICKER_WITHOUT_BRIEF = "NVDA"
AVGO_ACCESSION = "0001730168-26-000051"


def main() -> None:
    client = TestClient(app)

    # --- Latest AVGO brief ---
    response = client.get(f"/briefs/latest/{TICKER_WITH_BRIEF}")
    assert response.status_code == 200, (
        f"Expected 200 from /briefs/latest/{TICKER_WITH_BRIEF}, "
        f"got {response.status_code}."
    )
    brief = response.json()

    assert brief["ticker"] == TICKER_WITH_BRIEF, (
        f"Expected ticker={TICKER_WITH_BRIEF!r}, got {brief['ticker']!r}."
    )
    assert brief["accession_number"] == AVGO_ACCESSION, (
        f"Expected accession_number={AVGO_ACCESSION!r}, "
        f"got {brief['accession_number']!r}."
    )
    assert brief["version_number"] == 1, (
        f"Expected version_number=1, got {brief['version_number']}."
    )
    assert brief["trusted_claim_count"] == 5, (
        f"Expected trusted_claim_count=5, got {brief['trusted_claim_count']}."
    )
    assert brief["markdown_content"], "markdown_content must not be empty."
    assert brief["storage_path"], "storage_path must not be empty."
    print(
        f"GET /briefs/latest/{TICKER_WITH_BRIEF} -> 200, "
        f"version={brief['version_number']}, "
        f"trusted={brief['trusted_claim_count']}, "
        f"storage_path={brief['storage_path']}"
    )

    # --- Ticker with no stored brief ---
    response = client.get(f"/briefs/latest/{TICKER_WITHOUT_BRIEF}")
    assert response.status_code == 404, (
        f"Expected 404 for ticker without a brief, got {response.status_code}."
    )
    print(f"GET /briefs/latest/{TICKER_WITHOUT_BRIEF} -> 404")

    print()
    print(
        "PASS: latest-brief endpoint returns the stored AVGO v1 brief with the "
        "expected claim counts and 404s for tickers without a persisted brief."
    )


if __name__ == "__main__":
    main()
