"""Test the /review-queue endpoint.

Uses FastAPI TestClient against live Supabase data. Read-only: no AI calls,
no row mutations. Verifies that only grounded pending claims are exposed and
that ungrounded legacy pending rows never appear.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app
from src.database import get_supabase_client


def main() -> None:
    client = TestClient(app)
    supabase = get_supabase_client()

    response = client.get("/review-queue")
    assert response.status_code == 200, (
        f"Expected 200 from /review-queue, got {response.status_code}."
    )
    body = response.json()

    # --- Structure ---
    assert "count" in body, "Response must include 'count'."
    assert "claims" in body, "Response must include 'claims'."
    assert body["count"] == len(body["claims"]), "count must match claims length."
    print(f"GET /review-queue -> 200, count={body['count']}")

    # --- Every returned claim is pending and grounded ---
    for claim in body["claims"]:
        assert claim["review_status"] == "pending", (
            f"Non-pending claim leaked into queue: {claim['review_status']!r}."
        )
        assert claim["source_chunk_id"] is not None, (
            f"Ungrounded claim leaked into queue: id={claim['id']}."
        )
    print(f"  [OK] all {body['count']} returned claims are pending and grounded")

    # --- Ungrounded legacy pending rows must not appear ---
    ungrounded = (
        supabase.table("proposed_claims")
        .select("id")
        .eq("review_status", "pending")
        .is_("source_chunk_id", "null")
        .execute()
        .data
    )
    ungrounded_ids = {row["id"] for row in ungrounded}
    returned_ids = {claim["id"] for claim in body["claims"]}
    leaked = ungrounded_ids & returned_ids
    assert not leaked, f"Ungrounded legacy claims leaked into the queue: {leaked}."
    print(
        f"  [OK] {len(ungrounded_ids)} ungrounded legacy pending rows exist in "
        f"proposed_claims and none appear in the queue"
    )

    print()
    print(
        "PASS: review queue exposes only grounded pending claims and hides "
        "ungrounded legacy rows."
    )


if __name__ == "__main__":
    main()
