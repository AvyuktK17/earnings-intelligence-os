from src.database import get_supabase_client
from src.sec_client import get_recent_filings

RELEVANT_FORMS = {"10-K", "10-Q", "8-K"}


def _build_sec_url(cik: str, accession_number: str, primary_document: str) -> str:
    """Build the direct SEC EDGAR URL for a filing document."""
    cik_no_zeros = str(cik).lstrip("0")
    accession_no_hyphens = accession_number.replace("-", "")
    return (
        f"https://www.sec.gov/Archives/edgar/data/"
        f"{cik_no_zeros}/{accession_no_hyphens}/{primary_document}"
    )


def sync_recent_filings(ticker: str, cik: str, limit: int = 10) -> dict:
    """Fetch recent SEC filings and sync new ones to Supabase.

    Args:
        ticker: Stock ticker symbol (e.g. "QCOM").
        cik: SEC CIK number for the company.
        limit: Maximum number of relevant filings to consider.

    Returns:
        A dict with ticker, checked_count, inserted_count, skipped_count,
        and inserted_filings.
    """
    supabase = get_supabase_client()

    # Fetch all recent filings from SEC, then filter and cap at limit
    all_filings = get_recent_filings(cik)
    relevant = [f for f in all_filings if f["form"] in RELEVANT_FORMS][:limit]

    inserted_count = 0
    skipped_count = 0
    inserted_filings = []

    for filing in relevant:
        accession_number = filing["accession_number"]

        # Check if this accession number already exists in Supabase
        existing = (
            supabase.table("filings")
            .select("id")
            .eq("accession_number", accession_number)
            .execute()
        )

        if existing.data:
            skipped_count += 1
            continue

        # Build the SEC URL and insert the new row
        sec_url = _build_sec_url(cik, accession_number, filing["primary_document"])

        row = {
            "ticker": ticker,
            "accession_number": accession_number,
            "form": filing["form"],
            "filing_date": filing["filing_date"] or None,
            "report_date": filing["report_date"] or None,
            "primary_document": filing["primary_document"],
            "sec_url": sec_url,
            "processing_status": "detected",
        }

        supabase.table("filings").insert(row).execute()

        inserted_count += 1
        inserted_filings.append(accession_number)

    return {
        "ticker": ticker,
        "checked_count": len(relevant),
        "inserted_count": inserted_count,
        "skipped_count": skipped_count,
        "inserted_filings": inserted_filings,
    }
