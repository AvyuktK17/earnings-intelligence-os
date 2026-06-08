"""Read-only analyst review queue for proposed_claims.

Prints all pending claims ordered by created_at descending.
Does not approve, reject, edit, or delete any rows.
Does not call Gemini or any external AI.
"""

from src.database import get_supabase_client


def main() -> None:
    supabase = get_supabase_client()

    rows = (
        supabase.table("proposed_claims")
        .select(
            "id, ticker, accession_number, document_key, theme, claim_text, "
            "supporting_excerpt, source_chunk_id, source_chunk_index, "
            "claim_type, confidence, review_status, created_at"
        )
        .eq("review_status", "pending")
        .order("created_at", desc=True)
        .execute()
        .data
    )

    print(f"Pending proposed claims: {len(rows)}")
    print("=" * 72)

    for i, r in enumerate(rows, 1):
        print(f"\nClaim {i} of {len(rows)}")
        print(f"  id                : {r['id']}")
        print(f"  ticker            : {r['ticker']}")
        print(f"  accession_number  : {r['accession_number']}")
        print(f"  document_key      : {r['document_key']}")
        print(f"  theme             : {r['theme']}")
        print(f"  claim_text        : {r['claim_text']}")
        print(f"  supporting_excerpt: {r['supporting_excerpt']}")
        print(f"  source_chunk_id   : {r['source_chunk_id']}")
        print(f"  source_chunk_index: {r['source_chunk_index']}")
        print(f"  claim_type        : {r['claim_type']}")
        print(f"  confidence        : {r['confidence']}")
        print(f"  review_status     : {r['review_status']}")
        print(f"  created_at        : {r['created_at']}")
        print("-" * 72)

    print(f"\nTotal pending claims: {len(rows)}")


if __name__ == "__main__":
    main()
