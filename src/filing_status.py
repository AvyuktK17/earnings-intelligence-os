from datetime import datetime, timezone

from src.database import get_supabase_client


def mark_filing_downloaded(accession_number: str) -> dict:
    """Mark a filing as downloaded and record the timestamp.

    Args:
        accession_number: The filing's unique accession number.

    Returns:
        The updated row from the filings table.
    """
    supabase = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()

    response = (
        supabase.table("filings")
        .update(
            {
                "processing_status": "downloaded",
                "downloaded_at": now,
            }
        )
        .eq("accession_number", accession_number)
        .execute()
    )

    return response.data[0]


def mark_filing_parsed(accession_number: str) -> dict:
    """Mark a filing as parsed and record the timestamp.

    Args:
        accession_number: The filing's unique accession number.

    Returns:
        The updated row from the filings table.
    """
    supabase = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()

    response = (
        supabase.table("filings")
        .update(
            {
                "processing_status": "parsed",
                "parsed_at": now,
            }
        )
        .eq("accession_number", accession_number)
        .execute()
    )

    return response.data[0]
