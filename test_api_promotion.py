"""Test the POST /claims/promote endpoint in global and scoped modes.

Global mode: inserts four temporary proposed_claims rows (approved, edited,
rejected, pending) tied to a real AVGO exhibit chunk, promotes via the API,
verifies only the approved and edited rows reach qualitative_claims, reruns
to prove idempotency.

Scoped mode: inserts temporary approved claims for two different filings and
verifies a filing-scoped promote touches only the matching row, then that
global mode still promotes the rest.

Every temporary trusted and proposed row is deleted afterward. Real trusted
AVGO claims are never touched. No AI calls.
"""

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app
from src.database import get_supabase_client

ACCESSION = "0001730168-26-000051"
DOCUMENT_KEY = "exhibit:avgo-05032026x8kxex99.htm"
TEMP_THEME = "TEMP_API_TEST_PROMOTION"


def insert_temp_claim(supabase, filing_id, chunk, review_status, edited_text=None,
                      ticker="AVGO", accession=ACCESSION) -> int:
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "filing_id": filing_id,
        "ticker": ticker,
        "accession_number": accession,
        "document_key": DOCUMENT_KEY,
        "theme": TEMP_THEME,
        "claim_text": f"Temporary {review_status} claim for promotion test.",
        "supporting_excerpt": "Temporary test excerpt.",
        "source_chunk_index": chunk["chunk_index"],
        "source_chunk_id": chunk["id"],
        "claim_type": "factual",
        "confidence": "high",
        "review_status": review_status,
        "edited_claim_text": edited_text,
        "reviewed_at": None if review_status == "pending" else now,
    }
    resp = supabase.table("proposed_claims").insert(row).execute()
    return resp.data[0]["id"]


def fetch_trusted_by_proposed_ids(supabase, proposed_ids):
    return (
        supabase.table("qualitative_claims")
        .select("proposed_claim_id, claim, theme")
        .in_("proposed_claim_id", proposed_ids)
        .execute()
        .data
    )


