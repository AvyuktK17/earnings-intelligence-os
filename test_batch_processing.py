"""
Test batch processing of 3 detected filings including Storage uploads.
Verifies each result and matching Supabase row is fully updated.
Does NOT delete rows, make the bucket public, or commit filing contents.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.process_detected_filings import process_detected_filings

BATCH_SIZE = 3


def count_detected(supabase) -> int:
    response = (
        supabase.table("filings")
        .select("id", count="exact")
        .eq("processing_status", "detected")
        .execute()
    )
    return response.count


def main():
    supabase = get_supabase_client()

    detected_before = count_detected(supabase)
    print(f"Detected filings before processing: {detected_before}")
    assert detected_before >= BATCH_SIZE, (
        f"Need at least {BATCH_SIZE} detected filings but only found {detected_before}. "
        "Run python run_monitor.py to sync new filings first."
    )

    print(f"\nProcessing {BATCH_SIZE} detected filings...\n")
    results = process_detected_filings(limit=BATCH_SIZE)

    assert len(results) == BATCH_SIZE, (
        f"Expected {BATCH_SIZE} results but got {len(results)}."
    )

    col = "{:<6} {:<28} {:<8} {:<42} {:<42}"
    header = col.format("Ticker", "Accession Number", "Status", "HTML Storage Path", "Text Storage Path")
    print(header)
    print("-" * len(header))

    for r in results:
        print(col.format(
            r["ticker"],
            r["accession_number"],
            r["status"],
            r.get("html_storage_path", ""),
            r.get("text_storage_path", ""),
        ))

        assert r["status"] == "parsed", (
            f"{r['accession_number']}: expected status 'parsed' but got {r['status']!r}. "
            f"Error: {r.get('error_message', 'n/a')}"
        )
        assert r.get("html_storage_path"), (
            f"{r['accession_number']}: html_storage_path is missing from result."
        )
        assert r.get("text_storage_path"), (
            f"{r['accession_number']}: text_storage_path is missing from result."
        )

        # Confirm Supabase row is fully updated
        db_response = (
            supabase.table("filings")
            .select("processing_status, downloaded_at, parsed_at, html_storage_path, text_storage_path")
            .eq("accession_number", r["accession_number"])
            .execute()
        )
        assert db_response.data, f"Row not found in Supabase for {r['accession_number']}."
        row = db_response.data[0]

        assert row["processing_status"] == "parsed", (
            f"{r['accession_number']}: Supabase processing_status should be 'parsed'."
        )
        assert row["downloaded_at"], f"{r['accession_number']}: downloaded_at not populated."
        assert row["parsed_at"], f"{r['accession_number']}: parsed_at not populated."
        assert row["html_storage_path"], f"{r['accession_number']}: html_storage_path not in Supabase."
        assert row["text_storage_path"], f"{r['accession_number']}: text_storage_path not in Supabase."

    detected_after = count_detected(supabase)

    print()
    print(f"Detected before : {detected_before}")
    print(f"Detected after  : {detected_after}")
    print()
    print("PASS: batch processing with Storage uploads is working correctly.")


if __name__ == "__main__":
    main()
