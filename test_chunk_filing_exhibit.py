"""
Test exhibit chunking for the Broadcom 8-K earnings-release exhibit
(accession 0001730168-26-000051, document_type='earnings_release').

Verifies:
  - exhibit chunks are stored with the correct document_key and filing_document_id
  - chunk indexes are sequential starting at 0
  - every chunk respects the 2000-character limit
  - primary-document chunks for the same accession are untouched
  - rerunning safely replaces exhibit chunks without creating duplicates

Does not call Gemini, modify qualitative_claims, or delete Supabase rows beyond
the exhibit chunks being replaced.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.filing_chunker import chunk_and_store_document

ACCESSION_NUMBER = "0001730168-26-000051"
DOCUMENT_TYPE = "earnings_release"
MIN_CHUNK_COUNT = 5
MAX_CHUNK_CHARACTERS = 2000


def fetch_chunks(supabase, accession_number: str, document_key: str) -> list[dict]:
    response = (
        supabase.table("filing_chunks")
        .select("chunk_index, chunk_text, character_count, document_key, filing_document_id")
        .eq("accession_number", accession_number)
        .eq("document_key", document_key)
        .order("chunk_index")
        .execute()
    )
    return response.data


def main():
    supabase = get_supabase_client()

    # Look up the filing_documents row
    doc_response = (
        supabase.table("filing_documents")
        .select("id, filename")
        .eq("accession_number", ACCESSION_NUMBER)
        .eq("document_type", DOCUMENT_TYPE)
        .execute()
    )
    assert doc_response.data, (
        f"No filing_documents row found for accession={ACCESSION_NUMBER!r} "
        f"document_type={DOCUMENT_TYPE!r}. Run test_process_filing_exhibit.py first."
    )
    doc_row = doc_response.data[0]
    document_id = doc_row["id"]
    filename = doc_row["filename"]
    expected_document_key = f"exhibit:{filename}"

    print(f"Filing          : {ACCESSION_NUMBER}")
    print(f"Document id     : {document_id}")
    print(f"Filename        : {filename}")
    print(f"Expected key    : {expected_document_key}")

    # Count primary chunks before we run anything (must still exist after)
    primary_before = fetch_chunks(supabase, ACCESSION_NUMBER, "primary")
    print(f"\nPrimary chunks before run: {len(primary_before)}")

    # Run 1
    print(f"\nRun 1: chunking exhibit document {document_id} ...")
    result = chunk_and_store_document(document_id)

    ticker = result["ticker"]
    chunk_count = result["chunk_count"]
    avg_chars = result["average_chunk_characters"]
    document_key = result["document_key"]

    print(f"\n  Ticker              : {ticker}")
    print(f"  Accession number    : {result['accession_number']}")
    print(f"  Filename            : {result['filename']}")
    print(f"  Document key        : {document_key}")
    print(f"  Chunk count         : {chunk_count}")
    print(f"  Average chunk size  : {avg_chars} chars")

    # Verify chunk_count
    assert chunk_count > MIN_CHUNK_COUNT, (
        f"Expected more than {MIN_CHUNK_COUNT} exhibit chunks, got {chunk_count}."
    )

    # Verify document_key matches expected pattern
    assert document_key == expected_document_key, (
        f"Expected document_key {expected_document_key!r}, got {document_key!r}."
    )

    # Verify the filing_document_id in the result
    assert result["filing_document_id"] == document_id, (
        f"Expected filing_document_id {document_id}, got {result['filing_document_id']}."
    )

    # Fetch stored rows and verify each one
    stored = fetch_chunks(supabase, ACCESSION_NUMBER, expected_document_key)
    assert len(stored) == chunk_count, (
        f"Expected {chunk_count} stored rows, found {len(stored)}."
    )

    for row in stored:
        assert row["document_key"] == expected_document_key, (
            f"Chunk has wrong document_key: {row['document_key']!r}."
        )
        assert row["filing_document_id"] == document_id, (
            f"Chunk has wrong filing_document_id: {row['filing_document_id']}."
        )
        char_count = row["character_count"]
        assert 0 < char_count <= MAX_CHUNK_CHARACTERS, (
            f"chunk_index {row['chunk_index']}: character_count {char_count} "
            f"is outside (0, {MAX_CHUNK_CHARACTERS}]."
        )

    # Verify sequential chunk indexes starting at 0
    indexes = [row["chunk_index"] for row in stored]
    assert indexes == list(range(len(stored))), (
        f"Chunk indexes are not sequential from 0: {indexes}."
    )

    # Verify primary chunks are untouched
    primary_after = fetch_chunks(supabase, ACCESSION_NUMBER, "primary")
    assert len(primary_after) == len(primary_before), (
        f"Primary chunk count changed from {len(primary_before)} to {len(primary_after)}. "
        "The exhibit chunker must not touch primary chunks."
    )
    print(f"\n  Primary chunks after run: {len(primary_after)} (unchanged)")

    # Run 2: rerun to verify no duplicates
    print(f"\nRun 2: rerunning to verify no duplicate exhibit chunks ...")
    result2 = chunk_and_store_document(document_id)
    stored2 = fetch_chunks(supabase, ACCESSION_NUMBER, expected_document_key)
    assert len(stored2) == result2["chunk_count"], (
        f"After rerun, DB has {len(stored2)} rows but result says {result2['chunk_count']}."
    )
    print(f"  Exhibit chunks after rerun: {len(stored2)} (no duplicates)")

    # Primary chunks must still be untouched after second run
    primary_after2 = fetch_chunks(supabase, ACCESSION_NUMBER, "primary")
    assert len(primary_after2) == len(primary_before), (
        f"Primary chunk count changed after second run: {len(primary_after2)}."
    )

    print()
    print("PASS: exhibit chunker is working correctly.")
    print(f"  Ticker                       : {ticker}")
    print(f"  Accession number             : {result['accession_number']}")
    print(f"  Filename                     : {filename}")
    print(f"  Document key                 : {document_key}")
    print(f"  Exhibit chunk count          : {chunk_count}")
    print(f"  Average chunk size           : {avg_chars} chars")
    print(f"  Primary chunks still present : {len(primary_after2)}")
    print(f"  Duplicate rows after rerun   : none")


if __name__ == "__main__":
    main()
