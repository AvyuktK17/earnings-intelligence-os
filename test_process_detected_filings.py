"""
Test the detected-filing worker using a single 'detected' row in Supabase.
Verifies that exactly one filing is processed and its status updated correctly.
Does NOT delete rows or commit downloaded/parsed files.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.process_detected_filings import process_detected_filings


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
    assert detected_before >= 1, (
        "No filings with status 'detected' found. "
        "Run python run_monitor.py to sync new filings first."
    )

    print("\nProcessing one detected filing...")
    results = process_detected_filings(limit=1)

    assert len(results) == 1, (
        f"Expected exactly 1 result but got {len(results)}."
    )
    result = results[0]

    print(f"\nResult:")
    print(f"  Ticker           : {result['ticker']}")
    print(f"  Accession number : {result['accession_number']}")
    print(f"  Status           : {result['status']}")
    print(f"  HTML path        : {result.get('html_path', 'n/a')}")
    print(f"  Text path        : {result.get('text_path', 'n/a')}")
    print(f"  HTML size        : {result.get('html_size_bytes', 0):,} bytes")
    print(f"  Text size        : {result.get('text_size_bytes', 0):,} bytes")

    assert result["status"] == "parsed", (
        f"Expected status 'parsed' but got {result['status']!r}. "
        f"Error: {result.get('error_message', 'n/a')}"
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
    # 8-K filings are legitimately short; 500 chars confirms the parser produced real output
    assert len(text_content) >= 500, (
        f"Expected at least 500 text characters but got {len(text_content)}."
    )

    # Confirm Supabase row is updated
    db_response = (
        supabase.table("filings")
        .select("processing_status, downloaded_at, parsed_at")
        .eq("accession_number", result["accession_number"])
        .execute()
    )
    assert db_response.data, "Could not find the filing row in Supabase."
    row = db_response.data[0]

    assert row["processing_status"] == "parsed", (
        f"Supabase processing_status should be 'parsed' but got {row['processing_status']!r}."
    )
    assert row["downloaded_at"], "downloaded_at is not populated."
    assert row["parsed_at"], "parsed_at is not populated."

    print(f"\n  Supabase status  : {row['processing_status']}")
    print(f"  Downloaded at    : {row['downloaded_at']}")
    print(f"  Parsed at        : {row['parsed_at']}")
    print()
    print("PASS: process_detected_filings is working correctly.")


if __name__ == "__main__":
    main()
