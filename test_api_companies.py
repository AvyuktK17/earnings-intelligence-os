"""Test the GET /companies endpoint.

Read-only: no Supabase mutations, no AI calls.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app

EXPECTED_TICKERS = ["AMD", "AVGO", "INTC", "NVDA", "QCOM"]
EXPECTED_FIELDS = {"ticker", "company_name", "cik", "business_model"}


def main() -> None:
    client = TestClient(app)

    response = client.get("/companies")
    assert response.status_code == 200, (
        f"Expected 200 from /companies, got {response.status_code}."
    )
    body = response.json()

    assert body["count"] == 5, f"Expected 5 companies, got {body['count']}."
    assert body["count"] == len(body["companies"])

    tickers = [c["ticker"] for c in body["companies"]]
    assert tickers == EXPECTED_TICKERS, (
        f"Expected tickers in ascending order {EXPECTED_TICKERS}, got {tickers}."
    )

    for company in body["companies"]:
        missing = EXPECTED_FIELDS - set(company.keys())
        assert not missing, f"Company {company['ticker']} missing {missing}."
        assert company["company_name"], "company_name must be populated."
    print(f"GET /companies -> 200, count={body['count']}, tickers={tickers}")

    print()
    print(
        "PASS: /companies returns the five monitored companies in ticker "
        "order with the expected fields."
    )


if __name__ == "__main__":
    main()
