import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.run_all_filing_checks import run_all_filing_checks


def print_summary(results: list[dict]) -> None:
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

    failures = [r for r in results if r["status"] == "failed"]
    if failures:
        print("\nFailed companies:")
        for r in failures:
            print(f"  {r['ticker']}: {r.get('error_message', 'unknown error')}")
    else:
        print("No failures.")


if __name__ == "__main__":
    print("Running filing monitor for all companies (limit=10 each)...\n")
    results = run_all_filing_checks(trigger_type="manual", limit_per_company=10)
    print_summary(results)
