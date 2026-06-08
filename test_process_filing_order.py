"""
Verify that process_filing() only marks a filing as 'parsed' after both
Storage uploads and Storage path recording succeed.
Uses the latest Qualcomm 10-Q (safe to reprocess; upsert keeps it idempotent).
Does NOT delete rows or make the bucket public.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.process_filing import process_filing


def main():
    supabase = get_supabase_client()

    # Fetch the most recent Qualcomm 10-Q
    response = (
        supabase.table("filings")
        .select("ticker, accession_number, sec_url, filing_date")
        .eq("ticker", "QCOM")
        .eq("form", "10-Q")
        .order("filing_date", desc=True)
        .limit(1)
        .execute()
    )

    assert response.data, "No QCOM 10-Q filings found in Supabase."
    filing = response.data[0]
    print(f"Processing: {filing['accession_number']}")

    process_filing(filing)

    # Query Supabase to verify the final state
    db_response = (
        supabase.table("filings")
        .select("processing_status, downloaded_at, parsed_at, html_storage_path, text_storage_path")
        .eq("accession_number", filing["accession_number"])
        .execute()
    )
    assert db_response.data, "Filing row not found in Supabase after processing."
    row = db_response.data[0]

    print(f"  processing_status  : {row['processing_status']}")
    print(f"  downloaded_at      : {row['downloaded_at']}")
    print(f"  parsed_at          : {row['parsed_at']}")
    print(f"  html_storage_path  : {row['html_storage_path']}")
    print(f"  text_storage_path  : {row['text_storage_path']}")

    assert row["processing_status"] == "parsed", (
        f"Expected 'parsed' but got {row['processing_status']!r}."
    )
    assert row["html_storage_path"], "html_storage_path is not populated."
    assert row["text_storage_path"], "text_storage_path is not populated."
    assert row["downloaded_at"], "downloaded_at is not populated."
    assert row["parsed_at"], "parsed_at is not populated."

    print()
    print("PASS: processing order is correct — 'parsed' is only set after Storage uploads succeed.")


if __name__ == "__main__":
    main()
