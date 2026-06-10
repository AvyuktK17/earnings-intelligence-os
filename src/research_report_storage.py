"""Generate, render, persist, and version a deterministic research report.

Each call generates the next version of an earnings-update report for a ticker,
renders Markdown + HTML + PDF, uploads all three to private Supabase Storage,
inserts a ``research_reports`` row plus its ``report_evidence_links``, and
brackets the whole run with a ``report_generation_runs`` audit row. Prior
versions are never overwritten. No AI is called.

PDF export uses fpdf2 (pure-Python, no system dependencies) so it builds
reliably on Render where cairo/pango-based engines (WeasyPrint, xhtml2pdf) do
not install cleanly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fpdf import FPDF

from src.database import get_supabase_client
from src.research_report import generate_research_report
from src.storage import upload_file

_LOCAL_DIR = "output/reports"

# fpdf2's built-in Helvetica is a latin-1 core font, so transliterate the
# common non-latin-1 punctuation that appears in SEC excerpts before rendering.
# The stored Markdown/HTML keep full Unicode fidelity; only the PDF is coerced.
_PDF_TRANSLITERATIONS = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...", "•": "*",
    "™": "(TM)", "→": "->", "×": "x", "≈": "~",
    " ": " ",
}


def _latin1_safe(text: str) -> str:
    """Coerce text to a latin-1-renderable form for the core PDF font."""
    for src, dst in _PDF_TRANSLITERATIONS.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


def render_pdf(html: str, local_path: str) -> str:
    """Render report HTML to a PDF file with fpdf2; returns the local path.

    Feeds fpdf2 a body-only, latin-1-safe fragment (its HTML parser does not
    handle <head>/<style>/<meta>, and its core font is latin-1).
    """
    if "<body>" in html:
        html = html.split("<body>", 1)[1].split("</body>", 1)[0]
    body = _latin1_safe(html)

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    pdf.write_html(body)
    out = Path(local_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))
    return str(out)


def _next_version(supabase, ticker: str, report_type: str) -> int:
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


def generate_and_store_research_report(
    ticker: str,
    accession_number: str | None = None,
    report_type: str = "earnings_update",
) -> dict:
    """Generate, render, upload, and persist a versioned research report.

    Returns:
        Metadata for the stored report (id, version_number, storage paths,
        counts, and the evidence-link count).

    Raises:
        ValueError: If the company or filing cannot be found (no run row is
            left dangling — the audit row is marked failed first).
    """
    supabase = get_supabase_client()
    ticker = ticker.upper()
    started_at = datetime.now(timezone.utc).isoformat()

    run_row = (
        supabase.table("report_generation_runs")
        .insert(
            {
                "ticker": ticker,
                "accession_number": accession_number,
                "report_type": report_type,
                "generator_type": "deterministic",
                "run_status": "running",
                "started_at": started_at,
            }
        )
        .execute()
        .data
    )
    run_id = run_row[0]["id"]

    try:
        report = generate_research_report(ticker, accession_number, report_type)

        version_number = _next_version(supabase, ticker, report_type)
        ticker_lower = ticker.lower()
        base = f"reports/{ticker_lower}/{report_type}/v{version_number}"
        md_path, html_path, pdf_path = f"{base}.md", f"{base}.html", f"{base}.pdf"

        # Write locally (gitignored), then upload to private Storage.
        local_base = Path(_LOCAL_DIR) / ticker_lower / report_type
        local_base.mkdir(parents=True, exist_ok=True)
        local_md = local_base / f"v{version_number}.md"
        local_html = local_base / f"v{version_number}.html"
        local_pdf = local_base / f"v{version_number}.pdf"
        local_md.write_text(report["markdown"], encoding="utf-8")
        local_html.write_text(report["html"], encoding="utf-8")
        render_pdf(report["html"], str(local_pdf))

        upload_file(str(local_md), md_path)
        upload_file(str(local_html), html_path)
        upload_file(str(local_pdf), pdf_path)

        generated_at = datetime.now(timezone.utc).isoformat()
        inserted = (
            supabase.table("research_reports")
            .insert(
                {
                    "ticker": ticker,
                    "accession_number": report["accession_number"],
                    "report_type": report_type,
                    "report_status": report["report_status"],
                    "version_number": version_number,
                    "title": report["title"],
                    "markdown_content": report["markdown"],
                    "html_content": report["html"],
                    "pdf_storage_path": pdf_path,
                    "source_claim_count": report["source_claim_count"],
                    "source_metric_count": report["source_metric_count"],
                    "valuation_snapshot_date": report["valuation_snapshot_date"],
                    "generator_type": report["generator_type"],
                    "generated_at": generated_at,
                }
            )
            .execute()
            .data
        )
        report_id = inserted[0]["id"]

        links = [
            {
                "research_report_id": report_id,
                "qualitative_claim_id": link["qualitative_claim_id"],
                "source_chunk_id": link["source_chunk_id"],
                "accession_number": link["accession_number"],
                "document_key": link["document_key"],
                "section_name": link["section_name"],
                "supporting_excerpt": link["supporting_excerpt"],
            }
            for link in report["evidence_links"]
        ]
        if links:
            supabase.table("report_evidence_links").insert(links).execute()

        supabase.table("report_generation_runs").update(
            {
                "run_status": "completed",
                "report_id": report_id,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", run_id).execute()

        return {
            "report_id": report_id,
            "ticker": ticker,
            "accession_number": report["accession_number"],
            "report_type": report_type,
            "report_status": report["report_status"],
            "version_number": version_number,
            "title": report["title"],
            "md_storage_path": md_path,
            "html_storage_path": html_path,
            "pdf_storage_path": pdf_path,
            "source_claim_count": report["source_claim_count"],
            "source_metric_count": report["source_metric_count"],
            "evidence_link_count": len(links),
            "valuation_snapshot_date": report["valuation_snapshot_date"],
            "run_id": run_id,
        }

    except Exception as exc:
        # Record the failure on the audit row (truncated) and re-raise; no
        # partial report row is created because inserts happen after success.
        supabase.table("report_generation_runs").update(
            {
                "run_status": "failed",
                "error_message": str(exc)[:500],
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", run_id).execute()
        raise
