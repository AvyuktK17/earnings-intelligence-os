"""
Test the filing downloader using the most recent Qualcomm 10-Q stored in Supabase.
Downloads the filing HTML to data/raw_filings/qcom_latest_10q.html.
Does NOT modify .env or upload any downloaded content.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.filing_downloader import download_filing

OUTPUT_PATH = "data/raw_filings/qcom_latest_10q.html"


def main():
    supabase = get_supabase_client()

    # Fetch the most recent Qualcomm 10-Q from Supabase
    response = (
        supabase.table("filings")
        .select("accession_number, sec_url, filing_date")
        .eq("ticker", "QCOM")
        .eq("form", "10-Q")
        .order("filing_date", desc=True)
        .limit(1)
        .execute()
    )

    assert response.data, "No QCOM 10-Q filings found in Supabase."
    filing = response.data[0]

    accession_number = filing["accession_number"]
    sec_url = filing["sec_url"]

    print(f"Accession number : {accession_number}")
    print(f"SEC URL          : {sec_url}")
    print(f"Downloading to   : {OUTPUT_PATH}")

    saved_path = download_filing(sec_url, OUTPUT_PATH)

    # Verify the file exists and is not empty
    assert os.path.exists(saved_path), f"File not found at {saved_path}."
    file_size = os.path.getsize(saved_path)
    assert file_size > 0, "Downloaded file is empty."

    # Verify the content looks like HTML
    with open(saved_path, "rb") as f:
        start = f.read(1024).lower()
    assert b"<html" in start or b"<!doctype" in start, (
        "Downloaded content does not appear to be HTML."
    )

    print(f"File size        : {file_size:,} bytes")
    print()
    print("PASS: filing downloader is working correctly.")


if __name__ == "__main__":
    main()
