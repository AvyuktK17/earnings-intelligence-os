"""
Test SEC EDGAR client using Qualcomm (CIK 0000804328).
Fetches recent filings, filters to 10-K / 10-Q / 8-K, and prints the first 10.
Does NOT write anything to Supabase.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from sec_client import get_recent_filings

QUALCOMM_CIK = "0000804328"
RELEVANT_FORMS = {"10-K", "10-Q", "8-K"}


def main():
    print("Fetching recent SEC filings for Qualcomm (CIK 0000804328)...")
    all_filings = get_recent_filings(QUALCOMM_CIK)
    print(f"Total filings returned: {len(all_filings)}")

    relevant = [f for f in all_filings if f["form"] in RELEVANT_FORMS]
    print(f"Relevant filings (10-K / 10-Q / 8-K): {len(relevant)}")
    print()

    print("First 10 relevant filings:")
    print("-" * 60)
    for filing in relevant[:10]:
        print(f"  Form:              {filing['form']}")
        print(f"  Accession Number:  {filing['accession_number']}")
        print(f"  Filing Date:       {filing['filing_date']}")
        print(f"  Report Date:       {filing['report_date']}")
        print(f"  Primary Document:  {filing['primary_document']}")
        print("-" * 60)

    assert len(relevant) >= 1, (
        "Expected at least one relevant filing (10-K, 10-Q, or 8-K) "
        f"but got {len(relevant)}."
    )

    print()
    print("PASS: SEC EDGAR client is working correctly.")


if __name__ == "__main__":
    main()
