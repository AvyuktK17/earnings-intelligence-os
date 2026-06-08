"""
Test claim extraction on the Broadcom 8-K (0001730168-26-000051).
Verifies claims are valid, saved to Supabase, and rerunning replaces pending rows.
Does NOT approve claims or copy them to qualitative_claims.
"""

import re
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()

from src.database import get_supabase_client
from src.claim_extractor import extract_and_store_claims

ACCESSION_NUMBER = "0001730168-26-000051"
ALLOWED_CLAIM_TYPES = {"factual", "interpretive"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


def fetch_pending_claims(supabase, accession_number: str) -> list[dict]:
    response = (
        supabase.table("proposed_claims")
        .select("*")
        .eq("accession_number", accession_number)
        .eq("review_status", "pending")
        .execute()
    )
    return response.data


def fetch_chunks(supabase, accession_number: str) -> dict:
    response = (
        supabase.table("filing_chunks")
        .select("chunk_index, chunk_text")
        .eq("accession_number", accession_number)
        .execute()
    )
    return {row["chunk_index"]: row["chunk_text"] for row in response.data}


def print_claims(claims: list[dict]) -> None:
    for i, c in enumerate(claims, 1):
        print(f"\n  Claim {i}:")
        print(f"    theme             : {c.get('theme', c.get('theme', ''))}")
        print(f"    claim_text        : {c.get('claim_text', '')}")
        print(f"    supporting_excerpt: {c.get('supporting_excerpt', '')}")
        print(f"    source_chunk_index: {c.get('source_chunk_index', '')}")
        print(f"    claim_type        : {c.get('claim_type', '')}")
        print(f"    confidence        : {c.get('confidence', '')}")


def main():
    supabase = get_supabase_client()
    chunk_map = fetch_chunks(supabase, ACCESSION_NUMBER)

    print(f"Run 1: extracting claims from {ACCESSION_NUMBER}...")
    result = extract_and_store_claims(ACCESSION_NUMBER, max_claims=3)

    print(f"\n  Ticker               : {result['ticker']}")
    print(f"  Accession number     : {result['accession_number']}")
    print(f"  Proposed claim count : {result['proposed_claim_count']}")
    print(f"  Skipped invalid      : {result['skipped_invalid_count']}")
    print_claims(result["proposed_claims"])

    # Verify counts
    assert result["proposed_claim_count"] >= 1, "Expected at least 1 proposed claim."
    assert result["proposed_claim_count"] <= 3, (
        f"Expected at most 3 claims but got {result['proposed_claim_count']}."
    )

    # Verify stored rows
    stored = fetch_pending_claims(supabase, ACCESSION_NUMBER)
    assert len(stored) == result["proposed_claim_count"], (
        f"Supabase has {len(stored)} pending rows but result says {result['proposed_claim_count']}."
    )

    for row in stored:
        assert row["review_status"] == "pending", (
            f"Expected review_status 'pending' but got {row['review_status']!r}."
        )
        chunk_idx = row["source_chunk_index"]
        assert chunk_idx in chunk_map, (
            f"source_chunk_index {chunk_idx} does not exist in filing_chunks."
        )
        assert _normalize_ws(row["supporting_excerpt"]) in _normalize_ws(chunk_map[chunk_idx]), (
            f"supporting_excerpt not found in chunk {chunk_idx} after whitespace normalization."
        )
        assert row["claim_type"] in ALLOWED_CLAIM_TYPES, (
            f"Invalid claim_type: {row['claim_type']!r}."
        )
        assert row["confidence"] in ALLOWED_CONFIDENCE, (
            f"Invalid confidence: {row['confidence']!r}."
        )

    # Run 2: verify idempotency
    print(f"\nRun 2: re-extracting to verify no duplicate pending rows...")
    result2 = extract_and_store_claims(ACCESSION_NUMBER, max_claims=3)
    stored2 = fetch_pending_claims(supabase, ACCESSION_NUMBER)

    assert len(stored2) == result2["proposed_claim_count"], (
        f"After run 2, Supabase has {len(stored2)} rows but result says {result2['proposed_claim_count']}."
    )
    print(f"  Pending rows after re-run: {len(stored2)} (no duplicates)")

    print()
    print("PASS: claim extractor is working correctly.")


if __name__ == "__main__":
    main()
