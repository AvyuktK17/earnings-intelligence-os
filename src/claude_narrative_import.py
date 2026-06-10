"""Import locally generated Claude-assisted narrative drafts as review records.

Bundle B2.2 keeps Claude generation **manual and local**: an analyst runs
``export_report_packet.py``, invokes the ``/semiconductor-equity-research-report``
Claude Code skill, and saves a Markdown draft locally. This module imports that
local Markdown into ``research_reports`` as a **private draft** awaiting human
review — it never calls the Claude API or Gemini, never mutates trusted claims,
and never publishes anything.

An imported draft is `report_status = "draft"`, `generator_type =
"claude_assisted"`. It stays private (excluded from public report endpoints)
until an analyst approves it through ``src.research_report_review``.

Evidence links are reused from trusted sources: from the deterministic source
report's ``report_evidence_links`` when a ``source_report_id`` is given,
otherwise derived from the filing's trusted promoted claims — so a narrative
draft carries the same auditable evidence trail as the deterministic report.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone

from src.database import get_supabase_client
from src.quantitative import build_metric_series
from src.research_report import (
    _accession_from_reference,
    _latest_valuation,
    _metric_rows,
    _select_accession,
    _trusted_claims,
)

GENERATOR_TYPE = "claude_assisted"
DRAFT_STATUS = "draft"
REPORT_TYPE_DEFAULT = "earnings_update"

# The exact label a Claude-assisted draft must carry (written by the skill).
REQUIRED_LABEL = "Claude-assisted draft for analyst review"

# Minimum body length below which a draft is treated as empty/incomplete.
_MIN_CONTENT_CHARS = 200


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: str) -> str:
    """Stable SHA-256 of a file's bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_draft_markdown(markdown_content: str) -> None:
    """Reject empty, unlabelled, or obviously incomplete drafts.

    Raises:
        ValueError: when the content is missing the required review label, is
            too short, or has no Markdown sections.
    """
    if not markdown_content or not markdown_content.strip():
        raise ValueError("Draft markdown is empty.")
    if REQUIRED_LABEL not in markdown_content:
        raise ValueError(
            "Draft markdown is missing the required label "
            f"{REQUIRED_LABEL!r}; refusing to import."
        )
    stripped = markdown_content.strip()
    if len(stripped) < _MIN_CONTENT_CHARS or "## " not in markdown_content:
        raise ValueError(
            "Draft markdown looks incomplete (too short or has no sections); "
            "refusing to import."
        )


