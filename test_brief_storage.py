"""Test versioned earnings-brief generation, upload, and storage.

Calls generate_and_store_earnings_brief twice for the AVGO filing, verifies
versioning, Storage paths, and earnings_briefs DB rows, then deletes only
the temporary rows created by this test. Storage objects are left in place.
Does not call Gemini. Does not modify trusted claims.
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.brief_storage import generate_and_store_earnings_brief

TICKER = "AVGO"
ACCESSION = "0001730168-26-000051"


def fetch_brief_row(supabase, brief_id: int) -> dict:
    rows = (
        supabase.table("earnings_briefs")
        .select("*")
        .eq("id", brief_id)
        .execute()
        .data
    )
    return rows[0] if rows else {}


def main() -> None:
    supabase = get_supabase_client()

    # Snapshot: record the highest version already in the table before this test.
    existing = (
        supabase.table("earnings_briefs")
        .select("version_number")
        .eq("accession_number", ACCESSION)
        .order("version_number", desc=True)
        .limit(1)
        .execute()
        .data
    )
    base_version = existing[0]["version_number"] if existing else 0
    print(f"Highest existing version before test: {base_version}")

    inserted_ids = []

    try:
        # --- Run 1 ---
        print("\nRun 1: generate_and_store_earnings_brief()...")
        r1 = generate_and_store_earnings_brief(ticker=TICKER, accession_number=ACCESSION)

        expected_v1 = base_version + 1
        assert r1["version_number"] == expected_v1, (
            f"Expected version {expected_v1} but got {r1['version_number']}."
        )
        assert r1["storage_path"], "storage_path must not be empty."
        assert Path(r1["local_output_path"]).exists(), (
            f"Local file not found: {r1['local_output_path']}"
        )
        print(f"  version_number    : {r1['version_number']}")
        print(f"  local_output_path : {r1['local_output_path']}")
        print(f"  storage_path      : {r1['storage_path']}")

        # Verify the DB row.
        rows_v1 = (
            supabase.table("earnings_briefs")
            .select("id, version_number, markdown_content, storage_path, "
                    "trusted_claim_count, factual_claim_count, interpretive_claim_count")
            .eq("accession_number", ACCESSION)
            .eq("version_number", r1["version_number"])
            .execute()
            .data
        )
        assert rows_v1, f"No DB row found for version {r1['version_number']}."
        row_v1 = rows_v1[0]
        inserted_ids.append(row_v1["id"])

        assert row_v1["markdown_content"], "markdown_content must not be empty."
        assert row_v1["trusted_claim_count"] == 5, (
            f"Expected trusted_claim_count=5, got {row_v1['trusted_claim_count']}."
        )
        assert row_v1["factual_claim_count"] == 5, (
            f"Expected factual_claim_count=5, got {row_v1['factual_claim_count']}."
        )
        assert row_v1["interpretive_claim_count"] == 0, (
            f"Expected interpretive_claim_count=0, got {row_v1['interpretive_claim_count']}."
        )
        print(f"  [OK] DB row: trusted={row_v1['trusted_claim_count']} "
              f"factual={row_v1['factual_claim_count']} "
              f"interpretive={row_v1['interpretive_claim_count']}")
        print("  [OK] markdown_content non-empty")

        # --- Run 2 ---
        print("\nRun 2: generate_and_store_earnings_brief()...")
        r2 = generate_and_store_earnings_brief(ticker=TICKER, accession_number=ACCESSION)

        expected_v2 = r1["version_number"] + 1
        assert r2["version_number"] == expected_v2, (
            f"Expected version {expected_v2} but got {r2['version_number']}."
        )
        print(f"  version_number    : {r2['version_number']}")
        print(f"  local_output_path : {r2['local_output_path']}")
        print(f"  storage_path      : {r2['storage_path']}")

        assert r2["storage_path"] != r1["storage_path"], (
            "Run 2 storage_path must differ from run 1."
        )
        print(f"  [OK] storage paths are different: "
              f"{r1['storage_path']!r} vs {r2['storage_path']!r}")

        rows_v2 = (
            supabase.table("earnings_briefs")
            .select("id, version_number, storage_path")
            .eq("accession_number", ACCESSION)
            .eq("version_number", r2["version_number"])
            .execute()
            .data
        )
        assert rows_v2, f"No DB row found for version {r2['version_number']}."
        row_v2 = rows_v2[0]
        inserted_ids.append(row_v2["id"])

        # Both rows coexist.
        all_rows = (
            supabase.table("earnings_briefs")
            .select("id, version_number")
            .in_("id", inserted_ids)
            .execute()
            .data
        )
        assert len(all_rows) == 2, (
            f"Expected 2 brief rows to coexist but found {len(all_rows)}."
        )
        versions_stored = {r["version_number"] for r in all_rows}
        assert r1["version_number"] in versions_stored
        assert r2["version_number"] in versions_stored
        print("  [OK] both version rows coexist in earnings_briefs without overwriting")

    finally:
        # Delete only the temporary rows created by this test.
        if inserted_ids:
            supabase.table("earnings_briefs").delete().in_("id", inserted_ids).execute()
            remaining = (
                supabase.table("earnings_briefs")
                .select("id")
                .in_("id", inserted_ids)
                .execute()
                .data
            )
            assert len(remaining) == 0, f"Temp rows not fully deleted: {remaining}"
            print(f"\nCleaned up temp earnings_briefs rows {inserted_ids}.")
            print("Storage objects left in place.")

    print()
    print(
        "PASS: versioned brief storage works correctly — "
        "each run increments the version, Storage paths are distinct, "
        "and both rows coexist without overwriting."
    )


if __name__ == "__main__":
    main()
