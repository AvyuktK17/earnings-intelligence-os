from src.database import get_supabase_client
from src.filing_chunker import chunk_and_store_filing
from src.filing_status import mark_filing_chunked, mark_filing_failed


def backfill_missing_chunks(limit: int = 3) -> list[dict]:
    """Chunk parsed filings that have a text_storage_path but no chunks yet.

    Args:
        limit: Maximum number of filings to process in this run.

    Returns:
        A list of result dicts, one per filing attempted. Failed filings are
        included with status='failed' and an error_message key.
    """
    supabase = get_supabase_client()

    response = (
        supabase.table("filings")
        .select("ticker, accession_number, filing_date")
        .eq("processing_status", "parsed")
        .not_.is_("text_storage_path", "null")
        .order("filing_date", desc=True)
        .limit(limit)
        .execute()
    )

    filings = response.data
    results = []

    for filing in filings:
        accession_number = filing["accession_number"]
        try:
            chunk_result = chunk_and_store_filing(accession_number)
            mark_filing_chunked(accession_number)
        except Exception as exc:
            error_message = str(exc)
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
                "ticker": filing["ticker"],
                "accession_number": accession_number,
                "status": "chunked",
                "chunk_count": chunk_result["chunk_count"],
                "average_chunk_characters": chunk_result["average_chunk_characters"],
            }
        )

    return results
