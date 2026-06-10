"""Test the /briefs/latest/{ticker} endpoint.

Uses FastAPI TestClient against live Supabase data. Read-only: no AI calls,
no row mutations. Version-agnostic: analysts generate new brief versions in
production, so the test asserts the endpoint returns the *latest* stored
version rather than pinning exact version numbers.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app
from src.database import get_supabase_client

TICKER_WITH_BRIEF = "AVGO"
TICKER_WITHOUT_BRIEF = "ZZZZ"  # never on the watchlist, never has briefs


def main() -> None:
    client = TestClient(app)
    supabase = get_supabase_client()

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
    assert brief["version_number"] >= 1
    assert brief["trusted_claim_count"] >= 1
    assert brief["markdown_content"], "markdown_content must not be empty."
    assert brief["storage_path"], "storage_path must not be empty."

    # The endpoint must return the most recently generated stored brief.
    newest = (
        supabase.table("earnings_briefs")
        .select("id, generated_at")
        .eq("ticker", TICKER_WITH_BRIEF)
        .order("generated_at", desc=True)
        .limit(1)
        .execute()
        .data[0]
    )
    assert brief["id"] == newest["id"], (
        f"Endpoint returned brief id={brief['id']}, but the newest stored "
        f"brief is id={newest['id']}."
    )
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
        "PASS: latest-brief endpoint returns the most recent stored brief "
        "and 404s for tickers without a persisted brief."
    )


if __name__ == "__main__":
    main()
