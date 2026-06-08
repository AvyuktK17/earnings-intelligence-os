import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client


def main():
    supabase = get_supabase_client()

    # Get total count
    count_response = supabase.table("filings").select("id", count="exact").execute()
    total = count_response.count

    # Get 25 most recent filings
    response = (
        supabase.table("filings")
        .select("ticker, form, filing_date, accession_number, processing_status")
        .order("filing_date", desc=True)
        .limit(25)
        .execute()
    )
    rows = response.data

    col = "{:<6} {:<6} {:<13} {:<26} {:<12}"
    header = col.format("Ticker", "Form", "Filing Date", "Accession Number", "Status")
    print(header)
    print("-" * len(header))
    for r in rows:
        print(col.format(
            r["ticker"],
            r["form"],
            r["filing_date"] or "",
            r["accession_number"],
            r["processing_status"] or "",
        ))

    print(f"\nTotal filings stored: {total}")


if __name__ == "__main__":
    main()
