"""
Test the backfill worker that repairs parsed filings missing Storage paths.
Verifies that up to 3 rows are repaired and their Supabase rows are updated.
Does NOT delete rows, make the bucket public, or commit filing contents.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.backfill_missing_storage import backfill_missing_storage_paths

BATCH_SIZE = 3


def count_missing(supabase) -> int:
    response = (
        supabase.table("filings")
        .select("id", count="exact")
        .eq("processing_status", "parsed")
        .or_("html_storage_path.is.null,text_storage_path.is.null")
        .execute()
    )
    return response.count


def main():
    supabase = get_supabase_client()

    missing_before = count_missing(supabase)
    print(f"Parsed filings with missing Storage paths before backfill: {missing_before}")

    if missing_before == 0:
        print("Nothing to repair — all parsed filings already have Storage paths.")
        print("\nPASS: backfill worker correctly reports no work needed.")
        return

    print(f"\nRunning backfill (limit={BATCH_SIZE})...\n")
    results = backfill_missing_storage_paths(limit=BATCH_SIZE)

    assert len(results) <= BATCH_SIZE, (
        f"Expected at most {BATCH_SIZE} results but got {len(results)}."
    )

    successful = [r for r in results if r["status"] == "parsed"]

    for r in results:
        print(f"  {r['ticker']:<6} {r['accession_number']:<28} {r['status']}")
        if r["status"] == "parsed":
            print(f"    html_storage_path : {r['html_storage_path']}")
            print(f"    text_storage_path : {r['text_storage_path']}")
            assert r["html_storage_path"], "html_storage_path missing from result."
            assert r["text_storage_path"], "text_storage_path missing from result."

            # Verify Supabase row is fully updated
            db = (
                supabase.table("filings")
                .select("processing_status, html_storage_path, text_storage_path")
                .eq("accession_number", r["accession_number"])
                .execute()
            )
            assert db.data, f"Row not found in Supabase: {r['accession_number']}"
            row = db.data[0]
            assert row["processing_status"] == "parsed", (
                f"{r['accession_number']}: expected 'parsed' but got {row['processing_status']!r}."
            )
            assert row["html_storage_path"], (
                f"{r['accession_number']}: html_storage_path not saved in Supabase."
            )
            assert row["text_storage_path"], (
                f"{r['accession_number']}: text_storage_path not saved in Supabase."
            )

    missing_after = count_missing(supabase)
    expected_after = missing_before - len(successful)

    print(f"\nMissing before : {missing_before}")
    print(f"Missing after  : {missing_after}")
    print(f"Repaired       : {len(successful)}")

    assert missing_after == expected_after, (
        f"Expected missing count to drop to {expected_after} but got {missing_after}."
    )

    print()
    print("PASS: backfill worker is working correctly.")


if __name__ == "__main__":
    main()
