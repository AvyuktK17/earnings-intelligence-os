"""Test the /filings feed and /filings/{accession_number} detail endpoints.

Uses FastAPI TestClient against live Supabase data. Read-only: no AI calls,
no row mutations.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app

AVGO_ACCESSION = "0001730168-26-000051"
INVALID_ACCESSION = "0000000000-00-000000"


def main() -> None:
    client = TestClient(app)

    # --- Feed: default ---
    response = client.get("/filings")
    assert response.status_code == 200, (
        f"Expected 200 from /filings, got {response.status_code}."
    )
    body = response.json()
    assert body["count"] >= 1, "Expected at least one filing in the feed."
    assert body["count"] == len(body["filings"]), "count must match filings length."
    print(f"GET /filings -> 200, count={body['count']}")

    # --- Feed: respects limit ---
    response = client.get("/filings?limit=3")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] <= 3, f"limit=3 violated: got {body['count']} filings."
    print(f"GET /filings?limit=3 -> 200, count={body['count']}")

    # --- Feed: ticker filter ---
    response = client.get("/filings?ticker=AVGO")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1, "Expected at least one AVGO filing."
    for filing in body["filings"]:
        assert filing["ticker"] == "AVGO", (
            f"Non-AVGO filing leaked into ticker filter: {filing['ticker']!r}."
        )
    print(f"GET /filings?ticker=AVGO -> 200, count={body['count']}, all AVGO")

    # --- Feed: status filter ---
    response = client.get("/filings?status=chunked")
    assert response.status_code == 200
    body = response.json()
    for filing in body["filings"]:
        assert filing["processing_status"] == "chunked", (
            f"Non-chunked filing leaked into status filter: "
            f"{filing['processing_status']!r}."
        )
    print(f"GET /filings?status=chunked -> 200, count={body['count']}, all chunked")

    # --- Detail: AVGO filing ---
    response = client.get(f"/filings/{AVGO_ACCESSION}")
    assert response.status_code == 200, (
        f"Expected 200 from /filings/{AVGO_ACCESSION}, got {response.status_code}."
    )
    body = response.json()
    assert body["filing"]["accession_number"] == AVGO_ACCESSION
    assert body["filing"]["ticker"] == "AVGO"
    assert len(body["documents"]) >= 1, "Expected at least one filing document."
    assert body["chunk_count"] > 0, "Expected a positive chunk count."
    print(
        f"GET /filings/{AVGO_ACCESSION} -> 200, "
        f"documents={len(body['documents'])}, chunk_count={body['chunk_count']}"
    )

    # --- Detail: invalid accession number ---
    response = client.get(f"/filings/{INVALID_ACCESSION}")
    assert response.status_code == 404, (
        f"Expected 404 for invalid accession, got {response.status_code}."
    )
    print(f"GET /filings/{INVALID_ACCESSION} -> 404")

    print()
    print(
        "PASS: filings feed filters by ticker and status, respects limit, "
        "and the detail endpoint returns documents, chunk count, and 404s correctly."
    )


if __name__ == "__main__":
    main()