def main() -> None:
    client = TestClient(app)
    supabase = get_supabase_client()

    filing_id = (
        supabase.table("filings")
        .select("id")
        .eq("accession_number", ACCESSION)
        .execute()
        .data[0]["id"]
    )
    chunk = (
        supabase.table("filing_chunks")
        .select("id, chunk_index")
        .eq("accession_number", ACCESSION)
        .eq("document_key", DOCUMENT_KEY)
        .order("chunk_index")
        .limit(1)
        .execute()
        .data[0]
    )

    # Snapshot the real trusted rows so we can prove they are untouched.
    real_before = (
        supabase.table("qualitative_claims")
        .select("proposed_claim_id, claim, promoted_at")
        .not_.is_("proposed_claim_id", "null")
        .execute()
        .data
    )
    real_ids = {r["proposed_claim_id"] for r in real_before}
    print(f"Real trusted promoted rows before test: {sorted(real_ids)}")

    temp_ids = []
    try:
        approved_id = insert_temp_claim(supabase, filing_id, chunk, "approved")
        edited_id = insert_temp_claim(
            supabase, filing_id, chunk, "edited", edited_text="Edited trusted wording."
        )
        rejected_id = insert_temp_claim(supabase, filing_id, chunk, "rejected")
        pending_id = insert_temp_claim(supabase, filing_id, chunk, "pending")
        temp_ids = [approved_id, edited_id, rejected_id, pending_id]
        promotable_ids = [approved_id, edited_id]
        print(f"Inserted temp claims: approved={approved_id}, edited={edited_id}, "
              f"rejected={rejected_id}, pending={pending_id}\n")

        # --- First promotion run ---
        response = client.post("/claims/promote")
        assert response.status_code == 200, (
            f"Expected 200 from /claims/promote, got {response.status_code}."
        )
        body = response.json()
        for key in ("eligible_count", "promoted_count", "skipped_existing_count",
                    "promoted_claims"):
            assert key in body, f"Response missing {key!r}."
        assert body["promoted_count"] == 2, (
            f"Expected exactly the 2 temp claims promoted, got {body['promoted_count']}."
        )
        promoted_ids = {c["proposed_claim_id"] for c in body["promoted_claims"]}
        assert promoted_ids == set(promotable_ids), (
            f"Promoted ids {promoted_ids} != expected {set(promotable_ids)}."
        )
        assert body["skipped_existing_count"] >= len(real_ids), (
            "Real already-promoted claims must be skipped, not re-promoted."
        )
        print(f"POST /claims/promote -> 200: eligible={body['eligible_count']}, "
              f"promoted={body['promoted_count']}, "
              f"skipped_existing={body['skipped_existing_count']}")

        # --- Trusted rows exist; edited wording was used ---
        trusted = fetch_trusted_by_proposed_ids(supabase, promotable_ids)
        assert len(trusted) == 2, f"Expected 2 trusted rows, found {len(trusted)}."
        edited_row = next(
            r for r in trusted if r["proposed_claim_id"] == edited_id
        )
        assert edited_row["claim"] == "Edited trusted wording.", (
            "Edited claim must promote the reviewer's wording."
        )
        print("  [OK] approved and edited claims promoted; edited wording used")

        # --- Rejected and pending claims must not promote ---
        not_promoted = fetch_trusted_by_proposed_ids(
            supabase, [rejected_id, pending_id]
        )
        assert not not_promoted, (
            f"Rejected/pending claims leaked into qualitative_claims: {not_promoted}."
        )
        print("  [OK] rejected and pending claims were not promoted")

        # --- Second run: no duplicates ---
        response = client.post("/claims/promote")
        assert response.status_code == 200
        body2 = response.json()
        assert body2["promoted_count"] == 0, (
            f"Rerun must promote nothing, got {body2['promoted_count']}."
        )
        trusted_after = fetch_trusted_by_proposed_ids(supabase, promotable_ids)
        assert len(trusted_after) == 2, (
            f"Rerun created duplicates: {len(trusted_after)} rows."
        )
        print(f"POST /claims/promote (rerun) -> 200: promoted=0, no duplicates")

    finally:
        if temp_ids:
            supabase.table("qualitative_claims").delete().in_(
                "proposed_claim_id", temp_ids
            ).execute()
            supabase.table("proposed_claims").delete().in_("id", temp_ids).execute()
            leftover_trusted = fetch_trusted_by_proposed_ids(supabase, temp_ids)
            leftover_proposed = (
                supabase.table("proposed_claims")
                .select("id")
                .in_("id", temp_ids)
                .execute()
                .data
            )
            assert not leftover_trusted and not leftover_proposed, (
                f"Temp rows not fully deleted: trusted={leftover_trusted}, "
                f"proposed={leftover_proposed}"
            )
            print(f"\nCleaned up temp trusted and proposed rows for {temp_ids}.")

    # --- Real trusted rows are untouched ---
    real_after = (
        supabase.table("qualitative_claims")
        .select("proposed_claim_id, claim, promoted_at")
        .not_.is_("proposed_claim_id", "null")
        .execute()
        .data
    )
    assert sorted(real_after, key=lambda r: r["proposed_claim_id"]) == sorted(
        real_before, key=lambda r: r["proposed_claim_id"]
    ), "Real trusted AVGO claims changed during the test."
    print(f"Real trusted promoted rows after test: "
          f"{sorted(r['proposed_claim_id'] for r in real_after)} (unchanged)")

    print()
    print(
        "PASS: promotion endpoint promotes only approved and edited grounded "
        "claims, is idempotent, and real trusted claims are untouched."
    )


