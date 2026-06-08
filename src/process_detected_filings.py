from src.database import get_supabase_client
from src.process_filing import process_filing
from src.filing_status import mark_filing_failed


def process_detected_filings(limit: int = 1) -> list[dict]:
    """Fetch filings with status 'detected' and process them.

    Args:
        limit: Maximum number of filings to process in this run.

    Returns:
        A list of result dicts, one per filing attempted. Failed filings are
        included with status='failed' and an error_message key.
    """
    supabase = get_supabase_client()

    response = (
        supabase.table("filings")
        .select("ticker, accession_number, sec_url, filing_date")
        .eq("processing_status", "detected")
        .order("filing_date", desc=True)
        .limit(limit)
        .execute()
    )

    filings = response.data
    results = []

    for filing in filings:
        try:
            result = process_filing(filing)
        except Exception as exc:
            error_message = str(exc)
            accession_number = filing.get("accession_number", "")
            if accession_number:
                mark_filing_failed(accession_number, error_message)
            results.append(
                {
                    "ticker": filing.get("ticker", ""),
                    "accession_number": accession_number,
                    "status": "failed",
                    "error_message": error_message,
                }
            )
            continue

        results.append(result)

    return results
