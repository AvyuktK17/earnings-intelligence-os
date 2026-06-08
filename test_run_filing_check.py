"""
Test the filing-check orchestrator using Qualcomm (CIK 0000804328).
Verifies that the pipeline run is recorded as 'success' in Supabase.
Does NOT delete existing Supabase rows.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.run_filing_check import run_filing_check
from src.database import get_supabase_client


def main():
    print("Running filing check for QCOM...")
    result = run_filing_check(
        ticker="QCOM",
        cik="0000804328",
        trigger_type="manual_test",
        limit=10,
    )

    print("\nReturned result:")
    for key, value in result.items():
        print(f"  {key}: {value}")

    # Verify the returned result
    assert result["status"] == "success", (
        f"Expected status 'success' but got {result['status']!r}."
    )
    assert result["checked_count"] == 10, (
        f"Expected checked_count=10 but got {result['checked_count']}."
    )
    assert result["inserted_count"] == 0, (
        f"Expected inserted_count=0 but got {result['inserted_count']} "
        "(filings already exist from the previous sync test)."
    )
    assert result["skipped_count"] == 10, (
        f"Expected skipped_count=10 but got {result['skipped_count']}."
    )

    # Confirm the pipeline_runs row was saved with status = "success"
    supabase = get_supabase_client()
    run_row = (
        supabase.table("pipeline_runs")
        .select("id, status, ticker, trigger_type, completed_at")
        .eq("id", result["run_id"])
        .execute()
    )

    assert run_row.data, f"No pipeline_runs row found for id={result['run_id']}."
    row = run_row.data[0]

    print(f"\nPipeline run row in Supabase:")
    for key, value in row.items():
        print(f"  {key}: {value}")

    assert row["status"] == "success", (
        f"Expected pipeline run status 'success' but got {row['status']!r}."
    )

    print("\nPASS: orchestrator is working correctly.")


if __name__ == "__main__":
    main()
