"""
Test the multi-company filing check using the companies table in Supabase.
Expects exactly 5 companies: QCOM, AMD, NVDA, INTC, AVGO.
Does NOT delete existing Supabase rows.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.run_all_filing_checks import run_all_filing_checks

EXPECTED_TICKERS = {"QCOM", "AMD", "NVDA", "INTC", "AVGO"}
LIMIT = 5


def main():
    print("Running filing checks for all companies (limit=5 each)...\n")
    results = run_all_filing_checks(trigger_type="manual_test", limit_per_company=LIMIT)

    # Print summary table
    col = "{:<6} {:<10} {:>9} {:>10} {:>10}"
    header = col.format("Ticker", "Status", "Checked", "Inserted", "Skipped")
    print(header)
    print("-" * len(header))
    for r in results:
        print(col.format(
            r["ticker"],
            r["status"],
            r["checked_count"],
            r["inserted_count"],
            r["skipped_count"],
        ))

    total_inserted = sum(r["inserted_count"] for r in results)
    print(f"\nTotal new filings inserted: {total_inserted}")

    # Verify number of results
    assert len(results) == 5, (
        f"Expected 5 company results but got {len(results)}."
    )

    # Verify tickers
    returned_tickers = {r["ticker"] for r in results}
    assert returned_tickers == EXPECTED_TICKERS, (
        f"Expected tickers {EXPECTED_TICKERS} but got {returned_tickers}."
    )

    # Verify every company succeeded and checked the right number
    for r in results:
        assert r["status"] == "success", (
            f"{r['ticker']}: expected status 'success' but got {r['status']!r}. "
            f"Error: {r.get('error_message', 'n/a')}"
        )
        assert r["checked_count"] == LIMIT, (
            f"{r['ticker']}: expected checked_count={LIMIT} but got {r['checked_count']}."
        )

    print("\nPASS: all-company filing check is working correctly.")


if __name__ == "__main__":
    main()
