"""Test the GET /overview endpoint.

Read-only: no Supabase mutations, no AI calls.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app

TOTAL_FIELDS = {
    "companies_count",
    "total_filings_count",
    "extraction_ready_count",
    "pending_grounded_claim_count",
    "trusted_claim_count",
    "stored_brief_count",
    "companies",
}

ROW_FIELDS = {
    "ticker",
    "company_name",
    "extraction_ready_count",
    "trusted_claim_count",
    "latest_brief_version",
    "latest_filing_date",
}


def main() -> None:
    client = TestClient(app)

    response = client.get("/overview")
    assert response.status_code == 200, f"Got {response.status_code}."
    body = response.json()

    missing = TOTAL_FIELDS - set(body.keys())
    assert not missing, f"Response missing fields: {missing}."

    assert body["companies_count"] == 5
    assert body["companies_count"] == len(body["companies"])
    assert body["total_filings_count"] > 0
    assert body["stored_brief_count"] >= 1

    tickers = [c["ticker"] for c in body["companies"]]
    assert tickers == sorted(tickers), "Companies must be ordered by ticker."

    for row in body["companies"]:
        missing = ROW_FIELDS - set(row.keys())
        assert not missing, f"{row.get('ticker')} row missing {missing}."
        assert row["company_name"], "company_name must be populated."

    # Totals must be consistent with the per-company rows.
    assert body["extraction_ready_count"] == sum(
        c["extraction_ready_count"] for c in body["companies"]
    )
    assert body["trusted_claim_count"] == sum(
        c["trusted_claim_count"] for c in body["companies"]
    )

    avgo = next(c for c in body["companies"] if c["ticker"] == "AVGO")
    assert avgo["extraction_ready_count"] >= 1
    assert avgo["trusted_claim_count"] >= 5
    assert avgo["latest_brief_version"] >= 1
    assert avgo["latest_filing_date"], "AVGO must have a latest filing date."

    print(
        f"GET /overview -> 200: {body['companies_count']} companies, "
        f"{body['total_filings_count']} filings, "
        f"{body['extraction_ready_count']} extraction-ready, "
        f"{body['trusted_claim_count']} trusted, "
        f"{body['stored_brief_count']} briefs"
    )
    print()
    print(
        "PASS: overview endpoint returns consistent cross-company totals "
        "and per-company status rows."
    )


if __name__ == "__main__":
    main()
