"""Regression test: the exhibit worker must upgrade a filing to the
best-ranked exhibit instead of blindly reusing any existing chunked
earnings-release document.

Scenario (all temporary rows, ingestion and chunking monkeypatched — no
SEC network beyond discovery patches, no Storage writes, no AI calls):
a filing already has a chunked slide-deck document, but its directory also
contains a higher-ranked press release. The worker must ingest the press
release, re-point earnings_release_document_id to it, and keep the slide
deck and its chunks as secondary evidence. Exact-filename reuse and rerun
idempotency are also proven.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from unittest import mock

from src.database import get_supabase_client
from src.process_pending_exhibits import process_pending_exhibits

TEMP_ACCESSION = "0000000000-99-002222"
TEMP_TICKER = "ZZZT"
SLIDE_FILENAME = "zzzt-q1earningsslidesfin.htm"
PRESS_FILENAME = "zzzt-q1pr.htm"

_DISCOVERY = "src.process_pending_exhibits.get_filing_exhibits"
_INGEST = "src.process_pending_exhibits.process_earnings_release_exhibit"
_CHUNKER = "src.process_pending_exhibits.chunk_and_store_document"


def _candidate(filename: str, size_bytes: int) -> dict:
    return {
        "filename": filename,
        "url": f"https://www.sec.gov/fake/{filename}",
        "description": filename,
        "size_bytes": size_bytes,
        "likely_exhibit_type": "earnings_release",
    }


# The slide deck is much larger: under the old size-first selection it would
# win, and under the old reuse logic its existing chunks would short-circuit
# the upgrade entirely.
DIRECTORY = [_candidate(SLIDE_FILENAME, 900_000), _candidate(PRESS_FILENAME, 120_000)]


def main() -> None:
    supabase = get_supabase_client()
    filing_id = None
    slide_doc_id = None
    press_doc_id = None

    try:
        # --- Setup: filing with an already-chunked slide-deck document --------
        filing_id = (
            supabase.table("filings")
            .insert(
                {
                    "ticker": TEMP_TICKER,
                    "accession_number": TEMP_ACCESSION,
                    "form": "8-K",
                    # Future date so limit=1 selects this row first.
                    "filing_date": "2027-01-01",
                    "processing_status": "chunked",
                    "sec_url": "https://example.invalid/temp-repointing-test",
                }
            )
            .execute()
            .data[0]["id"]
        )
        slide_doc_id = (
            supabase.table("filing_documents")
            .insert(
                {
                    "filing_id": filing_id,
                    "ticker": TEMP_TICKER.lower(),
                    "accession_number": TEMP_ACCESSION,
                    "document_type": "earnings_release",
                    "filename": SLIDE_FILENAME,
                    "sec_url": f"https://example.invalid/{SLIDE_FILENAME}",
                }
            )
            .execute()
            .data[0]["id"]
        )
        slide_chunk_id = (
            supabase.table("filing_chunks")
            .insert(
                {
                    "filing_id": filing_id,
                    "filing_document_id": slide_doc_id,
                    "ticker": TEMP_TICKER,
                    "accession_number": TEMP_ACCESSION,
                    "document_key": f"exhibit:{SLIDE_FILENAME}",
                    "chunk_index": 0,
                    "chunk_text": "TEMP SLIDE CHUNK",
                    "character_count": 16,
                }
            )
            .execute()
            .data[0]["id"]
        )
        # The buggy state: pointer at the slide deck, then reset for recheck.
        supabase.table("filings").update(
            {
                "exhibit_processing_status": "not_checked",
                "earnings_release_document_id": slide_doc_id,
            }
        ).eq("id", filing_id).execute()

        # Fakes for the ingestion pipeline: a real filing_documents upsert and
        # one chunk row, with no SEC download or Storage upload.
        def fake_ingest(accession_number: str) -> dict:
            assert accession_number == TEMP_ACCESSION
            supabase.table("filing_documents").upsert(
                {
                    "filing_id": filing_id,
                    "ticker": TEMP_TICKER.lower(),
                    "accession_number": TEMP_ACCESSION,
                    "document_type": "earnings_release",
                    "filename": PRESS_FILENAME,
                    "sec_url": f"https://example.invalid/{PRESS_FILENAME}",
                },
                on_conflict="accession_number,filename",
            ).execute()
            doc_id = (
                supabase.table("filing_documents")
                .select("id")
                .eq("accession_number", TEMP_ACCESSION)
                .eq("filename", PRESS_FILENAME)
                .execute()
                .data[0]["id"]
            )
            return {
                "filing_document_id": doc_id,
                "filing_id": filing_id,
                "ticker": TEMP_TICKER.lower(),
                "accession_number": TEMP_ACCESSION,
                "filename": PRESS_FILENAME,
            }

        def fake_chunker(document_id: int) -> dict:
            supabase.table("filing_chunks").delete().eq(
                "accession_number", TEMP_ACCESSION
            ).eq("document_key", f"exhibit:{PRESS_FILENAME}").execute()
            supabase.table("filing_chunks").insert(
                {
                    "filing_id": filing_id,
                    "filing_document_id": document_id,
                    "ticker": TEMP_TICKER,
                    "accession_number": TEMP_ACCESSION,
                    "document_key": f"exhibit:{PRESS_FILENAME}",
                    "chunk_index": 0,
                    "chunk_text": "TEMP PRESS CHUNK",
                    "character_count": 16,
                }
            ).execute()
            return {
                "document_key": f"exhibit:{PRESS_FILENAME}",
                "chunk_count": 1,
                "average_chunk_characters": 16,
            }

        # --- 1. Worker upgrades to the better-ranked press release ------------
        with mock.patch(_DISCOVERY, return_value=DIRECTORY), mock.patch(
            _INGEST, side_effect=fake_ingest
        ), mock.patch(_CHUNKER, side_effect=fake_chunker):
            results = process_pending_exhibits(limit=1)

        assert len(results) == 1
        result = results[0]
        assert result["accession_number"] == TEMP_ACCESSION
        assert result["status"] == "processed"
        assert result["filename"] == PRESS_FILENAME, (
            f"Worker kept {result['filename']!r} instead of upgrading to the "
            "press release."
        )
        press_doc_id = result["filing_document_id"]
        assert press_doc_id != slide_doc_id

        filing = (
            supabase.table("filings")
            .select("exhibit_processing_status, earnings_release_document_id")
            .eq("id", filing_id)
            .execute()
            .data[0]
        )
        assert filing["exhibit_processing_status"] == "processed"
        assert filing["earnings_release_document_id"] == press_doc_id, (
            "Filing pointer did not move to the press-release document."
        )
        print("Upgrade: press release ingested and pointer re-pointed.")

        # --- 2. Slide deck stays as secondary evidence -------------------------
        slide_doc = (
            supabase.table("filing_documents")
            .select("id")
            .eq("id", slide_doc_id)
            .execute()
            .data
        )
        slide_chunks = (
            supabase.table("filing_chunks")
            .select("id")
            .eq("filing_document_id", slide_doc_id)
            .execute()
            .data
        )
        assert slide_doc, "Slide-deck document row was deleted."
        assert [c["id"] for c in slide_chunks] == [slide_chunk_id], (
            "Slide-deck chunks were deleted or changed."
        )
        print("Secondary evidence: slide-deck document and chunks preserved.")

        # --- 3. Exact-match reuse + rerun idempotency ---------------------------
        press_chunk_ids = sorted(
            c["id"]
            for c in supabase.table("filing_chunks")
            .select("id")
            .eq("filing_document_id", press_doc_id)
            .execute()
            .data
        )
        supabase.table("filings").update(
            {"exhibit_processing_status": "not_checked"}
        ).eq("id", filing_id).execute()

        # Ingestion and chunking must NOT run when the selected document is
        # already ingested — exploding mocks prove the reuse path is taken.
        with mock.patch(_DISCOVERY, return_value=DIRECTORY), mock.patch(
            _INGEST, side_effect=AssertionError("ingest must not run")
        ), mock.patch(
            _CHUNKER, side_effect=AssertionError("chunker must not run")
        ):
            rerun = process_pending_exhibits(limit=1)[0]

        assert rerun["status"] == "processed", rerun.get("error_message")
        assert rerun["filing_document_id"] == press_doc_id
        assert rerun["chunk_count"] == 1

        press_chunk_ids_after = sorted(
            c["id"]
            for c in supabase.table("filing_chunks")
            .select("id")
            .eq("filing_document_id", press_doc_id)
            .execute()
            .data
        )
        assert press_chunk_ids_after == press_chunk_ids, (
            "Exact-match reuse changed existing chunk ids."
        )
        press_docs = (
            supabase.table("filing_documents")
            .select("id")
            .eq("accession_number", TEMP_ACCESSION)
            .eq("filename", PRESS_FILENAME)
            .execute()
            .data
        )
        assert len(press_docs) == 1, "Rerun duplicated the press-release row."
        print(
            "Reuse: exact filename match skips re-ingestion and preserves "
            "chunk ids; rerun is idempotent."
        )

    finally:
        if filing_id is not None:
            supabase.table("filings").update(
                {"earnings_release_document_id": None}
            ).eq("id", filing_id).execute()
        supabase.table("filing_chunks").delete().eq(
            "accession_number", TEMP_ACCESSION
        ).execute()
        supabase.table("filing_documents").delete().eq(
            "accession_number", TEMP_ACCESSION
        ).execute()
        if filing_id is not None:
            supabase.table("filings").delete().eq("id", filing_id).execute()
        for table in ("filing_chunks", "filing_documents", "filings"):
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
        "PASS: the worker upgrades filings to the best-ranked exhibit, keeps "
        "lower-ranked documents as secondary evidence, and reuses an "
        "exact-match ingestion without touching its chunk ids."
    )


if __name__ == "__main__":
    main()
