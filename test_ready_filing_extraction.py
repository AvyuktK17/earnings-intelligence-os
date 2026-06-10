"""Tests for extract_claims_for_ready_filing.

The Gemini-backed extractor is monkeypatched everywhere, so no free-tier
quota is consumed. Uses temporary filing / document / claim rows and cleans
them all up. No real filings or trusted claims are touched.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from unittest import mock

from src.database import get_supabase_client
from src.ready_filing_extraction import (
    ClaimExtractionError,
    ClaimExtractionQuotaError,
    extract_claims_for_ready_filing,
)

TEMP_ACCESSION = "0000000000-99-000999"
TEMP_TICKER = "ZZZT"
TEMP_FILENAME = "zzzt-temp-pr.htm"
TEMP_DOCUMENT_KEY = f"exhibit:{TEMP_FILENAME}"

_PATCH_TARGET = "src.ready_filing_extraction.extract_and_store_claims"


def _filing_state(supabase) -> dict:
    return (
        supabase.table("filings")
        .select(
            "claim_extraction_status, claim_extracted_at, claim_extraction_error"
        )
        .eq("accession_number", TEMP_ACCESSION)
        .execute()
        .data[0]
    )


def main() -> None:
    supabase = get_supabase_client()
    filing_id = None
    document_id = None

    try:
        filing_id = (
            supabase.table("filings")
            .insert(
                {
                    "ticker": TEMP_TICKER,
                    "accession_number": TEMP_ACCESSION,
                    "form": "8-K",
                    "filing_date": "2000-01-01",
                    "processing_status": "chunked",
                    "sec_url": "https://example.invalid/temp-extraction-test",
                }
            )
            .execute()
            .data[0]["id"]
        )
        document_id = (
            supabase.table("filing_documents")
            .insert(
                {
                    "filing_id": filing_id,
                    "ticker": TEMP_TICKER.lower(),
                    "accession_number": TEMP_ACCESSION,
                    "document_type": "earnings_release",
                    "filename": TEMP_FILENAME,
                    "sec_url": "https://example.invalid/temp-exhibit",
                }
            )
            .execute()
            .data[0]["id"]
        )

        # --- Precondition: not extraction-ready yet --------------------------
        try:
            extract_claims_for_ready_filing(TEMP_ACCESSION)
            raise AssertionError("Expected ValueError for unprocessed exhibit.")
        except ValueError as exc:
            assert "no processed earnings-release exhibit" in str(exc)
        state = _filing_state(supabase)
        assert state["claim_extraction_status"] == "not_started", (
            "Precondition failures must not mark the filing failed."
        )
        print("Not-ready filing: ValueError, status untouched.")

        # --- Missing filing ---------------------------------------------------
        try:
            extract_claims_for_ready_filing("0000000000-00-000000")
            raise AssertionError("Expected ValueError for a missing filing.")
        except ValueError as exc:
            assert "No filing found" in str(exc)
        print("Missing filing: ValueError.")

        # Make the temp filing extraction-ready.
        supabase.table("filings").update(
            {
                "exhibit_processing_status": "processed",
                "earnings_release_document_id": document_id,
            }
        ).eq("accession_number", TEMP_ACCESSION).execute()

        # --- Success path -----------------------------------------------------
        fake_result = {
            "ticker": TEMP_TICKER,
            "accession_number": TEMP_ACCESSION,
            "document_key": TEMP_DOCUMENT_KEY,
            "proposed_claim_count": 2,
            "skipped_invalid_count": 1,
            "proposed_claims": [{"theme": "TEMP"}, {"theme": "TEMP2"}],
        }
        with mock.patch(_PATCH_TARGET, return_value=fake_result) as extractor:
            result = extract_claims_for_ready_filing(TEMP_ACCESSION, max_claims=4)
        extractor.assert_called_once_with(
            accession_number=TEMP_ACCESSION,
            max_claims=4,
            document_key=TEMP_DOCUMENT_KEY,
        )
        assert result["claim_extraction_status"] == "pending_review"
        assert result["proposed_claim_count"] == 2
        state = _filing_state(supabase)
        assert state["claim_extraction_status"] == "pending_review"
        assert state["claim_extracted_at"] is not None
        assert state["claim_extraction_error"] is None
        print(
            "Success: extractor called with the exhibit document_key, "
            "filing marked pending_review."
        )

        # A pre-existing pending draft to prove failures never delete drafts.
        draft_id = (
            supabase.table("proposed_claims")
            .insert(
                {
                    "filing_id": filing_id,
                    "ticker": TEMP_TICKER,
                    "accession_number": TEMP_ACCESSION,
                    "document_key": TEMP_DOCUMENT_KEY,
                    "theme": "TEMP DRAFT",
                    "claim_text": "temp",
                    "supporting_excerpt": "temp",
                    "source_chunk_index": 0,
                    "claim_type": "factual",
                    "confidence": "low",
                    "review_status": "pending",
                }
            )
            .execute()
            .data[0]["id"]
        )

        # --- Quota failure ----------------------------------------------------
        with mock.patch(
            _PATCH_TARGET,
            side_effect=RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded"),
        ):
            try:
                extract_claims_for_ready_filing(TEMP_ACCESSION)
                raise AssertionError("Expected ClaimExtractionQuotaError.")
            except ClaimExtractionQuotaError as exc:
                assert "quota or rate limit" in str(exc)
        state = _filing_state(supabase)
        assert state["claim_extraction_status"] == "failed"
        assert "RESOURCE_EXHAUSTED" in state["claim_extraction_error"]
        print("Quota failure: ClaimExtractionQuotaError, filing marked failed.")

        # --- Generic provider failure -----------------------------------------
        with mock.patch(_PATCH_TARGET, side_effect=RuntimeError("boom")):
            try:
                extract_claims_for_ready_filing(TEMP_ACCESSION)
                raise AssertionError("Expected ClaimExtractionError.")
            except ClaimExtractionError as exc:
                assert "boom" not in str(exc), (
                    "Caller-facing message must not leak the raw error."
                )
        state = _filing_state(supabase)
        assert state["claim_extraction_status"] == "failed"
        assert state["claim_extraction_error"] == "boom"
        print("Generic failure: safe ClaimExtractionError, raw error stored on row.")

        # --- Workflow ValueError from the extractor ---------------------------
        with mock.patch(
            _PATCH_TARGET,
            side_effect=ValueError("All 3 claims returned by Gemini failed validation."),
        ):
            try:
                extract_claims_for_ready_filing(TEMP_ACCESSION)
                raise AssertionError("Expected ValueError to propagate.")
            except ValueError as exc:
                assert "failed validation" in str(exc)
        state = _filing_state(supabase)
        assert state["claim_extraction_status"] == "failed"
        print("Validation failure: ValueError propagates, filing marked failed.")

        # The pre-existing pending draft survived every failure.
        drafts = (
            supabase.table("proposed_claims")
            .select("id")
            .eq("id", draft_id)
            .execute()
            .data
        )
        assert drafts, "Existing pending draft was deleted by a failed run."
        print("Existing pending drafts survived all failure paths.")

    finally:
        supabase.table("proposed_claims").delete().eq(
            "accession_number", TEMP_ACCESSION
        ).execute()
        if filing_id is not None:
            supabase.table("filings").update(
                {"earnings_release_document_id": None}
            ).eq("id", filing_id).execute()
        if document_id is not None:
            supabase.table("filing_documents").delete().eq(
                "id", document_id
            ).execute()
        if filing_id is not None:
            supabase.table("filings").delete().eq("id", filing_id).execute()
        for table in ("proposed_claims", "filing_documents", "filings"):
            leftovers = (
                supabase.table(table)
                .select("*")
                .eq("accession_number", TEMP_ACCESSION)
                .execute()
                .data
            )
            assert not leftovers, f"Temporary {table} rows were not cleaned up."

    print()
    print(
        "PASS: ready-filing extraction enforces preconditions, tracks "
        "pending_review/failed states, classifies quota errors, and never "
        "deletes existing drafts on failure. No Gemini quota consumed."
    )


if __name__ == "__main__":
    main()
