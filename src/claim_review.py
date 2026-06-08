"""Human-review backend for proposed claims.

Three operations are supported:
  approve_claim            -- accept the claim as-is
  approve_claim_with_edits -- accept the claim with a wording correction
  reject_claim             -- discard the claim

All three functions require the claim to exist. Approval and editing
additionally require source_chunk_id to be populated (i.e. the claim
must have been produced by a grounded extractor run). Rejection is
allowed on any row, including legacy ungrounded rows.

No AI calls are made. Trusted qualitative_claims is not touched here.
"""

from datetime import datetime, timezone

from src.database import get_supabase_client


def _fetch_claim(supabase, claim_id: int) -> dict:
    """Return the proposed_claims row for claim_id, or raise ValueError."""
    resp = (
        supabase.table("proposed_claims")
        .select("*")
        .eq("id", claim_id)
        .execute()
    )
    if not resp.data:
        raise ValueError(f"No proposed claim found with id={claim_id}.")
    return resp.data[0]


def _require_grounded(claim: dict) -> None:
    """Raise ValueError if source_chunk_id is missing."""
    if claim.get("source_chunk_id") is None:
        raise ValueError(
            f"Claim {claim['id']} has no source_chunk_id. "
            "Ungrounded legacy claims cannot be approved. "
            "Re-extract the filing with the current extractor to obtain a grounded row."
        )


def approve_claim(claim_id: int, reviewer_notes: str | None = None) -> dict:
    """Approve a proposed claim without editing its text.

    Args:
        claim_id: The id of the proposed_claims row to approve.
        reviewer_notes: Optional notes from the reviewer.

    Returns:
        The updated proposed_claims row as a dict.

    Raises:
        ValueError: If the claim does not exist or has no source_chunk_id.
    """
    supabase = get_supabase_client()
    claim = _fetch_claim(supabase, claim_id)
    _require_grounded(claim)

    now = datetime.now(timezone.utc).isoformat()
    supabase.table("proposed_claims").update(
        {
            "review_status": "approved",
            "reviewer_notes": reviewer_notes,
            "reviewed_at": now,
        }
    ).eq("id", claim_id).execute()

    return _fetch_claim(supabase, claim_id)


def approve_claim_with_edits(
    claim_id: int,
    edited_claim_text: str,
    reviewer_notes: str | None = None,
) -> dict:
    """Approve a proposed claim with a corrected wording.

    The original claim_text is preserved. edited_claim_text holds the
    reviewer's improved version. review_status is set to "edited".

    Args:
        claim_id: The id of the proposed_claims row to approve.
        edited_claim_text: The reviewer's corrected claim text (must not be empty).
        reviewer_notes: Optional notes from the reviewer.

    Returns:
        The updated proposed_claims row as a dict.

    Raises:
        ValueError: If the claim does not exist, has no source_chunk_id,
                    or edited_claim_text is empty.
    """
    supabase = get_supabase_client()
    claim = _fetch_claim(supabase, claim_id)
    _require_grounded(claim)

    if not edited_claim_text or not edited_claim_text.strip():
        raise ValueError("edited_claim_text must be a non-empty string.")

    now = datetime.now(timezone.utc).isoformat()
    supabase.table("proposed_claims").update(
        {
            "review_status": "edited",
            "edited_claim_text": edited_claim_text.strip(),
            "reviewer_notes": reviewer_notes,
            "reviewed_at": now,
        }
    ).eq("id", claim_id).execute()

    return _fetch_claim(supabase, claim_id)


def reject_claim(claim_id: int, reviewer_notes: str | None = None) -> dict:
    """Reject a proposed claim.

    Rejection is allowed even when source_chunk_id is missing, so legacy
    ungrounded rows can be cleaned up through the review workflow.

    Args:
        claim_id: The id of the proposed_claims row to reject.
        reviewer_notes: Optional notes from the reviewer.

    Returns:
        The updated proposed_claims row as a dict.

    Raises:
        ValueError: If the claim does not exist.
    """
    supabase = get_supabase_client()
    _fetch_claim(supabase, claim_id)  # existence check

    now = datetime.now(timezone.utc).isoformat()
    supabase.table("proposed_claims").update(
        {
            "review_status": "rejected",
            "reviewer_notes": reviewer_notes,
            "reviewed_at": now,
        }
    ).eq("id", claim_id).execute()

    return _fetch_claim(supabase, claim_id)
