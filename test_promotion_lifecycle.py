"""Tests for the promotion-driven claim-extraction lifecycle.

Proves with temporary rows that filing-scoped promotion marks the matching
filing "approved" exactly when no grounded pending drafts remain: rejected
rows and ungrounded legacy pending rows never block approval, one grounded
pending row does, other filings are untouched, and reruns are idempotent.
No AI calls; no real filings or trusted claims modified.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.claim_promotion import promote_reviewed_claims
from src.database import get_supabase_client

ACC_A = "0000000000-99-004444"  # fully reviewed filing
ACC_B = "0000000000-99-005555"  # filing with one grounded pending draft
TEMP_TICKER = "ZZZT"


def _make_filing(supabase, accession: str) -> int:
    return (
        supabase.table("filings")
        .insert(
            {
                "ticker": TEMP_TICKER,
                "accession_number": accession,
                "form": "8-K",
                "filing_date": "2000-01-01",
                "processing_status": "chunked",
                "sec_url": f"https://example.invalid/{accession}",
                "claim_extraction_status": "pending_review",
            }
        )
        .execute()
        .data[0]["id"]
    )


def _make_chunk(supabase, filing_id: int, accession: str) -> int:
    return (
        supabase.table("filing_chunks")
        .insert(
            {
                "filing_id": filing_id,
                "ticker": TEMP_TICKER,
                "accession_number": accession,
                "document_key": "exhibit:zzzt-lifecycle.htm",
                "chunk_index": 0,
                "chunk_text": "TEMP LIFECYCLE CHUNK",
                "character_count": 20,
            }
        )
        .execute()
        .data[0]["id"]
    )


def _make_claim(
    supabase,
    filing_id: int,
    accession: str,
    theme: str,
    review_status: str,
    source_chunk_id: int | None,
) -> int:
    return (
        supabase.table("proposed_claims")
        .insert(
            {
                "filing_id": filing_id,
                "ticker": TEMP_TICKER,
                "accession_number": accession,
                "document_key": "exhibit:zzzt-lifecycle.htm",
                "theme": theme,
                "claim_text": "temp lifecycle claim",
                "edited_claim_text": (
                    "temp edited" if review_status == "edited" else None
                ),
                "supporting_excerpt": "TEMP LIFECYCLE CHUNK",
                "source_chunk_index": 0,
                "source_chunk_id": source_chunk_id,
                "claim_type": "factual",
                "confidence": "low",
                "review_status": review_status,
            }
        )
        .execute()
        .data[0]["id"]
    )


def _status(supabase, accession: str) -> str:
    return (
        supabase.table("filings")
        .select("claim_extraction_status")
        .eq("accession_number", accession)
        .execute()
        .data[0]["claim_extraction_status"]
    )


def main() -> None:
    supabase = get_supabase_client()
    claim_ids: list[int] = []
    filing_ids: list[int] = []
    chunk_ids: list[int] = []

    try:
        # Filing A: approved + edited + rejected grounded claims, plus an
        # ungrounded legacy pending row — fully reviewed in practice.
        filing_a = _make_filing(supabase, ACC_A)
        filing_ids.append(filing_a)
        chunk_a = _make_chunk(supabase, filing_a, ACC_A)
        chunk_ids.append(chunk_a)
        claim_ids.append(_make_claim(supabase, filing_a, ACC_A, "A approved", "approved", chunk_a))
        claim_ids.append(_make_claim(supabase, filing_a, ACC_A, "A edited", "edited", chunk_a))
        claim_ids.append(_make_claim(supabase, filing_a, ACC_A, "A rejected", "rejected", chunk_a))
        claim_ids.append(_make_claim(supabase, filing_a, ACC_A, "A legacy", "pending", None))

        # Filing B: one approved and one still-pending grounded claim.
        filing_b = _make_filing(supabase, ACC_B)
        filing_ids.append(filing_b)
        chunk_b = _make_chunk(supabase, filing_b, ACC_B)
        chunk_ids.append(chunk_b)
        claim_ids.append(_make_claim(supabase, filing_b, ACC_B, "B approved", "approved", chunk_b))
        claim_ids.append(_make_claim(supabase, filing_b, ACC_B, "B pending", "pending", chunk_b))

        # --- Scoped promotion of A: approved despite rejected + legacy rows ---
        result = promote_reviewed_claims(accession_number=ACC_A)
        assert result["eligible_count"] == 2, result
        assert result["promoted_count"] == 2, result
        assert result["approved_filings"] == [ACC_A], result
        assert _status(supabase, ACC_A) == "approved"
        print(
            "Filing A approved: rejected and ungrounded legacy pending rows "
            "did not block."
        )

        # --- Filing B untouched by A's promotion --------------------------------
        assert _status(supabase, ACC_B) == "pending_review", (
            "Scoped promotion of A changed filing B."
        )
        b_trusted = (
            supabase.table("qualitative_claims")
            .select("proposed_claim_id", count="exact")
            .in_("proposed_claim_id", claim_ids[4:])
            .execute()
            .count
            or 0
        )
        assert b_trusted == 0, "A-scoped promotion promoted B claims."
        print("Filing B untouched by A-scoped promotion.")

        # --- Scoped promotion of B: grounded pending row blocks approval --------
        result = promote_reviewed_claims(accession_number=ACC_B)
        assert result["promoted_count"] == 1, result
        assert result["approved_filings"] == [], result
        assert _status(supabase, ACC_B) == "pending_review", (
            "Filing B was approved while a grounded pending draft remained."
        )
        print("Filing B blocked by its grounded pending draft.")

        # --- Review B's last draft; rerun scoped promotion -> approved ----------
        supabase.table("proposed_claims").update(
            {"review_status": "rejected"}
        ).eq("theme", "B pending").eq("accession_number", ACC_B).execute()
        result = promote_reviewed_claims(accession_number=ACC_B)
        assert result["promoted_count"] == 0, result
        assert result["skipped_existing_count"] == 1, result
        assert result["approved_filings"] == [ACC_B], result
        assert _status(supabase, ACC_B) == "approved"
        print(
            "Filing B approved after its last draft was reviewed — promoted "
            "rows stayed idempotent (skipped, not duplicated)."
        )

        # --- Rerunning A stays idempotent and approved ---------------------------
        result = promote_reviewed_claims(accession_number=ACC_A)
        assert result["promoted_count"] == 0, result
        assert result["skipped_existing_count"] == 2, result
        assert result["approved_filings"] == [ACC_A], result
        assert _status(supabase, ACC_A) == "approved"
        a_trusted = (
            supabase.table("qualitative_claims")
            .select("proposed_claim_id", count="exact")
            .in_("proposed_claim_id", claim_ids[:4])
            .execute()
            .count
            or 0
        )
        assert a_trusted == 2, f"Expected 2 trusted A rows, got {a_trusted}."
        print("Rerun on A: idempotent, still approved, no duplicates.")

    finally:
        if claim_ids:
            supabase.table("qualitative_claims").delete().in_(
                "proposed_claim_id", claim_ids
            ).execute()
        for accession in (ACC_A, ACC_B):
            supabase.table("proposed_claims").delete().eq(
                "accession_number", accession
            ).execute()
            supabase.table("filing_chunks").delete().eq(
                "accession_number", accession
            ).execute()
            supabase.table("filings").delete().eq(
                "accession_number", accession
            ).execute()
        for accession in (ACC_A, ACC_B):
            for table in ("proposed_claims", "filing_chunks", "filings"):
                leftovers = (
                    supabase.table(table)
                    .select("*")
                    .eq("accession_number", accession)
                    .execute()
                    .data
                )
                assert not leftovers, f"Temp {table} rows remain for {accession}."
        if claim_ids:
            leftovers = (
                supabase.table("qualitative_claims")
                .select("proposed_claim_id")
                .in_("proposed_claim_id", claim_ids)
                .execute()
                .data
            )
            assert not leftovers, "Temp qualitative_claims rows remain."

    print()
    print(
        "PASS: scoped promotion approves exactly the fully reviewed filing — "
        "rejected and ungrounded rows never block, grounded pending rows do, "
        "other filings stay untouched, and reruns are idempotent."
    )


if __name__ == "__main__":
    main()
