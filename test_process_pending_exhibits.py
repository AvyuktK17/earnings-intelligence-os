"""Integration tests for the automated earnings-release exhibit worker.

Covers the processed path (against the real, already-ingested AVGO 8-K),
the not-found path, and the failure path (both with a temporary filing row
and monkeypatched exhibit discovery — no synthetic SEC traffic). Verifies
idempotency, that existing exhibit chunks referenced by trusted claims are
never deleted, and that trusted claims are untouched. No AI calls. The AVGO
filing is intentionally left in its true final state: "processed".
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from unittest import mock

from src.database import get_supabase_client
from src.process_pending_exhibits import process_pending_exhibits

AVGO_ACCESSION = "0001730168-26-000051"
AVGO_GROUNDED_CHUNK_ID = 1499  # referenced by trusted claims 30-34

TEMP_ACCESSION = "0000000000-99-000777"
TEMP_TICKER = "ZZZT"


def _reset_avgo_exhibit_status(supabase) -> None:
    supabase.table("filings").update(
        {
            "exhibit_processing_status": "not_checked",
            "earnings_release_document_id": None,
            "exhibit_checked_at": None,
            "exhibit_processing_error": None,
        }
    ).eq("accession_number", AVGO_ACCESSION).execute()


def _avgo_filing(supabase) -> dict:
    return (
        supabase.table("filings")
        .select(
            "exhibit_processing_status, earnings_release_document_id, "
            "exhibit_checked_at, exhibit_processing_error"
        )
        .eq("accession_number", AVGO_ACCESSION)
        .execute()
        .data[0]
    )


def _avgo_exhibit_state(supabase) -> tuple[list[dict], int]:
    documents = (
        supabase.table("filing_documents")
        .select("id, filename")
        .eq("accession_number", AVGO_ACCESSION)
        .eq("document_type", "earnings_release")
        .execute()
        .data
    )
    chunk_count = (
        supabase.table("filing_chunks")
        .select("id", count="exact")
        .eq("filing_document_id", documents[0]["id"])
        .execute()
        .count
        if documents
        else 0
    )
    return documents, chunk_count or 0


def _trusted_avgo_claims(supabase) -> list[dict]:
    return (
        supabase.table("qualitative_claims")
        .select("proposed_claim_id, claim, source_chunk_id, document_key")
        .eq("ticker", "AVGO")
        .not_.is_("proposed_claim_id", "null")
        .order("proposed_claim_id", desc=False)
        .execute()
        .data
    )


def _temp_filing_row(supabase) -> dict | None:
    rows = (
        supabase.table("filings")
        .select(
            "id, exhibit_processing_status, exhibit_checked_at, "
            "exhibit_processing_error, earnings_release_document_id"
        )
        .eq("accession_number", TEMP_ACCESSION)
        .execute()
        .data
    )
    return rows[0] if rows else None


def main() -> None:
    supabase = get_supabase_client()
    temp_filing_id = None

    try:
        # --- 1. Positive path on the real AVGO filing -----------------------
        documents_before, chunks_before = _avgo_exhibit_state(supabase)
        assert len(documents_before) == 1, (
            "Expected exactly one existing AVGO earnings_release document."
        )
        assert chunks_before > 0, "Expected existing AVGO exhibit chunks."
        trusted_before = _trusted_avgo_claims(supabase)
        assert len(trusted_before) == 5, "Expected 5 trusted AVGO claims."

        _reset_avgo_exhibit_status(supabase)

        # AVGO (2026-06-03) is the newest real 8-K, so limit=1 selects it.
        results = process_pending_exhibits(limit=1)
        assert len(results) == 1, f"Expected 1 result, got {len(results)}."
        result = results[0]
        assert result["accession_number"] == AVGO_ACCESSION, (
            f"Worker selected {result['accession_number']}, expected AVGO."
        )
        assert result["status"] == "processed", f"Got {result['status']!r}."
        assert result["filing_document_id"] == documents_before[0]["id"]
        assert result["chunk_count"] == chunks_before
        assert result["document_key"] == f"exhibit:{documents_before[0]['filename']}"
        assert result["average_chunk_characters"] > 0
        print(
            f"AVGO processed: document_id={result['filing_document_id']}, "
            f"chunks={result['chunk_count']}"
        )

        filing = _avgo_filing(supabase)
        assert filing["exhibit_processing_status"] == "processed"
        assert (
            filing["earnings_release_document_id"] == documents_before[0]["id"]
        )
        assert filing["exhibit_checked_at"] is not None
        assert filing["exhibit_processing_error"] is None

        # --- 2. Rerun safety: no duplicate documents or chunks --------------
        _reset_avgo_exhibit_status(supabase)
        rerun = process_pending_exhibits(limit=1)[0]
        assert rerun["accession_number"] == AVGO_ACCESSION
        assert rerun["status"] == "processed"
        assert rerun["filing_document_id"] == documents_before[0]["id"]

        documents_after, chunks_after = _avgo_exhibit_state(supabase)
        assert len(documents_after) == 1, "Duplicate filing_documents row."
        assert documents_after[0]["id"] == documents_before[0]["id"]
        assert chunks_after == chunks_before, (
            f"Chunk count changed: {chunks_before} -> {chunks_after}."
        )
        grounded_chunk = (
            supabase.table("filing_chunks")
            .select("id")
            .eq("id", AVGO_GROUNDED_CHUNK_ID)
            .execute()
            .data
        )
        assert grounded_chunk, "Grounded chunk referenced by claims was deleted."
        print("Rerun safe: no duplicate document rows, chunks untouched.")

        # A processed filing is never selected again by default. Checked with
        # the worker's own selection filter (read-only — running the worker
        # over every pending row would touch real filings).
        selectable = (
            supabase.table("filings")
            .select("accession_number")
            .eq("form", "8-K")
            .eq("processing_status", "chunked")
            .in_("exhibit_processing_status", ["not_checked", "failed"])
            .execute()
            .data
        )
        assert all(
            r["accession_number"] != AVGO_ACCESSION for r in selectable
        ), "Processed AVGO filing is still selectable by the worker."
        print("Processed filings are excluded from later runs.")

        # --- 3. Not-found path on a temporary 8-K row -----------------------
        temp_filing_id = (
            supabase.table("filings")
            .insert(
                {
                    "ticker": TEMP_TICKER,
                    "accession_number": TEMP_ACCESSION,
                    "form": "8-K",
                    # Future date so this row sorts first with limit=1.
                    "filing_date": "2027-01-01",
                    "processing_status": "chunked",
                    "sec_url": "https://example.invalid/temp-exhibit-test",
                }
            )
            .execute()
            .data[0]["id"]
        )

        with mock.patch(
            "src.process_pending_exhibits.get_filing_exhibits", return_value=[]
        ):
            results = process_pending_exhibits(limit=1)
        assert len(results) == 1
        result = results[0]
        assert result["accession_number"] == TEMP_ACCESSION
        assert result["status"] == "not_found"
        temp_row = _temp_filing_row(supabase)
        assert temp_row["exhibit_processing_status"] == "not_found"
        assert temp_row["exhibit_checked_at"] is not None
        assert temp_row["exhibit_processing_error"] is None
        assert temp_row["earnings_release_document_id"] is None
        print("Not-found path: status and timestamp recorded.")

        # --- 4. Failure path -------------------------------------------------
        supabase.table("filings").update(
            {"exhibit_processing_status": "not_checked", "exhibit_checked_at": None}
        ).eq("accession_number", TEMP_ACCESSION).execute()

        with mock.patch(
            "src.process_pending_exhibits.get_filing_exhibits",
            side_effect=RuntimeError("synthetic test failure"),
        ):
            results = process_pending_exhibits(limit=1)
        result = results[0]
        assert result["accession_number"] == TEMP_ACCESSION
        assert result["status"] == "failed"
        assert result["error_message"] == "synthetic test failure"
        temp_row = _temp_filing_row(supabase)
        assert temp_row["exhibit_processing_status"] == "failed"
        assert temp_row["exhibit_processing_error"] == "synthetic test failure"
        print("Failure path: status and error message recorded.")

        # Failed rows are skipped by default (read-only filter check) but
        # retried with include_failed=True.
        default_selectable = (
            supabase.table("filings")
            .select("accession_number")
            .eq("form", "8-K")
            .eq("processing_status", "chunked")
            .in_("exhibit_processing_status", ["not_checked"])
            .execute()
            .data
        )
        assert all(
            r["accession_number"] != TEMP_ACCESSION for r in default_selectable
        ), "Failed row is selectable without include_failed."

        with mock.patch(
            "src.process_pending_exhibits.get_filing_exhibits", return_value=[]
        ):
            retry_run = process_pending_exhibits(limit=1, include_failed=True)
        assert retry_run[0]["accession_number"] == TEMP_ACCESSION
        assert retry_run[0]["status"] == "not_found"
        print("include_failed=True retries failed rows; default skips them.")

        # --- 5. Trusted claims untouched -------------------------------------
        trusted_after = _trusted_avgo_claims(supabase)
        assert trusted_after == trusted_before, "Trusted AVGO claims changed."
        print("Trusted AVGO claims are unchanged.")

    finally:
        supabase.table("filings").delete().eq(
            "accession_number", TEMP_ACCESSION
        ).execute()
        leftovers = (
            supabase.table("filings")
            .select("id")
            .eq("accession_number", TEMP_ACCESSION)
            .execute()
            .data
        )
        assert not leftovers, "Temporary filing row was not cleaned up."
        del temp_filing_id

    print()
    print(
        "PASS: exhibit worker processes, records not-found and failed states, "
        "stays idempotent, and never disturbs grounded chunks or trusted "
        "claims. AVGO is left in its true 'processed' state."
    )


if __name__ == "__main__":
    main()