def scoped_main() -> None:
    """Verify filing-scoped promotion touches only matching temp rows."""
    client = TestClient(app)
    supabase = get_supabase_client()

    avgo_filing_id = (
        supabase.table("filings")
        .select("id")
        .eq("accession_number", ACCESSION)
        .execute()
        .data[0]["id"]
    )
    nvda_filing = (
        supabase.table("filings")
        .select("id, accession_number")
        .eq("ticker", "NVDA")
        .limit(1)
        .execute()
        .data[0]
    )
    chunk = (
        supabase.table("filing_chunks")
        .select("id, chunk_index")
        .eq("accession_number", ACCESSION)
        .eq("document_key", DOCUMENT_KEY)
        .order("chunk_index")
        .limit(1)
        .execute()
        .data[0]
    )

    real_before = (
        supabase.table("qualitative_claims")
        .select("proposed_claim_id, claim, promoted_at")
        .not_.is_("proposed_claim_id", "null")
        .execute()
        .data
    )

    temp_ids = []
    try:
        avgo_id = insert_temp_claim(supabase, avgo_filing_id, chunk, "approved")
        nvda_id = insert_temp_claim(
            supabase, nvda_filing["id"], chunk, "approved",
            ticker="NVDA", accession=nvda_filing["accession_number"],
        )
        temp_ids = [avgo_id, nvda_id]
        print(f"\nInserted temp approved claims: AVGO={avgo_id}, "
              f"NVDA={nvda_id} ({nvda_filing['accession_number']})")

        # --- Filing-scoped promote (lowercase ticker must normalize) ---
        response = client.post(
            "/claims/promote",
            json={"ticker": "avgo", "accession_number": ACCESSION},
        )
        assert response.status_code == 200, (
            f"Scoped promote: expected 200, got {response.status_code}."
        )
        body = response.json()
        promoted_ids = {c["proposed_claim_id"] for c in body["promoted_claims"]}
        assert promoted_ids == {avgo_id}, (
            f"Scoped promote must touch only the AVGO temp claim, got {promoted_ids}."
        )
        print(f"POST /claims/promote (scoped to AVGO/{ACCESSION}) -> 200: "
              f"promoted={body['promoted_count']} (only the matching temp claim)")

        # --- Nonmatching temp row untouched ---
        nvda_trusted = fetch_trusted_by_proposed_ids(supabase, [nvda_id])
        assert not nvda_trusted, (
            f"Out-of-scope NVDA temp claim was promoted: {nvda_trusted}."
        )
        nvda_row = (
            supabase.table("proposed_claims")
            .select("review_status")
            .eq("id", nvda_id)
            .execute()
            .data[0]
        )
        assert nvda_row["review_status"] == "approved", (
            "Out-of-scope temp claim must remain approved and unpromoted."
        )
        print("  [OK] out-of-scope NVDA temp claim untouched")

        # --- Global mode still works: picks up the NVDA leftover ---
        response = client.post("/claims/promote")
        assert response.status_code == 200
        body = response.json()
        promoted_ids = {c["proposed_claim_id"] for c in body["promoted_claims"]}
        assert promoted_ids == {nvda_id}, (
            f"Global promote should pick up the NVDA temp claim, got {promoted_ids}."
        )
        print(f"POST /claims/promote (global, no body) -> 200: "
              f"promoted={body['promoted_count']} (the remaining temp claim)")

    finally:
        if temp_ids:
            supabase.table("qualitative_claims").delete().in_(
                "proposed_claim_id", temp_ids
            ).execute()
            supabase.table("proposed_claims").delete().in_("id", temp_ids).execute()
            print(f"Cleaned up temp trusted and proposed rows for {temp_ids}.")

    real_after = (
        supabase.table("qualitative_claims")
        .select("proposed_claim_id, claim, promoted_at")
        .not_.is_("proposed_claim_id", "null")
        .execute()
        .data
    )
    assert sorted(real_after, key=lambda r: r["proposed_claim_id"]) == sorted(
        real_before, key=lambda r: r["proposed_claim_id"]
    ), "Real trusted AVGO claims changed during the scoped test."
    print("Real trusted promoted rows unchanged.")

    print()
    print(
        "PASS: scoped promotion promotes only matching rows, leaves "
        "out-of-scope rows untouched, and global mode still works."
    )


if __name__ == "__main__":
    main()
    scoped_main()
