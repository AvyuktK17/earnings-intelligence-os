"""Test the analyst-review write endpoints: approve, edit, reject.

Inserts temporary proposed_claims rows tied to a real AVGO exhibit chunk,
exercises the three write endpoints plus error paths, then deletes only the
temporary rows. Real AVGO reviewed claims are never touched. No AI calls.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app

# Protected write endpoints require the admin token; use a private
# temporary one for this test run (never printed).
import secrets as _secrets
os.environ.setdefault("ADMIN_API_TOKEN", _secrets.token_urlsafe(32))
_ADMIN_HEADERS = {"X-Admin-Token": os.environ["ADMIN_API_TOKEN"]}
from src.database import get_supabase_client

ACCESSION = "0001730168-26-000051"
DOCUMENT_KEY = "exhibit:avgo-05032026x8kxex99.htm"
TEMP_THEME = "TEMP_API_TEST_REVIEW"


def insert_temp_claim(supabase, filing_id, chunk, grounded: bool = True) -> int:
    row = {
        "filing_id": filing_id,
        "ticker": "AVGO",
        "accession_number": ACCESSION,
        "document_key": DOCUMENT_KEY,
        "theme": TEMP_THEME,
        "claim_text": "Temporary test claim for API review actions.",
        "supporting_excerpt": "Temporary test excerpt.",
        "source_chunk_index": chunk["chunk_index"] if grounded else None,
        "source_chunk_id": chunk["id"] if grounded else None,
        "claim_type": "factual",
        "confidence": "high",
        "review_status": "pending",
    }
    resp = supabase.table("proposed_claims").insert(row).execute()
    return resp.data[0]["id"]


def main() -> None:
    client = TestClient(app, headers=_ADMIN_HEADERS)
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
    print(f"Using AVGO filing_id={filing_id}, exhibit chunk id={chunk['id']}")

    temp_ids = []
    try:
        approve_id = insert_temp_claim(supabase, filing_id, chunk)
        edit_id = insert_temp_claim(supabase, filing_id, chunk)
        reject_id = insert_temp_claim(supabase, filing_id, chunk)
        ungrounded_id = insert_temp_claim(supabase, filing_id, chunk, grounded=False)
        temp_ids = [approve_id, edit_id, reject_id, ungrounded_id]
        print(f"Inserted temp claims: {temp_ids}\n")

        # --- Approve ---
        response = client.post(
            f"/review-queue/{approve_id}/approve",
            json={"reviewer_notes": "Reviewed against SEC exhibit."},
        )
        assert response.status_code == 200, (
            f"Approve: expected 200, got {response.status_code}: {response.text}"
        )
        row = response.json()
        assert row["id"] == approve_id
        assert row["review_status"] == "approved", row["review_status"]
        assert row["reviewer_notes"] == "Reviewed against SEC exhibit."
        assert row["reviewed_at"], "reviewed_at must be set."
        print(f"POST /review-queue/{approve_id}/approve -> 200, status=approved")

        # --- Edit: preserves original text, saves edited wording ---
        response = client.post(
            f"/review-queue/{edit_id}/edit",
            json={
                "edited_claim_text": "Revised analyst wording.",
                "reviewer_notes": "Clarified wording without changing evidence.",
            },
        )
        assert response.status_code == 200, (
            f"Edit: expected 200, got {response.status_code}: {response.text}"
        )
        row = response.json()
        assert row["review_status"] == "edited", row["review_status"]
        assert row["claim_text"] == "Temporary test claim for API review actions.", (
            "Original claim_text must be preserved."
        )
        assert row["edited_claim_text"] == "Revised analyst wording."
        print(f"POST /review-queue/{edit_id}/edit -> 200, original preserved, edit saved")

        # --- Edit: empty text rejected ---
        response = client.post(
            f"/review-queue/{edit_id}/edit", json={"edited_claim_text": ""}
        )
        assert response.status_code in (400, 422), (
            f"Empty edit: expected 400/422, got {response.status_code}."
        )
        print(f"POST /review-queue/{edit_id}/edit (empty text) -> {response.status_code}")

        # --- Reject ---
        response = client.post(
            f"/review-queue/{reject_id}/reject",
            json={"reviewer_notes": "Not material for the briefing."},
        )
        assert response.status_code == 200, (
            f"Reject: expected 200, got {response.status_code}: {response.text}"
        )
        row = response.json()
        assert row["review_status"] == "rejected", row["review_status"]
        print(f"POST /review-queue/{reject_id}/reject -> 200, status=rejected")

        # --- Approve ungrounded claim -> 400 ---
        response = client.post(f"/review-queue/{ungrounded_id}/approve")
        assert response.status_code == 400, (
            f"Ungrounded approve: expected 400, got {response.status_code}."
        )
        print(f"POST /review-queue/{ungrounded_id}/approve (ungrounded) -> 400")

        # --- Reject ungrounded claim is allowed ---
        response = client.post(f"/review-queue/{ungrounded_id}/reject")
        assert response.status_code == 200, (
            f"Ungrounded reject: expected 200, got {response.status_code}."
        )
        print(f"POST /review-queue/{ungrounded_id}/reject (ungrounded) -> 200")

        # --- Invalid claim id -> 404 ---
        response = client.post("/review-queue/99999999/approve")
        assert response.status_code == 404, (
            f"Invalid id: expected 404, got {response.status_code}."
        )
        print("POST /review-queue/99999999/approve -> 404")

    finally:
        if temp_ids:
            supabase.table("proposed_claims").delete().in_("id", temp_ids).execute()
            remaining = (
                supabase.table("proposed_claims")
                .select("id")
                .in_("id", temp_ids)
                .execute()
                .data
            )
            assert len(remaining) == 0, f"Temp rows not fully deleted: {remaining}"
            print(f"\nCleaned up temp proposed_claims rows {temp_ids}.")

    print()
    print(
        "PASS: approve, edit, and reject endpoints work, grounding and "
        "missing-claim errors map to 400/404, and temp rows were removed."
    )


if __name__ == "__main__":
    main()
