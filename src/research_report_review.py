"""Analyst review controls for Claude-assisted narrative reports.

These actions apply **only** to ``generator_type = "claude_assisted"`` reports
in the ``draft`` state. They never touch deterministic reports, never mutate
trusted ``qualitative_claims``, and never call the Claude API or Gemini.

Transitions:

* ``approve`` — draft → reviewed (in place).
* ``edit_and_approve`` — preserve the original draft as an immutable
  ``superseded`` record and create a **new** ``reviewed`` version carrying the
  edited markdown plus copied provenance and evidence links.
* ``reject`` — draft → rejected, recording a required rejection reason.

A draft can only be acted on once; acting on a non-draft (already reviewed,
superseded, rejected) is an invalid transition.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.claude_narrative_import import (
    DRAFT_STATUS,
    GENERATOR_TYPE,
    _next_claude_version,
)
from src.database import get_supabase_client

REVIEWED_STATUS = "reviewed"
REJECTED_STATUS = "rejected"
SUPERSEDED_STATUS = "superseded"

_REPORT_COLUMNS = (
    "id, ticker, accession_number, report_type, report_status, version_number, "
    "title, markdown_content, generator_type, source_report_id, "
    "source_packet_hash, imported_at, reviewed_at, reviewer_notes, "
    "rejection_reason, source_claim_count, source_metric_count, "
    "valuation_snapshot_date, generated_at"
)


def _fetch_report(supabase, report_id: int) -> dict:
    rows = (
        supabase.table("research_reports")
        .select(_REPORT_COLUMNS)
        .eq("id", report_id)
        .execute()
        .data
    )
    if not rows:
        raise ValueError(f"No research report found with id={report_id}.")
    return rows[0]


def _require_claude_draft(supabase, report_id: int) -> dict:
    """Load a report and require it to be a Claude-assisted draft.

    Raises:
        ValueError: 404-class when missing; 400-class when it is not a
            Claude-assisted report or is not in the ``draft`` state.
    """
    report = _fetch_report(supabase, report_id)
    if report.get("generator_type") != GENERATOR_TYPE:
        raise ValueError(
            f"Report id={report_id} is not a Claude-assisted report; this "
            "review workflow applies only to Claude-assisted drafts."
        )
    if report.get("report_status") != DRAFT_STATUS:
        raise ValueError(
            f"Report id={report_id} is in state "
            f"{report.get('report_status')!r}, not 'draft'; invalid transition."
        )
    return report


def approve_research_report(
    report_id: int, reviewer_notes: str | None = None
) -> dict:
    """Approve a Claude-assisted draft in place (draft → reviewed)."""
    supabase = get_supabase_client()
    _require_claude_draft(supabase, report_id)
    supabase.table("research_reports").update(
        {
            "report_status": REVIEWED_STATUS,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "reviewer_notes": reviewer_notes,
        }
    ).eq("id", report_id).execute()
    return _fetch_report(supabase, report_id)


def edit_and_approve_research_report(
    report_id: int,
    edited_markdown_content: str,
    reviewer_notes: str | None = None,
) -> dict:
    """Create a new reviewed version from edited markdown; supersede the draft.

    The original imported draft is preserved immutably as ``superseded``; a new
    ``reviewed`` ``claude_assisted`` row is created with the next version number,
    the edited markdown, copied provenance, and copied evidence links.

    Raises:
        ValueError: empty edit, or the original is not a Claude-assisted draft.
    """
    if not edited_markdown_content or not edited_markdown_content.strip():
        raise ValueError("Edited markdown content must not be empty.")

    supabase = get_supabase_client()
    original = _require_claude_draft(supabase, report_id)

    version_number = _next_claude_version(
        supabase, original["ticker"], original["report_type"]
    )
    reviewed_at = datetime.now(timezone.utc).isoformat()

    inserted = (
        supabase.table("research_reports")
        .insert(
            {
                "ticker": original["ticker"],
                "accession_number": original["accession_number"],
                "report_type": original["report_type"],
                "report_status": REVIEWED_STATUS,
                "version_number": version_number,
                "title": original["title"],
                "markdown_content": edited_markdown_content,
                "generator_type": GENERATOR_TYPE,
                "source_report_id": original["id"],
                "source_packet_hash": original.get("source_packet_hash"),
                "imported_at": original.get("imported_at"),
                "reviewed_at": reviewed_at,
                "reviewer_notes": reviewer_notes,
                "source_claim_count": original.get("source_claim_count"),
                "source_metric_count": original.get("source_metric_count"),
                "valuation_snapshot_date": original.get("valuation_snapshot_date"),
                "generated_at": reviewed_at,
            }
        )
        .execute()
        .data
    )
    new_report_id = inserted[0]["id"]

    # Copy the original draft's evidence links to the new reviewed version.
    original_links = (
        supabase.table("report_evidence_links")
        .select(
            "qualitative_claim_id, source_chunk_id, accession_number, "
            "document_key, section_name, supporting_excerpt"
        )
        .eq("research_report_id", report_id)
        .order("id", desc=False)
        .execute()
        .data
    )
    if original_links:
        supabase.table("report_evidence_links").insert(
            [{**link, "research_report_id": new_report_id} for link in original_links]
        ).execute()

    # Preserve the original draft immutably as superseded.
    supabase.table("research_reports").update(
        {"report_status": SUPERSEDED_STATUS}
    ).eq("id", report_id).execute()

    return _fetch_report(supabase, new_report_id)


def reject_research_report(
    report_id: int,
    rejection_reason: str,
    reviewer_notes: str | None = None,
) -> dict:
    """Reject a Claude-assisted draft (draft → rejected)."""
    if not rejection_reason or not rejection_reason.strip():
        raise ValueError("A rejection reason is required.")

    supabase = get_supabase_client()
    _require_claude_draft(supabase, report_id)
    supabase.table("research_reports").update(
        {
            "report_status": REJECTED_STATUS,
            "rejection_reason": rejection_reason,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "reviewer_notes": reviewer_notes,
        }
    ).eq("id", report_id).execute()
    return _fetch_report(supabase, report_id)
