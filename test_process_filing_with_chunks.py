"""
Test that process_filing() automatically chunks the filing after parsing.
Uses the latest Qualcomm 10-Q. Runs twice to verify idempotency.
Does NOT delete rows, make the bucket public, or commit filing contents.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.process_filing import process_filing


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

    print(f"Run 1: processing {filing['accession_number']}...")
    result = process_filing(filing)

    print(f"  Ticker                   : {result['ticker']}")
    print(f"  Accession number         : {result['accession_number']}")
    print(f"  Final status             : {result['status']}")
    print(f"  HTML Storage path        : {result['html_storage_path']}")
    print(f"  Text Storage path        : {result['text_storage_path']}")
    print(f"  Chunk count              : {result['chunk_count']}")
    print(f"  Average chunk characters : {result['average_chunk_characters']:,}")

    assert result["status"] == "parsed", (
        f"Expected 'parsed' but got {result['status']!r}."
    )
    assert result["html_storage_path"], "html_storage_path is missing."
    assert result["text_storage_path"], "text_storage_path is missing."
    assert result["chunk_count"] > 20, (
        f"Expected more than 20 chunks but got {result['chunk_count']}."
    )
    assert result["average_chunk_characters"] > 0, "average_chunk_characters should be > 0."

    stored_count = count_stored_chunks(supabase, filing["accession_number"])
    assert stored_count == result["chunk_count"], (
        f"Supabase has {stored_count} chunk rows but result says {result['chunk_count']}."
    )

    print(f"\nRun 2: reprocessing to verify no duplicate chunks...")
    result2 = process_filing(filing)
    stored_count2 = count_stored_chunks(supabase, filing["accession_number"])

    assert result2["chunk_count"] == result["chunk_count"], (
        f"Run 2 produced {result2['chunk_count']} chunks, run 1 had {result['chunk_count']}."
    )
    assert stored_count2 == result2["chunk_count"], (
        f"After run 2, Supabase has {stored_count2} rows but expected {result2['chunk_count']}."
    )
    print(f"  Chunk count after re-run : {result2['chunk_count']} (no duplicates)")

    print()
    print("PASS: process_filing with automatic chunking is working correctly.")


if __name__ == "__main__":
    main()
