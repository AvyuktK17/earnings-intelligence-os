"""Test cleanup_legacy_claims.py dry-run behavior.

Runs the script WITHOUT --confirm only — the destructive mode is never
exercised by tests. Uses a temporary ungrounded pending row plus a grounded
control row and proves the dry run deletes nothing.
"""

import sys
import os
import subprocess

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client

TEMP_ACCESSION = "0000000000-99-006666"
TEMP_TICKER = "ZZZT"
PYTHON = sys.executable


def main() -> None:
    supabase = get_supabase_client()
    filing_id = None
    chunk_id = None

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
                    "sec_url": "https://example.invalid/temp-cleanup-test",
                }
            )
            .execute()
            .data[0]["id"]
        )
        chunk_id = (
            supabase.table("filing_chunks")
            .insert(
                {
                    "filing_id": filing_id,
                    "ticker": TEMP_TICKER,
                    "accession_number": TEMP_ACCESSION,
                    "document_key": "primary",
                    "chunk_index": 0,
                    "chunk_text": "TEMP CLEANUP CHUNK",
                    "character_count": 18,
                }
            )
            .execute()
            .data[0]["id"]
        )
        ungrounded_id = (
            supabase.table("proposed_claims")
            .insert(
                {
                    "filing_id": filing_id,
                    "ticker": TEMP_TICKER,
                    "accession_number": TEMP_ACCESSION,
                    "document_key": "primary",
                    "theme": "TEMP CLEANUP UNGROUNDED",
                    "claim_text": "temp",
                    "supporting_excerpt": "temp",
                    "source_chunk_index": 0,
                    "source_chunk_id": None,
                    "claim_type": "factual",
                    "confidence": "low",
                    "review_status": "pending",
                }
            )
            .execute()
            .data[0]["id"]
        )
        grounded_id = (
            supabase.table("proposed_claims")
            .insert(
                {
                    "filing_id": filing_id,
                    "ticker": TEMP_TICKER,
                    "accession_number": TEMP_ACCESSION,
                    "document_key": "primary",
                    "theme": "TEMP CLEANUP GROUNDED",
                    "claim_text": "temp",
                    "supporting_excerpt": "TEMP CLEANUP CHUNK",
                    "source_chunk_index": 0,
                    "source_chunk_id": chunk_id,
                    "claim_type": "factual",
                    "confidence": "low",
                    "review_status": "pending",
                }
            )
            .execute()
            .data[0]["id"]
        )

        # --- Dry run: lists the ungrounded row, deletes nothing --------------
        result = subprocess.run(
            [PYTHON, "cleanup_legacy_claims.py"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        out = result.stdout
        assert f"id={ungrounded_id}" in out, (
            "Dry run did not list the temp ungrounded pending row."
        )
        assert f"id={grounded_id}" not in out, (
            "Dry run listed a grounded row — selection is too broad."
        )
        assert "Dry run — nothing deleted" in out
        print("Dry run lists only ungrounded pending rows and deletes nothing.")

        # Both temp rows still exist.
        remaining = (
            supabase.table("proposed_claims")
            .select("id")
            .eq("accession_number", TEMP_ACCESSION)
            .execute()
            .data
        )
        assert {r["id"] for r in remaining} == {ungrounded_id, grounded_id}, (
            "Dry run deleted rows."
        )
        print("All rows survived the dry run.")

        # The known real legacy AVGO rows (ids 11, 12) are untouched as well.
        legacy = (
            supabase.table("proposed_claims")
            .select("id")
            .in_("id", [11, 12])
            .execute()
            .data
        )
        assert len(legacy) == 2, "Real legacy AVGO rows were modified."
        print("Real legacy AVGO rows (11, 12) untouched.")

    finally:
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

    print()
    print(
        "PASS: cleanup script dry run is safe — it identifies only "
        "ungrounded pending rows and deletes nothing without --confirm."
    )


if __name__ == "__main__":
    main()
