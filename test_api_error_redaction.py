"""Regression test: raw Gemini provider errors must never leak through the
public GET /extraction-ready payload.

A temporary extraction-ready filing is given a realistic provider error
(API key marker, provider hostname) in claim_extraction_error. The public
endpoint must replace it with the generic message while Supabase keeps the
full text for private debugging. Temp rows cleaned up; no AI calls.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.main import app
from src.database import get_supabase_client

TEMP_ACCESSION = "0000000000-99-003333"
TEMP_TICKER = "ZZZT"

RAW_PROVIDER_ERROR = (
    "400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': 'API key not "
    "valid. Please pass a valid API key.', 'status': 'INVALID_ARGUMENT', "
    "'details': [{'reason': 'API_KEY_INVALID', 'domain': "
    "'googleapis.com'}]}} from https://generativelanguage.googleapis.com/"
    "v1beta/models/gemini-2.5-flash:generateContent"
)

PUBLIC_MESSAGE = "Claim extraction failed. Retry later or contact the administrator."

FORBIDDEN_MARKERS = (
    "API_KEY_INVALID",
    "generativelanguage.googleapis.com",
    "INVALID_ARGUMENT",
    "API key",
)


def main() -> None:
    supabase = get_supabase_client()
    client = TestClient(app)
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
                    "sec_url": "https://example.invalid/temp-redaction-test",
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
                    "filename": "zzzt-redaction-pr.htm",
                    "sec_url": "https://example.invalid/zzzt-redaction-pr.htm",
                }
            )
            .execute()
            .data[0]["id"]
        )
        supabase.table("filings").update(
            {
                "exhibit_processing_status": "processed",
                "earnings_release_document_id": document_id,
                "claim_extraction_status": "failed",
                "claim_extraction_error": RAW_PROVIDER_ERROR,
            }
        ).eq("id", filing_id).execute()

        response = client.get("/extraction-ready")
        assert response.status_code == 200
        body = response.json()

        temp_rows = [
            f for f in body["filings"] if f["accession_number"] == TEMP_ACCESSION
        ]
        assert temp_rows, "Temp failed filing missing from /extraction-ready."
        temp = temp_rows[0]
        assert temp["claim_extraction_status"] == "failed"
        assert temp["claim_extraction_error"] == PUBLIC_MESSAGE, (
            f"Expected the generic public message, got "
            f"{temp['claim_extraction_error']!r}."
        )
        print("Failed filing carries the generic public error message.")

        # Nothing provider-specific anywhere in the whole public payload.
        for marker in FORBIDDEN_MARKERS:
            assert marker not in response.text, (
                f"Provider detail {marker!r} leaked into the public payload."
            )
        print("No provider markers anywhere in the public payload.")

        # Filings without an error keep a null field (no phantom errors).
        clean_rows = [
            f
            for f in body["filings"]
            if f["claim_extraction_status"] != "failed"
        ]
        assert all(f["claim_extraction_error"] is None for f in clean_rows), (
            "Non-failed filings must have a null claim_extraction_error."
        )
        print("Non-failed filings keep a null public error field.")

        # The raw error is preserved in Supabase for private debugging.
        stored = (
            supabase.table("filings")
            .select("claim_extraction_error")
            .eq("id", filing_id)
            .execute()
            .data[0]["claim_extraction_error"]
        )
        assert stored == RAW_PROVIDER_ERROR, "Raw error was not preserved in Supabase."
        print("Full raw provider error remains stored in Supabase.")

    finally:
        if filing_id is not None:
            supabase.table("filings").update(
                {"earnings_release_document_id": None}
            ).eq("id", filing_id).execute()
        supabase.table("filing_documents").delete().eq(
            "accession_number", TEMP_ACCESSION
        ).execute()
        if filing_id is not None:
            supabase.table("filings").delete().eq("id", filing_id).execute()
        for table in ("filing_documents", "filings"):
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
        "PASS: public /extraction-ready redacts provider errors to a generic "
        "message while Supabase retains the full text privately."
    )


if __name__ == "__main__":
    main()
