"""
Test earnings-release exhibit processing for the Broadcom 8-K (0001730168-26-000051).
Verifies the exhibit is downloaded, parsed, uploaded to Storage, and recorded in
filing_documents.  Runs twice to confirm upsert prevents duplicate rows.
Does not chunk the exhibit, call Gemini, or modify qualitative_claims.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.process_filing_exhibit import process_earnings_release_exhibit

ACCESSION_NUMBER = "0001730168-26-000051"
MIN_TEXT_BYTES = 1_000


def fetch_filing_document_rows(supabase, accession_number: str, filename: str) -> list[dict]:
    response = (
        supabase.table("filing_documents")
        .select("*")
        .eq("accession_number", accession_number)
        .eq("filename", filename)
        .execute()
    )
    return response.data


def main():
    supabase = get_supabase_client()

    # Run 1
    print(f"Run 1: processing earnings-release exhibit for {ACCESSION_NUMBER} ...")
    result = process_earnings_release_exhibit(ACCESSION_NUMBER)

    ticker = result["ticker"]
    filename = result["filename"]
    document_type = result["document_type"]
    html_storage_path = result["html_storage_path"]
    text_storage_path = result["text_storage_path"]
    html_size = result["html_size_bytes"]
    text_size = result["text_size_bytes"]

    print(f"\n  Ticker              : {ticker}")
    print(f"  Accession number    : {result['accession_number']}")
    print(f"  Filename            : {filename}")
    print(f"  Document type       : {document_type}")
    print(f"  HTML Storage path   : {html_storage_path}")
    print(f"  Text Storage path   : {text_storage_path}")
    print(f"  HTML size           : {html_size:,} bytes")
    print(f"  Parsed-text size    : {text_size:,} bytes")

    # Verify document_type
    assert document_type == "earnings_release", (
        f"Expected document_type 'earnings_release', got {document_type!r}."
    )

    # Verify filename is populated
    assert filename, "Expected filename to be populated."

    # Derive expected local paths to check on disk
    safe_acc = ACCESSION_NUMBER.replace("-", "_")
    import re
    safe_fn = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
    html_local = f"data/raw_filings/{ticker}_{safe_acc}_{safe_fn}"
    text_local = f"data/parsed_filings/{ticker}_{safe_acc}_{safe_fn}.txt"

    assert os.path.exists(html_local), f"Local HTML not found: {html_local}"
    assert os.path.exists(text_local), f"Local text not found: {text_local}"

    assert html_size > 0, f"HTML size is 0 bytes."
    assert text_size >= MIN_TEXT_BYTES, (
        f"Parsed-text is only {text_size:,} bytes; expected >= {MIN_TEXT_BYTES:,}."
    )

    # Verify Storage paths are populated
    assert html_storage_path, "html_storage_path should not be empty."
    assert text_storage_path, "text_storage_path should not be empty."

    # Verify exactly one row in filing_documents
    rows = fetch_filing_document_rows(supabase, ACCESSION_NUMBER, filename)
    assert len(rows) == 1, (
        f"Expected 1 filing_documents row, found {len(rows)}."
    )
    row = rows[0]
    assert row["document_type"] == "earnings_release"
    assert row["html_storage_path"] == html_storage_path
    assert row["text_storage_path"] == text_storage_path

    # Run 2: verify upsert prevents duplicate rows
    print(f"\nRun 2: rerunning to verify no duplicate filing_documents rows ...")
    process_earnings_release_exhibit(ACCESSION_NUMBER)
    rows_after = fetch_filing_document_rows(supabase, ACCESSION_NUMBER, filename)
    assert len(rows_after) == 1, (
        f"After rerun, expected 1 row but found {len(rows_after)} (duplicate inserted)."
    )
    print(f"  Rows after rerun: {len(rows_after)} (no duplicates)")

    print()
    print("PASS: earnings-release exhibit processor is working correctly.")
    print(f"  Ticker              : {ticker}")
    print(f"  Accession number    : {result['accession_number']}")
    print(f"  Selected filename   : {filename}")
    print(f"  Document type       : {document_type}")
    print(f"  HTML Storage path   : {html_storage_path}")
    print(f"  Text Storage path   : {text_storage_path}")
    print(f"  Parsed-text size    : {text_size:,} bytes")
    print(f"  Duplicate rows      : none")


if __name__ == "__main__":
    main()
