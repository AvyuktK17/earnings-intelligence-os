"""Tests for the filing-level claim-extraction status helpers.

Uses a temporary filing row only; no AI calls, no real filings touched.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.claim_extraction_status import (
    mark_claim_extraction_approved,
    mark_claim_extraction_failed,
    mark_claim_extraction_pending_review,
)
from src.database import get_supabase_client

TEMP_ACCESSION = "0000000000-99-000888"


def main() -> None:
    supabase = get_supabase_client()

    try:
        inserted = (
            supabase.table("filings")
            .insert(
                {
                    "ticker": "ZZZT",
                    "accession_number": TEMP_ACCESSION,
                    "form": "8-K",
                    "filing_date": "2000-01-01",
                    "processing_status": "chunked",
                    "sec_url": "https://example.invalid/temp-status-test",
                }
            )
            .execute()
            .data[0]
        )
        assert inserted["claim_extraction_status"] == "not_started", (
            "New filings must default to 'not_started'."
        )
        assert inserted["claim_extracted_at"] is None
        assert inserted["claim_extraction_error"] is None
        print("Default state: not_started with empty timestamp and error.")

        row = mark_claim_extraction_pending_review(TEMP_ACCESSION)
        assert row["claim_extraction_status"] == "pending_review"
        assert row["claim_extracted_at"] is not None
        assert row["claim_extraction_error"] is None
        extracted_at = row["claim_extracted_at"]
        print("pending_review: status set, timestamp recorded, error cleared.")

        row = mark_claim_extraction_failed(TEMP_ACCESSION, "synthetic status error")
        assert row["claim_extraction_status"] == "failed"
        assert row["claim_extracted_at"] is not None
        assert row["claim_extraction_error"] == "synthetic status error"
        print("failed: status, timestamp, and error message recorded.")

        row = mark_claim_extraction_approved(TEMP_ACCESSION)
        assert row["claim_extraction_status"] == "approved"
        assert row["claim_extraction_error"] is None
        assert row["claim_extracted_at"] is not None, (
            "approved must not erase the extraction timestamp."
        )
        del extracted_at
        print("approved: status set and error cleared; timestamp preserved.")

        try:
            mark_claim_extraction_approved("0000000000-00-000000")
            raise AssertionError("Expected ValueError for a missing filing.")
        except ValueError as exc:
            assert "No filing found" in str(exc)
        print("Missing filing raises ValueError.")

    finally:
        supabase.table("filings").delete().eq(
            "accession_number", TEMP_ACCESSION
        ).execute()
        leftovers = (
            supabase.table("filings")
            .select("id")
            .eq("accession_number", TEMP_ACCESSION)
            .execute()
            .data
        )
        assert not leftovers, "Temporary filing row was not cleaned up."

    print()
    print("PASS: claim-extraction status helpers update and return filing rows correctly.")


if __name__ == "__main__":
    main()
