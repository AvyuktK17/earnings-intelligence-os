"""Test the GET /extraction-ready endpoint.

Read-only: no Supabase mutations, no AI calls. Expects the AVGO 8-K exhibit
to be ingested (run test_process_pending_exhibits.py first if it is not).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app

AVGO_ACCESSION = "0001730168-26-000051"

EXPECTED_FIELDS = {
    "filing_id",
    "ticker",
    "accession_number",
    "form",
    "filing_date",
    "exhibit_processing_status",
    "earnings_release_document_id",
    "filename",
    "document_key",
    "chunk_count",
    "ready_for_extraction",
}


def main() -> None:
    client = TestClient(app)

    response = client.get("/extraction-ready")
    assert response.status_code == 200, (
        f"Expected 200 from /extraction-ready, got {response.status_code}."
    )
    body = response.json()

    assert body["count"] == len(body["filings"])
    assert body["count"] >= 1, "Expected at least the AVGO filing."

    dates = [f["filing_date"] for f in body["filings"]]
    assert dates == sorted(dates, reverse=True), (
        f"Filings are not ordered by filing_date descending: {dates}."
    )

    avgo_rows = [
        f for f in body["filings"] if f["accession_number"] == AVGO_ACCESSION
    ]
    assert avgo_rows, f"AVGO accession {AVGO_ACCESSION} missing from response."
    avgo = avgo_rows[0]

    missing = EXPECTED_FIELDS - set(avgo.keys())
    assert not missing, f"AVGO row missing fields: {missing}."
    assert avgo["ticker"] == "AVGO"
    assert avgo["form"] == "8-K"
    assert avgo["exhibit_processing_status"] == "processed"
    assert isinstance(avgo["earnings_release_document_id"], int)
    assert avgo["filename"], "Exhibit filename must be populated."
    assert avgo["document_key"] == f"exhibit:{avgo['filename']}"
    assert avgo["chunk_count"] > 0, "Expected a positive exhibit chunk count."
    assert avgo["ready_for_extraction"] is True

    print(
        f"GET /extraction-ready -> 200, count={body['count']}, AVGO "
        f"document_id={avgo['earnings_release_document_id']}, "
        f"chunks={avgo['chunk_count']}"
    )
    print()
    print(
        "PASS: /extraction-ready lists processed exhibits newest-first and "
        "the AVGO filing is extraction-ready."
    )


if __name__ == "__main__":
    main()
