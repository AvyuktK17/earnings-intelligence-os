"""
Test the filing-sync service using Qualcomm (CIK 0000804328).
Runs sync twice to verify idempotency: second run should insert nothing.
Does NOT delete existing Supabase rows.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.filing_sync import sync_recent_filings

TICKER = "QCOM"
CIK = "0000804328"
LIMIT = 10


def print_result(label: str, result: dict) -> None:
    print(f"\n--- {label} ---")
    print(f"  Ticker:          {result['ticker']}")
    print(f"  Checked:         {result['checked_count']}")
    print(f"  Inserted:        {result['inserted_count']}")
    print(f"  Skipped:         {result['skipped_count']}")
    if result["inserted_filings"]:
        print("  Inserted accession numbers:")
        for acc in result["inserted_filings"]:
            print(f"    - {acc}")
    else:
        print("  Inserted accession numbers: (none)")


def main():
    print("Run 1: syncing recent QCOM filings (limit=10)...")
    run1 = sync_recent_filings(TICKER, CIK, limit=LIMIT)
    print_result("Run 1 result", run1)

    print("\nRun 2: syncing again (should insert nothing)...")
    run2 = sync_recent_filings(TICKER, CIK, limit=LIMIT)
    print_result("Run 2 result", run2)

    # Verify run 1 checked the expected number
    assert run1["checked_count"] == LIMIT, (
        f"Run 1 should check {LIMIT} filings but checked {run1['checked_count']}."
    )

    # Verify run 2 inserts nothing and skips everything
    assert run2["inserted_count"] == 0, (
        f"Run 2 should insert 0 filings but inserted {run2['inserted_count']}."
    )
    assert run2["skipped_count"] == LIMIT, (
        f"Run 2 should skip {LIMIT} filings but skipped {run2['skipped_count']}."
    )

    print("\nPASS: filing sync is working correctly.")


if __name__ == "__main__":
    main()
