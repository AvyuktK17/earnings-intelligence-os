"""
Test the end-to-end filing processor including Supabase Storage upload,
using the most recent Qualcomm 10-Q. Verifies both local files and Storage paths
are recorded in Supabase. Does NOT delete rows or make the bucket public.
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

    result = process_filing(filing)

    # Verify returned result
    assert result["status"] == "parsed", (
        f"Expected status 'parsed' but got {result['status']!r}."
    )
    assert os.path.exists(result["html_path"]), (
        f"Local HTML file not found: {result['html_path']}"
    )
    assert os.path.exists(result["text_path"]), (
        f"Local text file not found: {result['text_path']}"
    )
    assert result["html_storage_path"], "html_storage_path is empty in result."
    assert result["text_storage_path"], "text_storage_path is empty in result."

    # Confirm Supabase row has the storage paths
    db_response = (
        supabase.table("filings")
        .select("processing_status, html_storage_path, text_storage_path")
        .eq("accession_number", filing["accession_number"])
        .execute()
    )
    assert db_response.data, "Filing row not found in Supabase."
    row = db_response.data[0]

    assert row["html_storage_path"] == result["html_storage_path"], (
        "html_storage_path in Supabase does not match the returned result."
    )
    assert row["text_storage_path"] == result["text_storage_path"], (
        "text_storage_path in Supabase does not match the returned result."
    )

    print(f"  Ticker             : {result['ticker']}")
    print(f"  Accession number   : {result['accession_number']}")
    print(f"  Final status       : {result['status']}")
    print(f"  HTML Storage path  : {result['html_storage_path']}")
    print(f"  Text Storage path  : {result['text_storage_path']}")
    print(f"  Supabase confirmed : html_storage_path = {row['html_storage_path']}")
    print(f"  Supabase confirmed : text_storage_path = {row['text_storage_path']}")
    print()
    print("PASS: end-to-end filing processor with storage is working correctly.")


if __name__ == "__main__":
    main()
