"""Dashboard-triggered grounded claim extraction for extraction-ready filings.

Wraps the existing document-specific Gemini extractor with filing-level
state tracking. Extraction stays strictly manual: nothing here is scheduled,
and the admin-protected API endpoint is the only non-CLI caller. Gemini's
free-tier quota is protected by surfacing quota errors as a distinct
exception so callers can back off instead of retrying.
"""

from src.claim_extraction_status import (
    mark_claim_extraction_failed,
    mark_claim_extraction_pending_review,
)
from src.claim_extractor import extract_and_store_claims
from src.database import get_supabase_client

# Marker strings that identify Gemini quota / rate-limit / availability
# errors (google.genai ClientError 429 or ServerError 503) without a hard
# dependency on the SDK's exception classes.
_QUOTA_MARKERS = (
    "429",
    "RESOURCE_EXHAUSTED",
    "quota",
    "rate",
    "503",
    "UNAVAILABLE",
    "high demand",
)

# Cap what we persist to claim_extraction_error: enough to diagnose, never
# a full provider response dump.
_MAX_STORED_ERROR_CHARS = 500


class ClaimExtractionQuotaError(RuntimeError):
    """Gemini quota or rate limit reached; retry after the window resets."""


class ClaimExtractionError(RuntimeError):
    """Unexpected extraction failure, re-raised with a caller-safe message."""


def extract_claims_for_ready_filing(
    accession_number: str,
    max_claims: int = 5,
) -> dict:
    """Run grounded claim extraction on a filing's processed earnings exhibit.

    Requires the filing to be extraction-ready (exhibit processed and
    chunked). Reuses the existing grounded extractor, which only replaces
    pending drafts after Gemini returns valid claims — a failed call never
    deletes existing pending rows. On success the filing is marked
    "pending_review"; on failure it is marked "failed" with the error.

    Args:
        accession_number: The filing's unique accession number.
        max_claims: Maximum number of claims to request from Gemini.

    Returns:
        The extractor result (ticker, accession_number, document_key,
        proposed_claim_count, skipped_invalid_count, proposed_claims) plus
        claim_extraction_status.

    Raises:
        ValueError: If the filing does not exist, is not extraction-ready,
            or the extractor reports a workflow error (e.g. every claim
            failed grounding validation).
        ClaimExtractionQuotaError: On Gemini quota / rate-limit failures.
        ClaimExtractionError: On any other unexpected provider failure.
    """
    supabase = get_supabase_client()

    filings = (
        supabase.table("filings")
        .select(
            "ticker, accession_number, exhibit_processing_status, "
            "earnings_release_document_id"
        )
        .eq("accession_number", accession_number)
        .execute()
        .data
    )
    if not filings:
        raise ValueError(
            f"No filing found with accession_number={accession_number!r}."
        )
    filing = filings[0]

    if (
        filing["exhibit_processing_status"] != "processed"
        or filing["earnings_release_document_id"] is None
    ):
        raise ValueError(
            f"Filing {accession_number} has no processed earnings-release "
            "exhibit. Only extraction-ready filings can have claims extracted."
        )

    documents = (
        supabase.table("filing_documents")
        .select("filename")
        .eq("id", filing["earnings_release_document_id"])
        .execute()
        .data
    )
    if not documents:
        raise ValueError(
            f"Filing {accession_number} references a missing "
            "filing_documents row."
        )
    document_key = f"exhibit:{documents[0]['filename']}"

    try:
        result = extract_and_store_claims(
            accession_number=accession_number,
            max_claims=max_claims,
            document_key=document_key,
        )
    except ValueError as exc:
        # Workflow failure with our own safe message (no chunks, every claim
        # failed validation, ...). Existing pending drafts were preserved.
        mark_claim_extraction_failed(
            accession_number, str(exc)[:_MAX_STORED_ERROR_CHARS]
        )
        raise
    except Exception as exc:
        detail = str(exc)
        mark_claim_extraction_failed(
            accession_number, detail[:_MAX_STORED_ERROR_CHARS]
        )
        if any(marker in detail for marker in _QUOTA_MARKERS):
            raise ClaimExtractionQuotaError(
                "Gemini API quota or rate limit reached. No pending drafts "
                "were deleted. Try again after the free-tier window resets."
            ) from exc
        raise ClaimExtractionError(
            "Claim extraction failed unexpectedly. The error was recorded "
            "on the filing and no pending drafts were deleted."
        ) from exc

    status_row = mark_claim_extraction_pending_review(accession_number)
    return {
        **result,
        "claim_extraction_status": status_row["claim_extraction_status"],
    }
