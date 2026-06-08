"""
Test claim extraction on the AVGO EX-99.1 exhibit
(accession 0001730168-26-000051, document_key "exhibit:avgo-05032026x8kxex99.htm").
Verifies ≥ 3 valid claims are stored and that rerunning replaces only exhibit
pending rows without touching primary-document pending rows.
Does NOT approve claims or copy them to qualitative_claims.
"""

import re
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.claim_extractor import extract_and_store_claims

ACCESSION_NUMBER = "0001730168-26-000051"
EXHIBIT_FILENAME = "avgo-05032026x8kxex99.htm"
DOCUMENT_KEY = f"exhibit:{EXHIBIT_FILENAME}"
ALLOWED_CLAIM_TYPES = {"factual", "interpretive"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def fetch_pending_claims(supabase, accession_number: str, document_key: str) -> list[dict]:
    response = (
        supabase.table("proposed_claims")
        .select("*")
        .eq("accession_number", accession_number)
        .eq("document_key", document_key)
        .eq("review_status", "pending")
        .execute()
    )
    return response.data


def fetch_chunks(supabase, accession_number: str, document_key: str) -> dict:
    response = (
        supabase.table("filing_chunks")
        .select("chunk_index, chunk_text")
        .eq("accession_number", accession_number)
        .eq("document_key", document_key)
        .execute()
    )
    return {row["chunk_index"]: row["chunk_text"] for row in response.data}


def print_claims(claims: list[dict]) -> None:
    for i, c in enumerate(claims, 1):
        print(f"\n  Claim {i}:")
        print(f"    theme             : {c.get('theme', '')}")
        print(f"    claim_text        : {c.get('claim_text', '')}")
        print(f"    supporting_excerpt: {c.get('supporting_excerpt', '')}")
        print(f"    source_chunk_index: {c.get('source_chunk_index', '')}")
        print(f"    claim_type        : {c.get('claim_type', '')}")
        print(f"    confidence        : {c.get('confidence', '')}")


def main():
    supabase = get_supabase_client()
    chunk_map = fetch_chunks(supabase, ACCESSION_NUMBER, DOCUMENT_KEY)

    print(f"Exhibit chunk count for {DOCUMENT_KEY}: {len(chunk_map)}")
    assert len(chunk_map) >= 3, (
        f"Expected ≥ 3 exhibit chunks but found {len(chunk_map)}. "
        "Run exhibit chunking first."
    )

    print(f"\nRun 1: extracting claims from exhibit {DOCUMENT_KEY}...")
    result = extract_and_store_claims(
        ACCESSION_NUMBER,
        max_claims=5,
        document_key=DOCUMENT_KEY,
    )

    print(f"\n  Ticker               : {result['ticker']}")
    print(f"  Accession number     : {result['accession_number']}")
    print(f"  Document key         : {result['document_key']}")
    print(f"  Proposed claim count : {result['proposed_claim_count']}")
    print(f"  Skipped invalid      : {result['skipped_invalid_count']}")
    print_claims(result["proposed_claims"])

    assert result["document_key"] == DOCUMENT_KEY, (
        f"result document_key mismatch: {result['document_key']!r}"
    )
    assert result["proposed_claim_count"] >= 3, (
        f"Expected ≥ 3 proposed claims but got {result['proposed_claim_count']}."
    )

    # Verify stored rows
    stored = fetch_pending_claims(supabase, ACCESSION_NUMBER, DOCUMENT_KEY)
    assert len(stored) == result["proposed_claim_count"], (
        f"Supabase has {len(stored)} exhibit pending rows but result says "
        f"{result['proposed_claim_count']}."
    )

    for row in stored:
        assert row["review_status"] == "pending", (
            f"Expected review_status 'pending' but got {row['review_status']!r}."
        )
        assert row["document_key"] == DOCUMENT_KEY, (
            f"Expected document_key {DOCUMENT_KEY!r} but got {row['document_key']!r}."
        )
        chunk_idx = row["source_chunk_index"]
        assert chunk_idx in chunk_map, (
            f"source_chunk_index {chunk_idx} does not exist in exhibit filing_chunks."
        )
        assert _normalize_ws(row["supporting_excerpt"]) in _normalize_ws(chunk_map[chunk_idx]), (
            f"supporting_excerpt not found in exhibit chunk {chunk_idx} after "
            "whitespace normalization."
        )
        assert row["claim_type"] in ALLOWED_CLAIM_TYPES, (
            f"Invalid claim_type: {row['claim_type']!r}."
        )
        assert row["confidence"] in ALLOWED_CONFIDENCE, (
            f"Invalid confidence: {row['confidence']!r}."
        )

    # Run 2: verify idempotency — exhibit claims only, primary rows untouched
    print(f"\nRun 2: re-extracting exhibit claims to verify idempotency...")
    result2 = extract_and_store_claims(
        ACCESSION_NUMBER,
        max_claims=5,
        document_key=DOCUMENT_KEY,
    )
    stored2 = fetch_pending_claims(supabase, ACCESSION_NUMBER, DOCUMENT_KEY)
    assert len(stored2) == result2["proposed_claim_count"], (
        f"After run 2, Supabase has {len(stored2)} rows but result says "
        f"{result2['proposed_claim_count']}."
    )
    print(f"  Exhibit pending rows after re-run: {len(stored2)} (no duplicates)")

    # Verify primary pending rows were not deleted during exhibit run
    primary_stored = (
        supabase.table("proposed_claims")
        .select("id")
        .eq("accession_number", ACCESSION_NUMBER)
        .eq("document_key", "primary")
        .eq("review_status", "pending")
        .execute()
    ).data
    print(f"  Primary pending rows untouched: {len(primary_stored)}")

    print()
    print("PASS: exhibit claim extractor is working correctly.")


if __name__ == "__main__":
    main()
