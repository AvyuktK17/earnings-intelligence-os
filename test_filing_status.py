"""
Test filing status updates using the latest Qualcomm 10-Q stored in Supabase.
Marks the filing as downloaded, then as parsed, and verifies both updates.
Does NOT delete any rows or modify downloaded files.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.filing_status import mark_filing_downloaded, mark_filing_parsed


def main():
    supabase = get_supabase_client()

    # Fetch the most recent Qualcomm 10-Q
    response = (
        supabase.table("filings")
        .select("accession_number, filing_date")
        .eq("ticker", "QCOM")
        .eq("form", "10-Q")
        .order("filing_date", desc=True)
        .limit(1)
        .execute()
    )

    assert response.data, "No QCOM 10-Q filings found in Supabase."
    accession_number = response.data[0]["accession_number"]
    print(f"Accession number : {accession_number}")

    # Mark as downloaded
    downloaded_row = mark_filing_downloaded(accession_number)
    assert downloaded_row["processing_status"] == "downloaded", (
        f"Expected 'downloaded' but got {downloaded_row['processing_status']!r}."
    )
    assert downloaded_row["downloaded_at"], "downloaded_at is empty."
    print(f"Downloaded status: {downloaded_row['processing_status']}")
    print(f"Downloaded at    : {downloaded_row['downloaded_at']}")

    # Mark as parsed
    parsed_row = mark_filing_parsed(accession_number)
    assert parsed_row["processing_status"] == "parsed", (
        f"Expected 'parsed' but got {parsed_row['processing_status']!r}."
    )
    assert parsed_row["parsed_at"], "parsed_at is empty."
    print(f"Parsed status    : {parsed_row['processing_status']}")
    print(f"Parsed at        : {parsed_row['parsed_at']}")

    print()
    print("PASS: filing status updates are working correctly.")


if __name__ == "__main__":
    main()
