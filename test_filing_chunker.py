"""
Test the filing chunker using the Qualcomm 10-Q (0000804328-26-000061).
Verifies chunk count, sizes, ordering, and idempotency.
Does NOT commit downloaded text or add AI logic.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.filing_chunker import chunk_and_store_filing

ACCESSION_NUMBER = "0000804328-26-000061"


def fetch_chunks(supabase, accession_number: str) -> list[dict]:
    response = (
        supabase.table("filing_chunks")
        .select("chunk_index, character_count, chunk_text")
        .eq("accession_number", accession_number)
        .order("chunk_index")
        .execute()
    )
    return response.data


def main():
    supabase = get_supabase_client()

    print(f"Run 1: chunking {ACCESSION_NUMBER}...")
    result = chunk_and_store_filing(ACCESSION_NUMBER)

    print(f"  Ticker                    : {result['ticker']}")
    print(f"  Accession number          : {result['accession_number']}")
    print(f"  Chunk count               : {result['chunk_count']}")
    print(f"  Total characters          : {result['total_characters']:,}")
    print(f"  Average chunk characters  : {result['average_chunk_characters']:,}")

    # Verify chunk count
    assert result["chunk_count"] > 20, (
        f"Expected more than 20 chunks but got {result['chunk_count']}."
    )

    # Fetch stored chunks and verify
    chunks = fetch_chunks(supabase, ACCESSION_NUMBER)
    assert len(chunks) == result["chunk_count"], (
        f"Supabase has {len(chunks)} rows but result says {result['chunk_count']}."
    )

    for row in chunks:
        assert row["character_count"] > 0, (
            f"Chunk {row['chunk_index']} has character_count=0."
        )
        assert row["character_count"] <= 2000, (
            f"Chunk {row['chunk_index']} exceeds 2000 characters: {row['character_count']}."
        )

    # Verify indexes are 0-based and sequential
    indexes = [row["chunk_index"] for row in chunks]
    assert indexes[0] == 0, f"First chunk index should be 0 but got {indexes[0]}."
    assert indexes == list(range(len(chunks))), "Chunk indexes are not sequential."

    assert result["total_characters"] > 0, "total_characters should be positive."

    print()
    print("--- First chunk preview ---")
    print(chunks[0]["chunk_text"][:300])
    print("---------------------------")

    # Run 2: verify idempotency (no duplicates)
    print(f"\nRun 2: re-chunking to verify no duplicates...")
    result2 = chunk_and_store_filing(ACCESSION_NUMBER)
    chunks2 = fetch_chunks(supabase, ACCESSION_NUMBER)

    assert len(chunks2) == result2["chunk_count"], "Run 2 chunk count mismatch."
    assert result2["chunk_count"] == result["chunk_count"], (
        f"Run 2 produced {result2['chunk_count']} chunks but run 1 produced {result['chunk_count']}."
    )

    print(f"  Chunk count after re-run  : {result2['chunk_count']} (same as run 1)")
    print()
    print("PASS: filing chunker is working correctly.")


if __name__ == "__main__":
    main()
