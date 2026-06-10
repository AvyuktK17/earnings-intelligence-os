"""Test the GET /companies/{ticker} endpoint.

Read-only: no Supabase mutations, no AI calls.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app

TOP_LEVEL_FIELDS = {
    "company",
    "filings_count",
    "chunked_filings_count",
    "extraction_ready_count",
    "trusted_claim_count",
    "latest_brief",
    "recent_filings",
    "extraction_ready",
}


def main() -> None:
    client = TestClient(app)

    # AVGO has a full workflow: filings, exhibits, trusted claims, briefs.
    response = client.get("/companies/AVGO")
    assert response.status_code == 200, f"Got {response.status_code}."
    body = response.json()

    missing = TOP_LEVEL_FIELDS - set(body.keys())
    assert not missing, f"Response missing fields: {missing}."

    company = body["company"]
    assert company["ticker"] == "AVGO"
    assert company["company_name"], "company_name must be populated."
    assert company["cik"], "cik must be populated."

    assert body["filings_count"] > 0
    assert body["chunked_filings_count"] > 0
    assert body["extraction_ready_count"] == len(body["extraction_ready"])
    assert body["extraction_ready_count"] >= 1
    assert body["trusted_claim_count"] >= 5, (
        "AVGO should have at least its 5 promoted trusted claims."
    )

    brief = body["latest_brief"]
    assert brief is not None, "AVGO should have a stored brief."
    assert brief["ticker"] == "AVGO"
    assert brief["version_number"] >= 1
    assert "markdown_content" not in brief, (
        "Company payload should carry brief metadata only, not the body."
    )

    assert len(body["recent_filings"]) <= 10
    assert all(f["ticker"] == "AVGO" for f in body["recent_filings"])
    dates = [f["filing_date"] for f in body["recent_filings"]]
    assert dates == sorted(dates, reverse=True)

    for row in body["extraction_ready"]:
        for field in (
            "accession_number",
            "form",
            "filing_date",
            "filename",
            "document_key",
            "chunk_count",
            "claim_extraction_status",
        ):
            assert field in row, f"extraction_ready row missing {field}."
    print(
        f"GET /companies/AVGO -> 200: {body['filings_count']} filings, "
        f"{body['extraction_ready_count']} extraction-ready, "
        f"{body['trusted_claim_count']} trusted, brief v{brief['version_number']}"
    )

    # Lowercase tickers normalize.
    response = client.get("/companies/avgo")
    assert response.status_code == 200
    assert response.json()["company"]["ticker"] == "AVGO"
    print("Lowercase ticker normalized to uppercase.")

    # Unknown ticker -> 404.
    response = client.get("/companies/ZZZZ")
    assert response.status_code == 404, f"Got {response.status_code}."
    print("Unknown ticker -> 404.")

    print()
    print(
        "PASS: company-detail endpoint returns the pipeline summary, "
        "normalizes tickers, and 404s for unknown companies."
    )


if __name__ == "__main__":
    main()
