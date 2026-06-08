"""
Test the chunk backfill worker on parsed filings that have a text_storage_path.
Verifies up to 3 rows are chunked and their Supabase rows are updated.
Does NOT delete rows, make the bucket public, or commit filing contents.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.backfill_missing_chunks import backfill_missing_chunks

BATCH_SIZE = 3


def count_parsed_with_storage(supabase) -> int:
    response = (
        supabase.table("filings")
        .select("id", count="exact")
        .eq("processing_status", "parsed")
        .not_.is_("text_storage_path", "null")
        .execute()
    )
    return response.count


def main():
    supabase = get_supabase_client()

    before_count = count_parsed_with_storage(supabase)
    print(f"Parsed filings with text_storage_path (need chunking): {before_count}")

    if before_count == 0:
        print("Nothing to backfill — all parsed filings already have chunks.")
        print("\nPASS: backfill worker correctly reports no work needed.")
        return

    print(f"\nRunning backfill (limit={BATCH_SIZE})...\n")
    results = backfill_missing_chunks(limit=BATCH_SIZE)

    assert len(results) <= BATCH_SIZE, (
        f"Expected at most {BATCH_SIZE} results but got {len(results)}."
    )

    successful = [r for r in results if r["status"] == "chunked"]

    for r in results:
        ticker = r["ticker"]
        acc = r["accession_number"]
        status = r["status"]

        if status == "chunked":
            print(f"  {ticker:<6} {acc:<28} {status}  chunks={r['chunk_count']}  avg={r['average_chunk_characters']} chars")
            assert r["chunk_count"] > 0, f"{acc}: chunk_count should be > 0."

            # Verify Supabase row
            db = (
                supabase.table("filings")
                .select("processing_status, chunked_at")
                .eq("accession_number", acc)
                .execute()
            )
            assert db.data, f"Row not found in Supabase for {acc}."
            row = db.data[0]
            assert row["processing_status"] == "chunked", (
                f"{acc}: expected 'chunked' but got {row['processing_status']!r}."
            )
            assert row["chunked_at"], f"{acc}: chunked_at not populated."

            # Verify filing_chunks rows exist
            chunks = (
                supabase.table("filing_chunks")
                .select("id", count="exact")
                .eq("accession_number", acc)
                .execute()
            )
            assert chunks.count == r["chunk_count"], (
                f"{acc}: Supabase has {chunks.count} chunk rows but result says {r['chunk_count']}."
            )
        else:
            print(f"  {ticker:<6} {acc:<28} {status}  error={r.get('error_message', '')}")

    after_count = count_parsed_with_storage(supabase)
    expected_after = before_count - len(successful)

    print(f"\nCount before : {before_count}")
    print(f"Count after  : {after_count}")
    print(f"Chunked      : {len(successful)}")

    assert after_count == expected_after, (
        f"Expected count to drop to {expected_after} but got {after_count}."
    )

    print()
    print("PASS: chunk backfill worker is working correctly.")


if __name__ == "__main__":
    main()
