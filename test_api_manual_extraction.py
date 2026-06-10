"""Tests for POST /extraction-ready/{accession_number}/extract and the
promotion-driven "approved" lifecycle.

Gemini is monkeypatched at the app level — no free-tier quota is consumed.
Uses temporary rows (cleaned up in finally) and proves the real trusted
AVGO claims stay byte-identical throughout.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from unittest import mock

from fastapi.testclient import TestClient

from app.main import app

import secrets as _secrets

os.environ.setdefault("ADMIN_API_TOKEN", _secrets.token_urlsafe(32))
_ADMIN_HEADERS = {"X-Admin-Token": os.environ["ADMIN_API_TOKEN"]}

from src.database import get_supabase_client
from src.ready_filing_extraction import (
    ClaimExtractionError,
    ClaimExtractionQuotaError,
)

TEMP_ACCESSION = "0000000000-99-001111"
TEMP_TICKER = "ZZZT"
MISSING_ACCESSION = "0000000000-00-000000"


def _trusted_avgo_snapshot(supabase) -> list[dict]:
    return (
        supabase.table("qualitative_claims")
        .select("*")
        .eq("ticker", "AVGO")
        .not_.is_("proposed_claim_id", "null")
        .order("proposed_claim_id", desc=False)
        .execute()
        .data
    )


def main() -> None:
    supabase = get_supabase_client()
    client = TestClient(app, headers=_ADMIN_HEADERS)
    anonymous = TestClient(app)

    trusted_before = _trusted_avgo_snapshot(supabase)

    filing_id = None
    chunk_id = None
    claim_ids: list[int] = []

    try:
        # --- Auth -------------------------------------------------------------
        response = anonymous.post(
            f"/extraction-ready/{MISSING_ACCESSION}/extract"
        )
        assert response.status_code == 401, f"Got {response.status_code}."
        response = anonymous.post(
            f"/extraction-ready/{MISSING_ACCESSION}/extract",
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Admin token missing or invalid."
        print("Missing/wrong admin token -> 401.")

        # --- Body validation ----------------------------------------------------
        for bad in (0, 11):
            response = client.post(
                f"/extraction-ready/{MISSING_ACCESSION}/extract",
                json={"max_claims": bad},
            )
            assert response.status_code == 422, (
                f"max_claims={bad} should be 422, got {response.status_code}."
            )
        print("max_claims outside 1-10 -> 422.")

        # --- Missing filing -----------------------------------------------------
        response = client.post(f"/extraction-ready/{MISSING_ACCESSION}/extract")
        assert response.status_code == 404, f"Got {response.status_code}."
        print("Unknown accession -> 404.")

        # --- Filing without a processed exhibit ----------------------------------
        filing_id = (
            supabase.table("filings")
            .insert(
                {
                    "ticker": TEMP_TICKER,
                    "accession_number": TEMP_ACCESSION,
                    "form": "8-K",
                    "filing_date": "2000-01-01",
                    "processing_status": "chunked",
                    "sec_url": "https://example.invalid/temp-api-extraction",
                }
            )
            .execute()
            .data[0]["id"]
        )
        response = client.post(f"/extraction-ready/{TEMP_ACCESSION}/extract")
        assert response.status_code == 400, f"Got {response.status_code}."
        assert "no processed earnings-release exhibit" in response.json()["detail"]
        print("Filing without processed exhibit -> 400.")

        # --- Success / quota / generic failure (extraction patched) -------------
        fake_result = {
            "ticker": TEMP_TICKER,
            "accession_number": TEMP_ACCESSION,
            "document_key": "exhibit:zzzt-temp-pr.htm",
            "proposed_claim_count": 3,
            "skipped_invalid_count": 0,
            "proposed_claims": [],
            "claim_extraction_status": "pending_review",
        }
        with mock.patch(
            "app.main.extract_claims_for_ready_filing", return_value=fake_result
        ) as patched:
            response = client.post(
                f"/extraction-ready/{TEMP_ACCESSION}/extract",
                json={"max_claims": 7},
            )
        assert response.status_code == 200
        assert response.json()["proposed_claim_count"] == 3
        patched.assert_called_once_with(TEMP_ACCESSION, max_claims=7)
        print("Success -> 200 with the extraction result; max_claims forwarded.")

        with mock.patch(
            "app.main.extract_claims_for_ready_filing",
            side_effect=ClaimExtractionQuotaError(
                "Gemini API quota or rate limit reached."
            ),
        ):
            response = client.post(f"/extraction-ready/{TEMP_ACCESSION}/extract")
        assert response.status_code == 429, f"Got {response.status_code}."
        assert "quota" in response.json()["detail"]
        print("Quota failure -> 429.")

        with mock.patch(
            "app.main.extract_claims_for_ready_filing",
            side_effect=ClaimExtractionError(
                "Claim extraction failed unexpectedly."
            ),
        ):
            response = client.post(f"/extraction-ready/{TEMP_ACCESSION}/extract")
        assert response.status_code == 500
        body_text = response.text
        for secret_marker in ("GEMINI_API_KEY", "Traceback", "google.genai"):
            assert secret_marker not in body_text
        print("Unexpected failure -> safe 500 without internals.")

        # --- Promotion marks a fully reviewed filing approved --------------------
        supabase.table("filings").update(
            {"claim_extraction_status": "pending_review"}
        ).eq("id", filing_id).execute()

        chunk_id = (
            supabase.table("filing_chunks")
            .insert(
                {
                    "filing_id": filing_id,
                    "ticker": TEMP_TICKER,
                    "accession_number": TEMP_ACCESSION,
                    "document_key": "exhibit:zzzt-temp-pr.htm",
                    "chunk_index": 0,
                    "chunk_text": "TEMP LIFECYCLE CHUNK",
                    "character_count": 20,
                }
            )
            .execute()
            .data[0]["id"]
        )
        for theme, status in (("TEMP LIFECYCLE A", "approved"), ("TEMP LIFECYCLE B", "pending")):
            claim_ids.append(
                supabase.table("proposed_claims")
                .insert(
                    {
                        "filing_id": filing_id,
                        "ticker": TEMP_TICKER,
                        "accession_number": TEMP_ACCESSION,
                        "document_key": "exhibit:zzzt-temp-pr.htm",
                        "theme": theme,
                        "claim_text": "temp",
                        "supporting_excerpt": "TEMP LIFECYCLE CHUNK",
                        "source_chunk_index": 0,
                        "source_chunk_id": chunk_id,
                        "claim_type": "factual",
                        "confidence": "low",
                        "review_status": status,
                    }
                )
                .execute()
                .data[0]["id"]
            )

        # One claim still pending -> promotion must NOT mark approved.
        response = client.post(
            "/claims/promote", json={"accession_number": TEMP_ACCESSION}
        )
        assert response.status_code == 200
        result = response.json()
        assert result["promoted_count"] == 1
        assert result["approved_filings"] == [], (
            "Filing was marked approved while a grounded pending row remained."
        )
        status = (
            supabase.table("filings")
            .select("claim_extraction_status")
            .eq("id", filing_id)
            .execute()
            .data[0]["claim_extraction_status"]
        )
        assert status == "pending_review", f"Got {status!r}."
        print("Promotion with a pending grounded row left -> not approved.")

        # Review the second claim, promote again -> approved.
        supabase.table("proposed_claims").update(
            {"review_status": "approved"}
        ).eq("id", claim_ids[1]).execute()
        response = client.post(
            "/claims/promote", json={"accession_number": TEMP_ACCESSION}
        )
        assert response.status_code == 200
        result = response.json()
        assert result["promoted_count"] == 1
        assert result["skipped_existing_count"] == 1
        assert result["approved_filings"] == [TEMP_ACCESSION]
        status = (
            supabase.table("filings")
            .select("claim_extraction_status")
            .eq("id", filing_id)
            .execute()
            .data[0]["claim_extraction_status"]
        )
        assert status == "approved", f"Got {status!r}."
        print("Promotion of a fully reviewed filing -> approved.")

        # --- Enriched extraction-ready payload -----------------------------------
        response = client.get("/extraction-ready")
        assert response.status_code == 200
        sample = response.json()["filings"][0]
        for field in (
            "claim_extraction_status",
            "claim_extracted_at",
            "claim_extraction_error",
            "pending_grounded_claim_count",
            "trusted_promoted_claim_count",
            "latest_brief_version",
        ):
            assert field in sample, f"/extraction-ready missing {field}."
        print("/extraction-ready exposes the extraction-lifecycle fields.")

        trusted_after = _trusted_avgo_snapshot(supabase)
        assert trusted_after == trusted_before, "Trusted AVGO claims changed."
        print("Real trusted AVGO claims are byte-identical.")

    finally:
        if claim_ids:
            supabase.table("qualitative_claims").delete().in_(
                "proposed_claim_id", claim_ids
            ).execute()
        supabase.table("proposed_claims").delete().eq(
            "accession_number", TEMP_ACCESSION
        ).execute()
        if chunk_id is not None:
            supabase.table("filing_chunks").delete().eq("id", chunk_id).execute()
        if filing_id is not None:
            supabase.table("filings").delete().eq("id", filing_id).execute()
        for table in ("proposed_claims", "filing_chunks", "filings"):
            leftovers = (
                supabase.table(table)
                .select("*")
                .eq("accession_number", TEMP_ACCESSION)
                .execute()
                .data
            )
            assert not leftovers, f"Temporary {table} rows were not cleaned up."
        if claim_ids:
            leftovers = (
                supabase.table("qualitative_claims")
                .select("proposed_claim_id")
                .in_("proposed_claim_id", claim_ids)
                .execute()
                .data
            )
            assert not leftovers, "Temporary qualitative_claims rows remain."

    print()
    print(
        "PASS: protected extraction endpoint enforces auth, validation, and "
        "error mapping; promotion advances fully reviewed filings to "
        "approved; trusted AVGO claims untouched; no Gemini quota consumed."
    )


if __name__ == "__main__":
    main()