def _next_claude_version(supabase, ticker: str, report_type: str) -> int:
    """Next version number for ``(ticker, report_type)``.

    The ``research_reports`` unique constraint is ``(ticker, report_type,
    version_number)`` — it does **not** include ``generator_type`` — so version
    numbers share one sequence across deterministic and Claude-assisted reports.
    Versioning per generator type would collide with deterministic versions, so
    we take the global max for the ticker/report_type and increment.
    """
    existing = (
        supabase.table("research_reports")
        .select("version_number")
        .eq("ticker", ticker)
        .eq("report_type", report_type)
        .order("version_number", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return (existing[0]["version_number"] + 1) if existing else 1


def _evidence_links_from_source_report(supabase, source_report_id: int) -> list[dict]:
    """Copy evidence-link records from a deterministic source report."""
    rows = (
        supabase.table("report_evidence_links")
        .select(
            "qualitative_claim_id, source_chunk_id, accession_number, "
            "document_key, section_name, supporting_excerpt"
        )
        .eq("research_report_id", source_report_id)
        .order("id", desc=False)
        .execute()
        .data
    )
    return rows


def _evidence_links_from_trusted_claims(
    supabase, ticker: str, accession_number: str
) -> list[dict]:
    """Derive evidence links from the filing's trusted promoted claims."""
    claims = [
        c
        for c in _trusted_claims(supabase, ticker)
        if _accession_from_reference(c.get("source_reference")) == accession_number
    ]
    return [
        {
            "qualitative_claim_id": c.get("proposed_claim_id"),
            "source_chunk_id": c.get("source_chunk_id"),
            "accession_number": accession_number,
            "document_key": c.get("document_key"),
            "section_name": "reviewed_takeaways",
            "supporting_excerpt": c.get("supporting_excerpt"),
        }
        for c in claims
    ]


def _insert_evidence_links(supabase, report_id: int, links: list[dict]) -> int:
    """Insert evidence-link rows for a report; returns the count inserted."""
    if not links:
        return 0
    rows = [
        {
            "research_report_id": report_id,
            "qualitative_claim_id": link.get("qualitative_claim_id"),
            "source_chunk_id": link.get("source_chunk_id"),
            "accession_number": link.get("accession_number"),
            "document_key": link.get("document_key"),
            "section_name": link.get("section_name"),
            "supporting_excerpt": link.get("supporting_excerpt"),
        }
        for link in links
    ]
    supabase.table("report_evidence_links").insert(rows).execute()
    return len(rows)


def insert_claude_draft(
    *,
    ticker: str,
    markdown_content: str,
    accession_number: str | None = None,
    source_report_id: int | None = None,
    source_packet_hash: str | None = None,
    report_type: str = REPORT_TYPE_DEFAULT,
    supabase=None,
) -> dict:
    """Validate and insert a Claude-assisted narrative draft (shared core).

    Used by both the file-based CLI service and the API import endpoint. No
    Claude/Gemini calls, no trusted-claim mutation, no overwrite of prior
    reports (always a new version).

    Raises:
        ValueError: invalid label/content (400-class), or unknown company /
            filing (404-class, message prefixed for the API mapper).
    """
    supabase = supabase or get_supabase_client()
    ticker = ticker.upper()
    validate_draft_markdown(markdown_content)

    company_rows = (
        supabase.table("companies")
        .select("ticker, company_name")
        .eq("ticker", ticker)
        .execute()
        .data
    )
    if not company_rows:
        raise ValueError(f"No monitored company found for ticker={ticker!r}.")
    company = company_rows[0]

    all_claims = _trusted_claims(supabase, ticker)
    if accession_number is None:
        accession_number = _select_accession(supabase, ticker, all_claims)

    filing_rows = (
        supabase.table("filings")
        .select("accession_number")
        .eq("accession_number", accession_number)
        .execute()
        .data
    )
    if not filing_rows:
        raise ValueError(
            f"No filing found with accession_number={accession_number!r}."
        )

    # Provenance counts: prefer the deterministic source report's stored counts;
    # otherwise compute deterministically from trusted sources.
    source_report = None
    if source_report_id is not None:
        source_rows = (
            supabase.table("research_reports")
            .select(
                "id, source_claim_count, source_metric_count, "
                "valuation_snapshot_date"
            )
            .eq("id", source_report_id)
            .execute()
            .data
        )
        if not source_rows:
            raise ValueError(
                f"No research report found with id={source_report_id} "
                "(source_report_id)."
            )
        source_report = source_rows[0]

    if source_report is not None:
        source_claim_count = source_report.get("source_claim_count")
        source_metric_count = source_report.get("source_metric_count")
        valuation_snapshot_date = source_report.get("valuation_snapshot_date")
    else:
        scoped_claims = [
            c
            for c in all_claims
            if _accession_from_reference(c.get("source_reference"))
            == accession_number
        ]
        source_claim_count = len(scoped_claims)
        source_metric_count = len(build_metric_series(_metric_rows(supabase, ticker)))
        snapshot = _latest_valuation(supabase, ticker)
        valuation_snapshot_date = (
            snapshot.get("share_price_date") if snapshot else None
        )

    version_number = _next_claude_version(supabase, ticker, report_type)
    title = f"{company['company_name']} ({ticker}) — Earnings Update (Claude-assisted)"
    imported_at = datetime.now(timezone.utc).isoformat()

    inserted = (
        supabase.table("research_reports")
        .insert(
            {
                "ticker": ticker,
                "accession_number": accession_number,
                "report_type": report_type,
                "report_status": DRAFT_STATUS,
                "version_number": version_number,
                "title": title,
                "markdown_content": markdown_content,
                "generator_type": GENERATOR_TYPE,
                "source_report_id": source_report_id,
                "source_packet_hash": source_packet_hash,
                "imported_at": imported_at,
                "source_claim_count": source_claim_count,
                "source_metric_count": source_metric_count,
                "valuation_snapshot_date": valuation_snapshot_date,
                "generated_at": imported_at,
            }
        )
        .execute()
        .data
    )
    report_id = inserted[0]["id"]

    # Reuse trusted evidence links (source report first, else trusted claims).
    links = []
    if source_report_id is not None:
        links = _evidence_links_from_source_report(supabase, source_report_id)
    if not links:
        links = _evidence_links_from_trusted_claims(
            supabase, ticker, accession_number
        )
    evidence_link_count = _insert_evidence_links(supabase, report_id, links)

    # Audit row: a completed import run (no LLM was called here).
    supabase.table("report_generation_runs").insert(
        {
            "ticker": ticker,
            "accession_number": accession_number,
            "report_type": report_type,
            "generator_type": GENERATOR_TYPE,
            "run_status": "completed",
            "report_id": report_id,
            "started_at": imported_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    ).execute()

    return {
        "report_id": report_id,
        "ticker": ticker,
        "accession_number": accession_number,
        "report_type": report_type,
        "report_status": DRAFT_STATUS,
        "version_number": version_number,
        "source_report_id": source_report_id,
        "source_packet_hash": source_packet_hash,
        "source_claim_count": source_claim_count,
        "evidence_link_count": evidence_link_count,
    }


def import_claude_assisted_narrative(
    ticker: str,
    markdown_path: str,
    accession_number: str | None = None,
    source_report_id: int | None = None,
    source_packet_path: str | None = None,
    report_type: str = REPORT_TYPE_DEFAULT,
) -> dict:
    """Import a local Claude-assisted narrative Markdown file as a draft report.

    Args:
        ticker: Company ticker (case-insensitive).
        markdown_path: Path to the locally generated narrative Markdown.
        accession_number: Filing to anchor on; defaults to the most recent
            filing with trusted claims (matching the report engine).
        source_report_id: Optional deterministic report this narrative was
            drafted from; its evidence links and provenance counts are reused.
        source_packet_path: Optional path to the report packet the narrative was
            drafted from; its SHA-256 is recorded as ``source_packet_hash``.
        report_type: Report family (default ``"earnings_update"``).

    Returns:
        Imported draft metadata (see ``insert_claude_draft``).

    Raises:
        FileNotFoundError: if the markdown or packet file does not exist.
        ValueError: invalid/unlabelled draft, or unknown company/filing.
    """
    if not os.path.exists(markdown_path):
        raise FileNotFoundError(f"Narrative markdown not found: {markdown_path!r}.")
    markdown_content = open(markdown_path, encoding="utf-8").read()

    source_packet_hash = None
    if source_packet_path is not None:
        if not os.path.exists(source_packet_path):
            raise FileNotFoundError(
                f"Source packet not found: {source_packet_path!r}."
            )
        source_packet_hash = _sha256_file(source_packet_path)

    return insert_claude_draft(
        ticker=ticker,
        markdown_content=markdown_content,
        accession_number=accession_number,
        source_report_id=source_report_id,
        source_packet_hash=source_packet_hash,
        report_type=report_type,
    )
