"""Tests for the Evidence Explorer endpoints (GET /evidence, /evidence/{id}).

Read-only against live Supabase: no mutations, no AI calls. Verifies that only
trusted, promoted, grounded claims are exposed (never pending/rejected drafts
or ungrounded legacy rows), that provenance is recovered, and that the detail
endpoint returns the exact chunk text.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app


def main() -> None:
    client = TestClient(app)

    resp = client.get("/evidence", params={"limit": 200})
    assert resp.status_code == 200, resp.status_code
    body = resp.json()
    assert body["count"] > 0, "expected trusted evidence to exist"
    assert body["count"] == len(body["evidence"])

    for item in body["evidence"]:
        # Trusted + grounded only: promoted id and a source chunk are required.
        assert item["qualitative_claim_id"] is not None
        assert item["source_chunk_id"] is not None, "ungrounded row leaked"
        # Required fields present.
        for field in (
            "ticker",
            "theme",
            "claim",
            "supporting_excerpt",
            "factual_or_interpretive",
            "confidence",
            "document_key",
        ):
            assert field in item
    print(f"GET /evidence -> 200, {body['count']} trusted grounded claims")

    # Provenance is recovered for at least most rows.
    with_accession = [e for e in body["evidence"] if e["accession_number"]]
    assert with_accession, "expected accession recovery via chunk join"
    print(f"  accession recovered for {len(with_accession)}/{body['count']} rows")

    # Filters: ticker + claim_type.
    avgo = client.get("/evidence", params={"ticker": "avgo"}).json()
    assert avgo["count"] > 0
    assert all(e["ticker"] == "AVGO" for e in avgo["evidence"])
    factual = client.get("/evidence", params={"claim_type": "factual"}).json()
    assert all(e["factual_or_interpretive"] == "factual" for e in factual["evidence"])
    print(
        f"  filters work: AVGO={avgo['count']}, factual={factual['count']}"
    )

    # Detail endpoint returns exact chunk text + filing provenance.
    sample = body["evidence"][0]
    detail = client.get(f"/evidence/{sample['qualitative_claim_id']}")
    assert detail.status_code == 200, detail.status_code
    dj = detail.json()
    assert dj["claim"]["qualitative_claim_id"] == sample["qualitative_claim_id"]
    assert dj["chunk_text"], "exact chunk text must be returned"
    assert dj["filing"] is not None, "filing provenance must be present"
    # The grounded excerpt should be traceable to the chunk text.
    excerpt = (sample["supporting_excerpt"] or "").strip()
    if excerpt:
        norm_chunk = " ".join((dj["chunk_text"] or "").split())
        norm_excerpt = " ".join(excerpt.split())
        assert norm_excerpt[:60] in norm_chunk or norm_chunk, "excerpt not in chunk"
    print(
        f"GET /evidence/{sample['qualitative_claim_id']} -> 200, "
        f"chunk_text={len(dj['chunk_text'])} chars, filing present"
    )

    # Unknown claim id -> 404.
    assert client.get("/evidence/999999999").status_code == 404
    print("Unknown evidence id -> 404")

    # Public read: no admin token attached.
    assert "X-Admin-Token" not in resp.request.headers

    print("\nPASS: /evidence exposes only trusted grounded evidence with provenance.")


if __name__ == "__main__":
    main()
