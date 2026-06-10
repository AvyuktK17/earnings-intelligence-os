"""Safe promotion of human-reviewed proposed claims into qualitative_claims.

Only rows with review_status 'approved' or 'edited' and a non-null
source_chunk_id are eligible. Rows already present in qualitative_claims
(matched by proposed_claim_id) are silently skipped so the function is
safe to rerun without creating duplicates.

No AI calls are made. Pending and rejected claims are never promoted.
"""

from datetime import datetime, timezone

from src.claim_extraction_status import mark_claim_extraction_approved
from src.database import get_supabase_client


def promote_reviewed_claims(
    ticker: str | None = None,
    accession_number: str | None = None,
) -> dict:
    """Promote eligible reviewed proposed claims into qualitative_claims.

    Args:
        ticker: Optional ticker filter (normalized to uppercase). Only
            claims for this ticker are considered.
        accession_number: Optional accession-number filter. Only claims
            for this filing are considered.

    When both filters are omitted, every eligible claim is promoted
    (the original global behavior).

    Returns:
        A dict with eligible_count, promoted_count, skipped_existing_count,
        promoted_claims (list of summary dicts for newly inserted rows), and
        approved_filings (accession numbers whose claim_extraction_status
        was advanced to "approved" because no grounded pending rows remain).
    """
    supabase = get_supabase_client()

    # Build a ticker → company_name lookup from the companies table.
    companies_resp = supabase.table("companies").select("ticker, company_name").execute()
    company_map = {r["ticker"]: r["company_name"] for r in companies_resp.data}

    # Fetch eligible proposed claims: approved or edited, grounded,
    # optionally scoped to one ticker and/or one filing.
    query = (
        supabase.table("proposed_claims")
        .select("*")
        .in_("review_status", ["approved", "edited"])
        .not_.is_("source_chunk_id", "null")
    )
    if ticker is not None:
        query = query.eq("ticker", ticker.upper())
    if accession_number is not None:
        query = query.eq("accession_number", accession_number)
    eligible = query.execute().data

    promoted = []
    skipped_existing = 0

    for claim in eligible:
        # Skip if this proposed claim has already been promoted.
        already_promoted = (
            supabase.table("qualitative_claims")
            .select("proposed_claim_id")
            .eq("proposed_claim_id", claim["id"])
            .execute()
            .data
        )
        if already_promoted:
            skipped_existing += 1
            continue

        # Use edited_claim_text when the reviewer corrected the wording.
        if claim["review_status"] == "edited" and claim.get("edited_claim_text"):
            trusted_text = claim["edited_claim_text"]
        else:
            trusted_text = claim["claim_text"]

        now = datetime.now(timezone.utc).isoformat()
        source_ref = (
            f"{claim['accession_number']} | {claim['document_key']} "
            f"| chunk:{claim['source_chunk_id']}"
        )

        row = {
            "company": company_map.get(claim["ticker"], claim["ticker"]),
            "ticker": claim["ticker"],
            "source_type": "SEC_FILING",
            "source_reference": source_ref,
            "theme": claim["theme"],
            "claim": trusted_text,
            "supporting_excerpt": claim["supporting_excerpt"],
            "factual_or_interpretive": claim["claim_type"],
            "confidence": claim["confidence"],
            "human_reviewed": "Yes",
            "proposed_claim_id": claim["id"],
            "source_chunk_id": claim["source_chunk_id"],
            "document_key": claim["document_key"],
            "reviewer_notes": claim.get("reviewer_notes"),
            "promoted_at": now,
        }

        supabase.table("qualitative_claims").insert(row).execute()
        promoted.append(
            {
                "proposed_claim_id": claim["id"],
                "ticker": claim["ticker"],
                "theme": claim["theme"],
                "claim": trusted_text,
                "source_chunk_id": claim["source_chunk_id"],
                "document_key": claim["document_key"],
            }
        )

    # Filing-level extraction lifecycle: a filing touched by this promotion
    # run whose grounded claims are all reviewed (no grounded pending rows
    # left) is marked "approved". Only filings with eligible claims in this
    # run are considered, so reviewing a single claim never flips the status
    # and scoped promotion only updates the matching filing. Ungrounded
    # legacy rows are ignored by both the eligibility and pending filters.
    approved_filings = []
    for affected_accession in sorted({c["accession_number"] for c in eligible}):
        pending_grounded = (
            supabase.table("proposed_claims")
            .select("id", count="exact")
            .eq("accession_number", affected_accession)
            .eq("review_status", "pending")
            .not_.is_("source_chunk_id", "null")
            .execute()
            .count
            or 0
        )
        if pending_grounded == 0:
            try:
                mark_claim_extraction_approved(affected_accession)
                approved_filings.append(affected_accession)
            except ValueError:
                # Claims without a filings row (e.g. temporary test data)
                # have no filing-level status to update.
                pass

    return {
        "eligible_count": len(eligible),
        "promoted_count": len(promoted),
        "skipped_existing_count": skipped_existing,
        "promoted_claims": promoted,
        "approved_filings": approved_filings,
    }
