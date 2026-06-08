"""
Test failure tracking by inserting a temporary TEST filing with an invalid URL,
running process_detected_filings, and verifying the failure is recorded.
Cleans up the TEST row at the end.
Does NOT process real filings or modify .env.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.filing_status import mark_filing_failed
from src.process_detected_filings import process_detected_filings

TEST_ACCESSION = "test-failure-000001"
TEST_TICKER = "TEST"


def insert_test_row(supabase) -> None:
    supabase.table("filings").insert(
        {
            "ticker": TEST_TICKER,
            "accession_number": TEST_ACCESSION,
            "form": "8-K",
            "sec_url": "https://example.invalid/filing.html",
            "processing_status": "detected",
        }
    ).execute()


def delete_test_row(supabase) -> None:
    supabase.table("filings").delete().eq(
        "accession_number", TEST_ACCESSION
    ).execute()


def main():
    supabase = get_supabase_client()

    # Insert the temporary test row
    print(f"Inserting temporary TEST row ({TEST_ACCESSION})...")
    insert_test_row(supabase)

    try:
        # process_detected_filings picks the most recent detected filing.
        # To ensure our test row is processed rather than a real filing,
        # call mark_filing_failed directly as a targeted unit test, then
        # verify the round-trip through process_filing via process_detected_filings
        # by temporarily setting a far-future filing_date on the test row so it
        # sorts first. Simpler approach: call process_filing on the test row directly.

        # Direct approach: call mark_filing_failed and verify Supabase update,
        # then also verify process_detected_filings records failures end-to-end.

        # --- Part 1: verify mark_filing_failed writes to Supabase ---
        error_msg = "Simulated download failure: connection refused"
        updated_row = mark_filing_failed(TEST_ACCESSION, error_msg)

        assert updated_row["processing_status"] == "failed", (
            f"Expected 'failed' but got {updated_row['processing_status']!r}."
        )
        assert updated_row["processing_error"] == error_msg, (
            "processing_error was not stored correctly."
        )
        print(f"mark_filing_failed verified:")
        print(f"  processing_status : {updated_row['processing_status']}")
        print(f"  processing_error  : {updated_row['processing_error']}")

        # Reset the test row to 'detected' so process_detected_filings can pick it up
        supabase.table("filings").update(
            {"processing_status": "detected", "processing_error": None}
        ).eq("accession_number", TEST_ACCESSION).execute()

        # --- Part 2: verify process_detected_filings calls mark_filing_failed ---
        # Temporarily set filing_date far in the future so the test row sorts first
        supabase.table("filings").update(
            {"filing_date": "2099-01-01"}
        ).eq("accession_number", TEST_ACCESSION).execute()

        print(f"\nRunning process_detected_filings(limit=1) with TEST row at top...")
        results = process_detected_filings(limit=1)

        assert len(results) == 1, f"Expected 1 result but got {len(results)}."
        result = results[0]

        print(f"Result:")
        print(f"  ticker            : {result['ticker']}")
        print(f"  accession_number  : {result['accession_number']}")
        print(f"  status            : {result['status']}")
        print(f"  error_message     : {result.get('error_message', '')}")

        assert result["accession_number"] == TEST_ACCESSION, (
            f"Expected test row to be processed but got {result['accession_number']!r}."
        )
        assert result["status"] == "failed", (
            f"Expected status 'failed' but got {result['status']!r}."
        )
        assert result.get("error_message"), "error_message should not be empty."

        # Confirm Supabase row reflects the failure
        db_response = (
            supabase.table("filings")
            .select("processing_status, processing_error")
            .eq("accession_number", TEST_ACCESSION)
            .execute()
        )
        row = db_response.data[0]
        assert row["processing_status"] == "failed", (
            f"Supabase row should be 'failed' but got {row['processing_status']!r}."
        )
        assert row["processing_error"], "processing_error should be populated in Supabase."

        print(f"\nSupabase row confirmed:")
        print(f"  processing_status : {row['processing_status']}")
        print(f"  processing_error  : {row['processing_error']}")

    finally:
        # Always clean up the test row
        delete_test_row(supabase)
        confirm = (
            supabase.table("filings")
            .select("id")
            .eq("accession_number", TEST_ACCESSION)
            .execute()
        )
        deleted = len(confirm.data) == 0
        print(f"\nTEST row deleted: {deleted}")

    print()
    print("PASS: failure tracking is working correctly.")


if __name__ == "__main__":
    main()
