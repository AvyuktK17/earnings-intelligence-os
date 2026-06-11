"""Post-promotion correction of trusted evidence claim wording.

Trusted ``qualitative_claims`` rows are normally immutable after promotion,
but an analyst sometimes spots a wording error only once a claim is visible
in the Evidence Explorer (e.g. a number that disagrees with the claim's own
supporting excerpt). This module supports exactly one narrow operation:
correcting the **claim text** of an already-promoted, grounded claim.

Audit trail uses the existing data model — no new schema:

* the source ``proposed_claims`` row keeps the original ``claim_text``
  untouched, records the correction in ``edited_claim_text``, sets
  ``review_status = "edited"`` and ``reviewed_at``, exactly as a
  pre-promotion edit-and-approve would;
* the ``qualitative_claims`` row gets the corrected ``claim`` wording and
  the reviewer's notes.

The excerpt may also be corrected — but only to another **literal quote
from the same source chunk**: a corrected excerpt must pass the identical
whitespace-normalized substring check that grounded extraction enforces
(``_normalize_ws`` semantics from ``src.claim_extractor``). The chunk
itself (``source_chunk_id``, ``document_key``) and all other provenance
fields can never change — corrections can change how a claim is worded or
which sentence of the chunk it quotes, never what document it cites.
The original excerpt is preserved untouched on the ``proposed_claims``
row, so the audit trail always shows what extraction produced.

No AI calls are made.
"""

import re
from datetime import datetime, timezone

from src.database import get_supabase_client


def _normalize_ws(text: str) -> str:
    """Whitespace normalization — identical to the grounded extractor's."""
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def correct_trusted_claim(
    claim_id: int,
    edited_claim_text: str | None = None,
    reviewer_notes: str | None = None,
    edited_supporting_excerpt: str | None = None,
) -> dict:
    """Correct the wording and/or excerpt of a trusted, grounded claim.

    Args:
        claim_id: The claim's ``proposed_claim_id`` (the stable key used by
            the public evidence endpoints).
        edited_claim_text: Corrected claim wording (optional).
        reviewer_notes: Optional note explaining the correction.
        edited_supporting_excerpt: Corrected excerpt (optional). Must be a
            literal substring of the claim's source chunk after whitespace
            normalization — the same grounding rule extraction enforces.

    At least one of ``edited_claim_text`` / ``edited_supporting_excerpt``
    is required.

    Returns:
        A summary dict with the claim id, ticker, previous and corrected
        wording, and the (previous and corrected) supporting excerpt.

    Raises:
        ValueError: If no trusted claim exists for ``claim_id``, the row is
            ungrounded, nothing was provided to correct, or the corrected
            excerpt is not a literal quote from the source chunk.
    """
    corrected_text = (edited_claim_text or "").strip() or None
    corrected_excerpt = (edited_supporting_excerpt or "").strip() or None
    if corrected_text is None and corrected_excerpt is None:
        raise ValueError(
            "Provide edited_claim_text and/or edited_supporting_excerpt."
        )

    supabase = get_supabase_client()

    trusted_rows = (
        supabase.table("qualitative_claims")
        .select(
            "proposed_claim_id, ticker, theme, claim, supporting_excerpt, "
            "source_reference, source_chunk_id, document_key"
        )
        .eq("proposed_claim_id", claim_id)
        .execute()
        .data
    )
    if not trusted_rows:
        raise ValueError(f"No trusted evidence claim found with id={claim_id}.")
    trusted = trusted_rows[0]
    if trusted.get("source_chunk_id") is None:
        raise ValueError(
            f"Trusted claim {claim_id} has no source_chunk_id. "
            "Ungrounded rows cannot be corrected through this workflow."
        )

    # A corrected excerpt must satisfy the extractor's grounding rule:
    # literal substring of the source chunk after whitespace normalization.
    if corrected_excerpt is not None:
        chunk_rows = (
            supabase.table("filing_chunks")
            .select("id, chunk_text")
            .eq("id", trusted["source_chunk_id"])
            .execute()
            .data
        )
        if not chunk_rows:
            raise ValueError(
                f"Trusted claim {claim_id} cites chunk "
                f"{trusted['source_chunk_id']}, which no longer exists."
            )
        chunk_text = chunk_rows[0]["chunk_text"] or ""
        corrected_excerpt = _normalize_ws(corrected_excerpt)
        if corrected_excerpt not in _normalize_ws(chunk_text):
            raise ValueError(
                "edited_supporting_excerpt is not a literal quote from the "
                "claim's source chunk. Corrections must quote the cited "
                "chunk exactly (whitespace differences are ignored)."
            )

    now = datetime.now(timezone.utc).isoformat()

    # Audit trail on the source draft row: original claim_text and original
    # supporting_excerpt are preserved untouched; a wording correction lands
    # in edited_claim_text (same shape as a pre-promotion edit-and-approve).
    draft_update: dict = {
        "review_status": "edited",
        "reviewer_notes": reviewer_notes,
        "reviewed_at": now,
    }
    if corrected_text is not None:
        draft_update["edited_claim_text"] = corrected_text
    supabase.table("proposed_claims").update(draft_update).eq(
        "id", claim_id
    ).execute()

    # The trusted row gets the corrected wording / validated excerpt. The
    # chunk reference and all other provenance fields are deliberately not
    # part of this update.
    trusted_update: dict = {"reviewer_notes": reviewer_notes}
    if corrected_text is not None:
        trusted_update["claim"] = corrected_text
    if corrected_excerpt is not None:
        trusted_update["supporting_excerpt"] = corrected_excerpt
    supabase.table("qualitative_claims").update(trusted_update).eq(
        "proposed_claim_id", claim_id
    ).execute()

    return {
        "qualitative_claim_id": claim_id,
        "ticker": trusted["ticker"],
        "theme": trusted["theme"],
        "previous_claim": trusted["claim"],
        "claim": corrected_text or trusted["claim"],
        "previous_supporting_excerpt": trusted["supporting_excerpt"],
        "supporting_excerpt": corrected_excerpt
        or trusted["supporting_excerpt"],
        "source_reference": trusted["source_reference"],
        "corrected_at": now,
    }
