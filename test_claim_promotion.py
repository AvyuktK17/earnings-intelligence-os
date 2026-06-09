"""Test claim promotion: approved and edited claims reach qualitative_claims;
rejected and pending are excluded; rerunning creates no duplicates.

Inserts four temporary proposed_claims rows (approved, edited, rejected,
pending) using a real AVGO exhibit chunk, calls promote_reviewed_claims(),
verifies behaviour, then cleans up only the temporary rows.
Does not call Gemini. Does not modify real proposed or qualitative claims.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.claim_promotion import promote_reviewed_claims

ACCESSION = "0001730168-26-000051"
DOCUMENT_KEY = "exhibit:avgo-05032026x8kxex99.htm"
TICKER = "AVGO"
FILING_ID = 26
SOURCE_CHUNK_ID = 1499
SOURCE_CHUNK_INDEX = 1


def _qc_for(supabase, proposed_claim_ids: list[int]) -> list[dict]:
    """Return qualitative_claims rows whose proposed_claim_id is in the given list."""
    return (
        supabase.table("qualitative_claims")
        .select("proposed_claim_id, ticker, theme, claim, source_chunk_id, document_key, human_reviewed, factual_or_interpretive, confidence")
        .in_("proposed_claim_id", proposed_claim_ids)
        .execute()
        .data
    )


def main() -> None:
    supabase = get_supabase_client()

    # Snapshot: how many qualitative_claims rows exist before the test.
    qc_before_count = len(
        supabase.table("qualitative_claims").select("proposed_claim_id").execute().data
    )
    print(f"qualitative_claims rows before test : {qc_before_count}")

    # --- Insert four temporary proposed_claims rows ---
    base = {
        "filing_id": FILING_ID,
        "ticker": TICKER,
        "accession_number": ACCESSION,
        "document_key": DOCUMENT_KEY,
        "source_chunk_id": SOURCE_CHUNK_ID,
        "source_chunk_index": SOURCE_CHUNK_INDEX,
        "theme": "Test",
        "supporting_excerpt": "placeholder excerpt for promotion test",
        "claim_type": "factual",
        "confidence": "high",
    }
    temp_rows = [
        {**base, "claim_text": "TEMP PROMO TEST — APPROVED", "review_status": "approved"},
        {
            **base,
            "claim_text": "TEMP PROMO TEST — EDIT (original)",
            "edited_claim_text": "TEMP PROMO TEST — EDIT (corrected)",
            "review_status": "edited",
        },
        {**base, "claim_text": "TEMP PROMO TEST — REJECTED", "review_status": "rejected"},
        {**base, "claim_text": "TEMP PROMO TEST — PENDING", "review_status": "pending"},
    ]

    inserted_ids = []
    for row in temp_rows:
        r = supabase.table("proposed_claims").insert(row).execute()
        inserted_ids.append(r.data[0]["id"])

    approved_id, edited_id, rejected_id, pending_id = inserted_ids
    print(
        f"Inserted temp rows: approved={approved_id}, edited={edited_id}, "
        f"rejected={rejected_id}, pending={pending_id}"
    )

    try:
        # --- Run 1: promotion ---
        print("\nRun 1: promote_reviewed_claims()...")
        result = promote_reviewed_claims()
        print(
            f"  eligible={result['eligible_count']}, "
            f"promoted={result['promoted_count']}, "
            f"skipped={result['skipped_existing_count']}"
        )

        # The two temp eligible rows (approved + edited) must appear in promoted_claims.
        promoted_ids = {c["proposed_claim_id"] for c in result["promoted_claims"]}
        assert approved_id in promoted_ids, (
            f"Approved temp claim {approved_id} was not promoted."
        )
        assert edited_id in promoted_ids, (
            f"Edited temp claim {edited_id} was not promoted."
        )
        assert rejected_id not in promoted_ids, (
            f"Rejected temp claim {rejected_id} must not be promoted."
        )
        assert pending_id not in promoted_ids, (
            f"Pending temp claim {pending_id} must not be promoted."
        )
        print("  [OK] approved and edited promoted; rejected and pending excluded")

        # Verify qualitative_claims rows for temp approved and edited.
        qc_rows = _qc_for(supabase, [approved_id, edited_id, rejected_id, pending_id])
        qc_map = {r["proposed_claim_id"]: r for r in qc_rows}

        assert approved_id in qc_map, "Approved row missing from qualitative_claims."
        assert edited_id in qc_map, "Edited row missing from qualitative_claims."
        assert rejected_id not in qc_map, "Rejected row must not be in qualitative_claims."
        assert pending_id not in qc_map, "Pending row must not be in qualitative_claims."

        approved_qc = qc_map[approved_id]
        assert approved_qc["claim"] == "TEMP PROMO TEST — APPROVED", (
            f"Approved claim text mismatch: {approved_qc['claim']!r}."
        )
        assert approved_qc["human_reviewed"] == "Yes"
        assert approved_qc["source_chunk_id"] == SOURCE_CHUNK_ID
        assert approved_qc["document_key"] == DOCUMENT_KEY
        assert approved_qc["ticker"] == TICKER
        print("  [OK] approved row: claim_text used, human_reviewed=Yes, provenance correct")

        edited_qc = qc_map[edited_id]
        assert edited_qc["claim"] == "TEMP PROMO TEST — EDIT (corrected)", (
            f"Edited claim must use edited_claim_text, got: {edited_qc['claim']!r}."
        )
        assert edited_qc["human_reviewed"] == "Yes"
        assert edited_qc["source_chunk_id"] == SOURCE_CHUNK_ID
        assert edited_qc["document_key"] == DOCUMENT_KEY
        print("  [OK] edited row: edited_claim_text used, human_reviewed=Yes, provenance correct")

        # --- Run 2: idempotency ---
        print("\nRun 2: promote_reviewed_claims() again (should skip already-promoted rows)...")
        result2 = promote_reviewed_claims()
        print(
            f"  eligible={result2['eligible_count']}, "
            f"promoted={result2['promoted_count']}, "
            f"skipped={result2['skipped_existing_count']}"
        )

        promoted_ids2 = {c["proposed_claim_id"] for c in result2["promoted_claims"]}
        assert approved_id not in promoted_ids2, (
            f"Approved row {approved_id} was promoted again (duplicate)."
        )
        assert edited_id not in promoted_ids2, (
            f"Edited row {edited_id} was promoted again (duplicate)."
        )

        # Confirm still exactly one row each for approved and edited temp claims.
        qc_rows2 = _qc_for(supabase, [approved_id, edited_id])
        counts = {}
        for r in qc_rows2:
            pid = r["proposed_claim_id"]
            counts[pid] = counts.get(pid, 0) + 1
        assert counts.get(approved_id, 0) == 1, (
            f"Expected 1 qualitative_claims row for approved {approved_id}, "
            f"found {counts.get(approved_id, 0)}."
        )
        assert counts.get(edited_id, 0) == 1, (
            f"Expected 1 qualitative_claims row for edited {edited_id}, "
            f"found {counts.get(edited_id, 0)}."
        )
        print("  [OK] no duplicates after second promotion run")

    finally:
        # --- Cleanup: delete only temp qualitative_claims and temp proposed_claims ---
        supabase.table("qualitative_claims").delete().in_(
            "proposed_claim_id", inserted_ids
        ).execute()
        supabase.table("proposed_claims").delete().in_("id", inserted_ids).execute()

        qc_remaining = _qc_for(supabase, inserted_ids)
        pc_remaining = (
            supabase.table("proposed_claims")
            .select("id")
            .in_("id", inserted_ids)
            .execute()
            .data
        )
        assert len(qc_remaining) == 0, f"Temp qualitative_claims rows not deleted: {qc_remaining}"
        assert len(pc_remaining) == 0, f"Temp proposed_claims rows not deleted: {pc_remaining}"
        print(f"\nCleaned up temp rows {inserted_ids} from both tables.")

    # --- Verify real AVGO approved proposed_claims are untouched ---
    real_avgo = (
        supabase.table("proposed_claims")
        .select("id, review_status")
        .in_("id", [30, 31, 32, 33, 34])
        .execute()
        .data
    )
    assert len(real_avgo) == 5, f"Expected 5 real AVGO rows but found {len(real_avgo)}."
    for row in real_avgo:
        assert row["review_status"] == "approved", (
            f"Real AVGO row id={row['id']} has unexpected status {row['review_status']!r}."
        )
    print(f"Real AVGO proposed_claims {[r['id'] for r in real_avgo]} confirmed untouched.")

    print()
    print(
        "PASS: promotion correctly promotes approved and edited claims, "
        "excludes rejected and pending, and is idempotent."
    )


if __name__ == "__main__":
    main()
