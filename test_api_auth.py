"""Test admin-token protection on the analyst write endpoints.

Uses a temporary random token injected through the environment (never
printed). Verifies GET endpoints stay public, missing/incorrect tokens are
rejected with 401, the correct token allows a temporary review action, and
a missing server-side ADMIN_API_TOKEN yields a controlled 500. Temporary
rows are cleaned up; real claims are never modified.
"""

import sys
import os
import secrets
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app
from src.database import get_supabase_client

ACCESSION = "0001730168-26-000051"
DOCUMENT_KEY = "exhibit:avgo-05032026x8kxex99.htm"

TEMP_TOKEN = secrets.token_urlsafe(32)


def insert_temp_claim(supabase) -> int:
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
    row = {
        "filing_id": filing_id,
        "ticker": "AVGO",
        "accession_number": ACCESSION,
        "document_key": DOCUMENT_KEY,
        "theme": "TEMP_API_TEST_AUTH",
        "claim_text": "Temporary test claim for auth test.",
        "supporting_excerpt": "Temporary test excerpt.",
        "source_chunk_index": chunk["chunk_index"],
        "source_chunk_id": chunk["id"],
        "claim_type": "factual",
        "confidence": "high",
        "review_status": "pending",
    }
    return supabase.table("proposed_claims").insert(row).execute().data[0]["id"]


def main() -> None:
    client = TestClient(app)
    supabase = get_supabase_client()

    with mock.patch.dict(os.environ, {"ADMIN_API_TOKEN": TEMP_TOKEN}):
        # --- GET endpoints stay public (no token) ---
        for path in ("/health", "/filings?limit=1", "/review-queue", "/companies"):
            response = client.get(path)
            assert response.status_code == 200, (
                f"GET {path} must stay public, got {response.status_code}."
            )
        print("GET /health, /filings, /review-queue, /companies -> 200 without token")

        # --- POST without token -> 401 ---
        response = client.post("/claims/promote")
        assert response.status_code == 401, (
            f"POST without token: expected 401, got {response.status_code}."
        )
        assert response.json()["detail"] == "Admin token missing or invalid."
        print("POST /claims/promote (no token) -> 401")

        # --- POST with incorrect token -> 401 ---
        response = client.post(
            "/claims/promote", headers={"X-Admin-Token": "wrong-token"}
        )
        assert response.status_code == 401, (
            f"POST with bad token: expected 401, got {response.status_code}."
        )
        print("POST /claims/promote (incorrect token) -> 401")

        # --- Correct token allows a temporary review action ---
        temp_id = insert_temp_claim(supabase)
        try:
            response = client.post(
                f"/review-queue/{temp_id}/approve",
                headers={"X-Admin-Token": TEMP_TOKEN},
                json={"reviewer_notes": "Auth test approval."},
            )
            assert response.status_code == 200, (
                f"POST with correct token: expected 200, "
                f"got {response.status_code}: {response.text}"
            )
            assert response.json()["review_status"] == "approved"
            print(f"POST /review-queue/{temp_id}/approve (correct token) -> 200")
        finally:
            supabase.table("proposed_claims").delete().eq("id", temp_id).execute()
            remaining = (
                supabase.table("proposed_claims")
                .select("id")
                .eq("id", temp_id)
                .execute()
                .data
            )
            assert not remaining, f"Temp claim {temp_id} not deleted."
            print(f"Cleaned up temp proposed_claims row {temp_id}.")

    # --- Missing server-side ADMIN_API_TOKEN -> controlled 500 ---
    with mock.patch.dict(os.environ):
        os.environ.pop("ADMIN_API_TOKEN", None)
        response = client.post("/claims/promote")
        assert response.status_code == 500, (
            f"Missing server token: expected 500, got {response.status_code}."
        )
        detail = response.json()["detail"]
        assert detail == "Server configuration error.", (
            f"500 detail must be generic, got {detail!r}."
        )
        assert "ADMIN_API_TOKEN" not in response.text, (
            "500 response must not name the missing variable."
        )
        print("POST /claims/promote (server token unset) -> 500 "
              "with generic message")

        # GETs still work even when the server token is unset.
        response = client.get("/health")
        assert response.status_code == 200
        print("GET /health (server token unset) -> 200")

    print()
    print(
        "PASS: write endpoints require the admin token, reads stay public, "
        "and a missing server-side token fails closed with a generic 500."
    )


if __name__ == "__main__":
    main()
