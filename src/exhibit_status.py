from datetime import datetime, timezone

from src.database import get_supabase_client


def _update_exhibit_fields(accession_number: str, fields: dict) -> dict:
    """Apply exhibit-status fields to the matching filing and return the row.

    Raises:
        ValueError: If no filing matches the accession number.
    """
    supabase = get_supabase_client()
    response = (
        supabase.table("filings")
        .update(fields)
        .eq("accession_number", accession_number)
        .execute()
    )
    if not response.data:
        raise ValueError(
            f"No filing found with accession_number={accession_number!r}."
        )
    return response.data[0]


def _checked_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mark_exhibit_processed(
    accession_number: str,
    earnings_release_document_id: int,
) -> dict:
    """Record a successfully ingested earnings-release exhibit on the filing."""
    return _update_exhibit_fields(
        accession_number,
        {
            "exhibit_processing_status": "processed",
            "earnings_release_document_id": earnings_release_document_id,
            "exhibit_checked_at": _checked_now(),
            "exhibit_processing_error": None,
        },
    )


def mark_exhibit_not_found(accession_number: str) -> dict:
    """Record that the filing has no likely earnings-release exhibit."""
    return _update_exhibit_fields(
        accession_number,
        {
            "exhibit_processing_status": "not_found",
            "earnings_release_document_id": None,
            "exhibit_checked_at": _checked_now(),
            "exhibit_processing_error": None,
        },
    )


def mark_exhibit_failed(accession_number: str, error_message: str) -> dict:
    """Record an exhibit-processing failure so it can be retried explicitly."""
    return _update_exhibit_fields(
        accession_number,
        {
            "exhibit_processing_status": "failed",
            "exhibit_checked_at": _checked_now(),
            "exhibit_processing_error": error_message,
        },
    )
