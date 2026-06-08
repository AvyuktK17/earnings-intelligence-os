"""Test the human-review backend (approve, edit, reject).

Inserts three temporary grounded rows using a real AVGO exhibit chunk,
exercises all three review paths, tests the ungrounded-legacy guard,
then deletes only the temporary rows and confirms legacy rows are untouched.

Does NOT call Gemini, modify real pending claims, or touch qualitative_claims.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.claim_review import approve_claim, approve_claim_with_edits, reject_claim

ACCESSION = "0001730168-26-000051"
DOCUMENT_KEY = "exhibit:avgo-05032026x8kxex99.htm"
TICKER = "AVGO"
FILING_ID = 26


def main() -> None:
    supabase = get_supabase_client()

    # --- 1. Query a real exhibit chunk ---
    chunks = (
        supabase.table("filing_chunks")
        .select("id, chunk_index")
        .eq("accession_number", ACCESSION)
        .eq("document_key", DOCUMENT_KEY)
        .order("chunk_index")
        .execute()
        .data
    )
    assert chunks, "No exhibit chunks found — run chunking first."
    # Prefer chunk_index=1 (substantive content) over 0 (tiny header).
    chunk = next((c for c in chunks if c["chunk_index"] == 1), chunks[0])
    source_chunk_id = chunk["id"]
    source_chunk_index = chunk["chunk_index"]
    print(f"Using exhibit chunk: id={source_chunk_id}, chunk_index={source_chunk_index}")

    # --- 2. Snapshot legacy rows before any writes ---
    legacy_before = (
        supabase.table("proposed_claims")
        .select("id, review_status, reviewer_notes, reviewed_at, source_chunk_id")
        .is_("source_chunk_id", "null")
        .execute()
        .data
    )
    legacy_ids = {r["id"] for r in legacy_before}
    print(f"Legacy rows (source_chunk_id=None): {sorted(legacy_ids)}")

    # --- 3. Insert three temporary grounded rows ---
    base = {
        "filing_id": FILING_ID,
        "ticker": TICKER,
        "accession_number": ACCESSION,
        "document_key": DOCUMENT_KEY,
        "source_chunk_id": source_chunk_id,
        "source_chunk_index": source_chunk_index,
        "theme": "Test",
        "supporting_excerpt": "placeholder excerpt for test row",
        "claim_type": "factual",
        "confidence": "high",
        "review_status": "pending",
    }
    temp_claims = [
        {**base, "claim_text": "TEMP TEST CLAIM FOR APPROVAL"},
        {**base, "claim_text": "TEMP TEST CLAIM FOR EDIT"},
        {**base, "claim_text": "TEMP TEST CLAIM FOR REJECTION"},
    ]
    inserted_ids = []
    for row in temp_claims:
        r = supabase.table("proposed_claims").insert(row).execute()
        inserted_ids.append(r.data[0]["id"])

    approve_id, edit_id, reject_id = inserted_ids
    print(
        f"Inserted temp rows: approve_id={approve_id}, "
        f"edit_id={edit_id}, reject_id={reject_id}"
    )

    try:
        # --- 4a. approve_claim ---
        print("\nTesting approve_claim()...")
        result = approve_claim(approve_id, reviewer_notes="Verified against source. Approved.")
        assert result["review_status"] == "approved", (
            f"Expected 'approved', got {result['review_status']!r}."
        )
        assert result["reviewed_at"] is not None, "reviewed_at should be set."
        assert result["reviewer_notes"] == "Verified against source. Approved."
        assert result["claim_text"] == "TEMP TEST CLAIM FOR APPROVAL"
        print("  [OK] approve_claim: status=approved, reviewed_at set, notes saved")

        # --- 4b. approve_claim_with_edits ---
        print("\nTesting approve_claim_with_edits()...")
        edited_text = "EDITED: Broadcom Q2 FY2026 AI revenue was $10.8 billion (reviewer-corrected)."
        result2 = approve_claim_with_edits(
            edit_id, edited_text, reviewer_notes="Corrected phrasing for clarity."
        )
        assert result2["review_status"] == "edited", (
            f"Expected 'edited', got {result2['review_status']!r}."
        )
        assert result2["edited_claim_text"] == edited_text, (
            f"edited_claim_text mismatch: {result2['edited_claim_text']!r}."
        )
        assert result2["claim_text"] == "TEMP TEST CLAIM FOR EDIT", (
            "Original claim_text must be preserved unchanged."
        )
        assert result2["reviewed_at"] is not None, "reviewed_at should be set."
        assert result2["reviewer_notes"] == "Corrected phrasing for clarity."
        print(
            "  [OK] approve_claim_with_edits: status=edited, original text preserved, "
            "edited_claim_text populated, reviewed_at set"
        )

        # --- 4c. reject_claim ---
        print("\nTesting reject_claim()...")
        result3 = reject_claim(reject_id, reviewer_notes="Not financially material.")
        assert result3["review_status"] == "rejected", (
            f"Expected 'rejected', got {result3['review_status']!r}."
        )
        assert result3["reviewed_at"] is not None, "reviewed_at should be set."
        assert result3["reviewer_notes"] == "Not financially material."
        print("  [OK] reject_claim: status=rejected, reviewed_at set, notes saved")

        # --- 5. Ungrounded-legacy approval guard ---
        print("\nTesting ungrounded-legacy approval guard...")
        legacy_pending = (
            supabase.table("proposed_claims")
            .select("id, source_chunk_id")
            .eq("review_status", "pending")
            .is_("source_chunk_id", "null")
            .limit(1)
            .execute()
            .data
        )
        assert legacy_pending, (
            "No legacy pending row with source_chunk_id=None found — cannot test guard."
        )
        legacy_id = legacy_pending[0]["id"]

        guard_fired = False
        try:
            approve_claim(legacy_id)
        except ValueError as exc:
            guard_fired = True
            print(f"  [OK] guard raised ValueError: {exc}")
        assert guard_fired, "Expected ValueError for ungrounded claim but none was raised."

        # Confirm the legacy row was not modified
        after = (
            supabase.table("proposed_claims")
            .select("review_status, reviewed_at, reviewer_notes")
            .eq("id", legacy_id)
            .execute()
            .data[0]
        )
        assert after["review_status"] == "pending", (
            f"Legacy row status changed to {after['review_status']!r} — must remain 'pending'."
        )
        assert after["reviewed_at"] is None, "Legacy row reviewed_at must remain NULL."
        assert after["reviewer_notes"] is None, "Legacy row reviewer_notes must remain NULL."
        print(f"  [OK] legacy row id={legacy_id} untouched: still pending, reviewed_at=None")

    finally:
        # --- 6. Delete only the three temporary rows ---
        supabase.table("proposed_claims").delete().in_("id", inserted_ids).execute()
        remaining = (
            supabase.table("proposed_claims")
            .select("id")
            .in_("id", inserted_ids)
            .execute()
            .data
        )
        assert len(remaining) == 0, f"Temp rows not fully deleted: {remaining}"
        print(f"\nCleaned up temp rows {inserted_ids}.")

    # --- 7. Confirm all legacy rows are still present and unmodified ---
    legacy_after = (
        supabase.table("proposed_claims")
        .select("id, review_status, reviewer_notes, reviewed_at")
        .in_("id", list(legacy_ids))
        .execute()
        .data
    )
    assert len(legacy_after) == len(legacy_ids), (
        f"Expected {len(legacy_ids)} legacy rows but found {len(legacy_after)}."
    )
    for row in legacy_after:
        assert row["review_status"] == "pending", (
            f"Legacy row id={row['id']} status changed to {row['review_status']!r}."
        )
        assert row["reviewed_at"] is None, (
            f"Legacy row id={row['id']} reviewed_at is no longer NULL."
        )
        assert row["reviewer_notes"] is None, (
            f"Legacy row id={row['id']} reviewer_notes is no longer NULL."
        )
    print(f"Legacy rows {sorted(legacy_ids)} confirmed untouched.")

    print()
    print(
        "PASS: approve, approve-with-edits, reject, and ungrounded-legacy guard "
        "all working correctly."
    )


if __name__ == "__main__":
    main()
