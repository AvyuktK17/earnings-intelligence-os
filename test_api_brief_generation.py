"""Test the POST /briefs/generate endpoint.

Generates a new versioned AVGO brief via the API, verifies the new row and
that the prior persisted version is untouched, exercises the 404 and 400
error paths, then deletes only the temporary earnings_briefs row created by
this test. Storage objects are left in place (no delete support in
src.storage). No AI calls. Trusted claims are not modified.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app
from src.database import get_supabase_client

TICKER = "AVGO"
ACCESSION = "0001730168-26-000051"
INVALID_ACCESSION = "0000000000-00-000000"


def main() -> None:
    client = TestClient(app)
    supabase = get_supabase_client()

    # Snapshot existing brief rows for this accession.
    before = (
        supabase.table("earnings_briefs")
        .select("id, version_number, storage_path")
        .eq("accession_number", ACCESSION)
        .order("version_number")
        .execute()
        .data
    )
    before_ids = {r["id"] for r in before}
    base_version = before[-1]["version_number"] if before else 0
    print(f"Existing brief versions before test: "
          f"{[r['version_number'] for r in before]}")

    temp_brief_id = None
    try:
        # --- Generate a new versioned brief ---
        response = client.post(
            "/briefs/generate",
            json={"ticker": "avgo", "accession_number": ACCESSION},
        )
        assert response.status_code == 200, (
            f"Expected 200 from /briefs/generate, got {response.status_code}: "
            f"{response.text}"
        )
        body = response.json()
        assert body["ticker"] == TICKER, (
            f"Lowercase input must be uppercased, got {body['ticker']!r}."
        )
        assert body["version_number"] == base_version + 1, (
            f"Expected version {base_version + 1}, got {body['version_number']}."
        )
        assert body["trusted_claim_count"] == 5, (
            f"Expected trusted_claim_count=5, got {body['trusted_claim_count']}."
        )
        assert body["storage_path"], "storage_path must be populated."
        print(f"POST /briefs/generate -> 200: version={body['version_number']}, "
              f"trusted={body['trusted_claim_count']}, "
              f"storage_path={body['storage_path']}")

        # --- New DB row inserted ---
        new_rows = (
            supabase.table("earnings_briefs")
            .select("id, version_number, storage_path, markdown_content")
            .eq("accession_number", ACCESSION)
            .eq("version_number", body["version_number"])
            .execute()
            .data
        )
        assert len(new_rows) == 1, f"Expected 1 new brief row, found {len(new_rows)}."
        temp_brief_id = new_rows[0]["id"]
        assert new_rows[0]["markdown_content"], "markdown_content must not be empty."
        print(f"  [OK] new earnings_briefs row id={temp_brief_id} inserted")

        # --- Prior persisted versions untouched ---
        after = (
            supabase.table("earnings_briefs")
            .select("id, version_number, storage_path")
            .eq("accession_number", ACCESSION)
            .in_("id", list(before_ids))
            .order("version_number")
            .execute()
            .data
        )
        assert after == before, "Prior persisted brief rows changed during the test."
        print(f"  [OK] prior version rows unchanged: "
              f"{[r['version_number'] for r in after]}")

        # --- Unknown filing -> 404 ---
        response = client.post(
            "/briefs/generate",
            json={"ticker": TICKER, "accession_number": INVALID_ACCESSION},
        )
        assert response.status_code == 404, (
            f"Expected 404 for unknown filing, got {response.status_code}."
        )
        print(f"POST /briefs/generate (unknown accession) -> 404")

        # --- Filing exists but no trusted claims -> 400 ---
        nvda_accession = (
            supabase.table("filings")
            .select("accession_number")
            .eq("ticker", "NVDA")
            .limit(1)
            .execute()
            .data[0]["accession_number"]
        )
        response = client.post(
            "/briefs/generate",
            json={"ticker": "NVDA", "accession_number": nvda_accession},
        )
        assert response.status_code == 400, (
            f"Expected 400 when no trusted claims exist, got {response.status_code}."
        )
        print(f"POST /briefs/generate (NVDA, no trusted claims) -> 400")

        # --- Missing body field -> 422 ---
        response = client.post("/briefs/generate", json={"ticker": TICKER})
        assert response.status_code == 422, (
            f"Expected 422 for missing accession_number, got {response.status_code}."
        )
        print("POST /briefs/generate (missing field) -> 422")

    finally:
        if temp_brief_id is not None:
            supabase.table("earnings_briefs").delete().eq(
                "id", temp_brief_id
            ).execute()
            remaining = (
                supabase.table("earnings_briefs")
                .select("id")
                .eq("id", temp_brief_id)
                .execute()
                .data
            )
            assert not remaining, f"Temp brief row {temp_brief_id} not deleted."
            print(f"\nCleaned up temp earnings_briefs row {temp_brief_id}. "
                  "Storage object left in place.")

    print()
    print(
        "PASS: brief-generation endpoint stores a new version, preserves prior "
        "versions, and maps missing filings to 404 and missing claims to 400."
    )


if __name__ == "__main__":
    main()
