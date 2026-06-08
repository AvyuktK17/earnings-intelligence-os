from src.database import get_supabase_client
from src.process_filing import process_filing
from src.filing_status import mark_filing_failed


def backfill_missing_storage_paths(limit: int = 3) -> list[dict]:
    """Re-process parsed filings that are missing Storage paths.

    Finds rows where processing_status='parsed' but html_storage_path or
    text_storage_path is null, and runs process_filing() on each to upload
    the files and record the paths.

    Args:
        limit: Maximum number of filings to repair in this run.

    Returns:
        A list of result dicts, one per filing attempted. Failed filings are
        included with status='failed' and an error_message key.
    """
    supabase = get_supabase_client()

    response = (
        supabase.table("filings")
        .select("ticker, accession_number, sec_url, filing_date")
        .eq("processing_status", "parsed")
        .or_("html_storage_path.is.null,text_storage_path.is.null")
        .order("filing_date", desc=True)
        .limit(limit)
        .execute()
    )

    filings = response.data
    results = []

    for filing in filings:
        accession_number = filing.get("accession_number", "")
        try:
            result = process_filing(filing)
        except Exception as exc:
            error_message = str(exc)
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

        results.append(
            {
                "ticker": result["ticker"],
                "accession_number": result["accession_number"],
                "status": result["status"],
                "html_storage_path": result["html_storage_path"],
                "text_storage_path": result["text_storage_path"],
            }
        )

    return results
