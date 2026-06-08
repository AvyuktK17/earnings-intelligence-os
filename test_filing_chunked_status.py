"""
Test that process_filing() sets processing_status='chunked' and records chunked_at
only after chunk creation succeeds. Uses QCOM 10-Q 0000804328-26-000061.
Runs twice to verify idempotency. Does NOT delete rows or expose credentials.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.process_filing import process_filing

ACCESSION_NUMBER = "0000804328-26-000061"


def count_stored_chunks(supabase, accession_number: str) -> int:
    response = (
        supabase.table("filing_chunks")
        .select("id", count="exact")
        .eq("accession_number", accession_number)
        .execute()
    )
    return response.count


def main():
    supabase = get_supabase_client()

    filing_response = (
        supabase.table("filings")
        .select("ticker, accession_number, sec_url, filing_date")
        .eq("accession_number", ACCESSION_NUMBER)
        .execute()
    )
    assert filing_response.data, f"Filing {ACCESSION_NUMBER} not found in Supabase."
    filing = filing_response.data[0]

    print(f"Run 1: processing {ACCESSION_NUMBER}...")
    result = process_filing(filing)

    # Verify returned result
    assert result["status"] == "chunked", (
        f"Expected status 'chunked' but got {result['status']!r}."
    )
    assert result["html_storage_path"], "html_storage_path missing from result."
    assert result["text_storage_path"], "text_storage_path missing from result."
    assert result["chunk_count"] > 20, (
        f"Expected more than 20 chunks but got {result['chunk_count']}."
    )
    assert result["average_chunk_characters"] > 0, "average_chunk_characters should be > 0."

    # Verify Supabase row
    db = (
        supabase.table("filings")
        .select("processing_status, downloaded_at, parsed_at, chunked_at, html_storage_path, text_storage_path")
        .eq("accession_number", ACCESSION_NUMBER)
        .execute()
    )
    assert db.data, "Filing row not found in Supabase."
    row = db.data[0]

    assert row["processing_status"] == "chunked", (
        f"Supabase processing_status should be 'chunked' but got {row['processing_status']!r}."
    )
    assert row["downloaded_at"], "downloaded_at not populated."
    assert row["parsed_at"], "parsed_at not populated."
    assert row["chunked_at"], "chunked_at not populated."
    assert row["html_storage_path"], "html_storage_path not in Supabase row."
    assert row["text_storage_path"], "text_storage_path not in Supabase row."

    stored_chunks = count_stored_chunks(supabase, ACCESSION_NUMBER)
    assert stored_chunks == result["chunk_count"], (
        f"Supabase has {stored_chunks} chunk rows but result says {result['chunk_count']}."
    )

    print(f"  Ticker       : {result['ticker']}")
    print(f"  Accession    : {result['accession_number']}")
    print(f"  Status       : {result['status']}")
    print(f"  chunked_at   : {row['chunked_at']}")
    print(f"  Chunk count  : {result['chunk_count']}")

    # Run 2: idempotency check
    print(f"\nRun 2: reprocessing to verify idempotency...")
    result2 = process_filing(filing)
    stored_chunks2 = count_stored_chunks(supabase, ACCESSION_NUMBER)

    assert result2["status"] == "chunked", (
        f"Run 2 status should be 'chunked' but got {result2['status']!r}."
    )
    assert result2["chunk_count"] == result["chunk_count"], (
        f"Run 2 produced {result2['chunk_count']} chunks, run 1 had {result['chunk_count']}."
    )
    assert stored_chunks2 == result2["chunk_count"], (
        f"After run 2, Supabase has {stored_chunks2} rows but expected {result2['chunk_count']}."
    )
    print(f"  Chunk count after re-run : {result2['chunk_count']} (no duplicates)")
    print(f"  Final status             : {result2['status']}")

    print()
    print("PASS: chunked status tracking is working correctly.")


if __name__ == "__main__":
    main()
