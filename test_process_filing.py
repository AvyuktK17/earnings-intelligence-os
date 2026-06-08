"""
Test the unified filing processor using the latest Qualcomm 10-Q in Supabase.
Verifies the HTML and text files are created and the Supabase row is updated.
Does NOT delete rows or commit downloaded/parsed files.
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

    print(f"Processing filing: {filing['accession_number']}")
    result = process_filing(filing)

    print()
    print("Result:")
    for key, value in result.items():
        print(f"  {key}: {value}")

    # Verify returned result
    assert result["status"] == "parsed", (
        f"Expected status 'parsed' but got {result['status']!r}."
    )
    assert os.path.exists(result["html_path"]), (
        f"HTML file not found: {result['html_path']}"
    )
    assert os.path.exists(result["text_path"]), (
        f"Text file not found: {result['text_path']}"
    )
    assert result["html_size_bytes"] > 0, "HTML file is empty."

    with open(result["text_path"], "r", encoding="utf-8") as f:
        text_content = f.read()
    assert len(text_content) >= 10_000, (
        f"Expected at least 10,000 characters but got {len(text_content)}."
    )

    # Confirm Supabase row was updated
    db_row = (
        supabase.table("filings")
        .select("processing_status, downloaded_at, parsed_at")
        .eq("accession_number", filing["accession_number"])
        .execute()
    )
    assert db_row.data, "Filing row not found in Supabase."
    row = db_row.data[0]
    assert row["processing_status"] == "parsed", (
        f"Supabase processing_status should be 'parsed' but got {row['processing_status']!r}."
    )

    print()
    print(f"Supabase status  : {row['processing_status']}")
    print(f"Downloaded at    : {row['downloaded_at']}")
    print(f"Parsed at        : {row['parsed_at']}")
    print()
    print("PASS: process_filing is working correctly.")


if __name__ == "__main__":
    main()
