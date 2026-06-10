from datetime import datetime, timezone

from src.database import get_supabase_client


def _update_extraction_fields(accession_number: str, fields: dict) -> dict:
    """Apply claim-extraction fields to the matching filing and return the row.

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


def _extracted_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mark_claim_extraction_pending_review(accession_number: str) -> dict:
    """Record a successful extraction run; drafted claims await review."""
    return _update_extraction_fields(
        accession_number,
        {
            "claim_extraction_status": "pending_review",
            "claim_extracted_at": _extracted_now(),
            "claim_extraction_error": None,
        },
    )


def mark_claim_extraction_failed(accession_number: str, error_message: str) -> dict:
    """Record a failed extraction run with its error message."""
    return _update_extraction_fields(
        accession_number,
        {
            "claim_extraction_status": "failed",
            "claim_extracted_at": _extracted_now(),
            "claim_extraction_error": error_message,
        },
    )


def mark_claim_extraction_approved(accession_number: str) -> dict:
    """Record that every grounded drafted claim was reviewed and promoted."""
    return _update_extraction_fields(
        accession_number,
        {
            "claim_extraction_status": "approved",
            "claim_extraction_error": None,
        },
    )
