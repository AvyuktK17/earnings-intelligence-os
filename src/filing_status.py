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
                "processing_error": None,
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
                "processing_error": None,
            }
        )
        .eq("accession_number", accession_number)
        .execute()
    )

    return response.data[0]


def record_filing_storage_paths(
    accession_number: str,
    html_storage_path: str,
    text_storage_path: str,
) -> dict:
    """Record the Supabase Storage paths for a filing's HTML and text files.

    Args:
        accession_number: The filing's unique accession number.
        html_storage_path: Storage path of the uploaded HTML file.
        text_storage_path: Storage path of the uploaded plain-text file.

    Returns:
        The updated row from the filings table.
    """
    supabase = get_supabase_client()

    response = (
        supabase.table("filings")
        .update(
            {
                "html_storage_path": html_storage_path,
                "text_storage_path": text_storage_path,
            }
        )
        .eq("accession_number", accession_number)
        .execute()
    )

    return response.data[0]


def mark_filing_failed(accession_number: str, error_message: str) -> dict:
    """Mark a filing as failed and store the error message.

    Args:
        accession_number: The filing's unique accession number.
        error_message: Description of what went wrong.

    Returns:
        The updated row from the filings table.
    """
    supabase = get_supabase_client()

    response = (
        supabase.table("filings")
        .update(
            {
                "processing_status": "failed",
                "processing_error": error_message,
            }
        )
        .eq("accession_number", accession_number)
        .execute()
    )

    return response.data[0]
