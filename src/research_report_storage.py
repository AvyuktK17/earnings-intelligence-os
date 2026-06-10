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
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

from src.database import get_supabase_client
from src.research_report import generate_research_report
from src.storage import upload_file

_LOCAL_DIR = "output/reports"

# Neutral institutional palette (no copied branding). Dark slate ink and muted
# rules keep the note legible and restrained, not consumer-flashy.
_BRAND = "Earnings Intelligence OS Research"
_INK = (26, 31, 39)
_SLATE = (40, 52, 74)
_GRAY = (110, 120, 135)
_RULE = (188, 195, 206)
_HEADER_FILL = (40, 52, 74)
_ZEBRA = (244, 246, 249)
_DISCLAIMER = (
    "Deterministic research note - no forecasts, ratings, price targets, or DCF. "
    "Valuation figures are a dated, manually reviewed snapshot, not a live feed."
)

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


class _ResearchPDF(FPDF):
    """A4 research note with a branded running header and a numbered, disclaimer
    footer. Pure-Python (core fonts only) so it deploys on Render unchanged.
    """

    def __init__(self, subtitle: str) -> None:
        super().__init__(format="A4")
        self._subtitle = subtitle
        self.set_margins(left=16, top=14, right=16)
        self.set_auto_page_break(auto=True, margin=16)

    def header(self) -> None:
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*_SLATE)
        self.cell(0, 5, _latin1_safe(_BRAND), align="L")
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*_GRAY)
        self.cell(0, 5, _latin1_safe(self._subtitle), align="R",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*_RULE)
        self.set_line_width(0.4)
        y = self.get_y() + 1.0
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(5)

    def footer(self) -> None:
        self.set_y(-13)
        self.set_draw_color(*_RULE)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1.2)
        self.set_font("Helvetica", "", 6.8)
        self.set_text_color(*_GRAY)
        self.cell(0, 4, _latin1_safe(_DISCLAIMER), align="L")
        self.cell(0, 4, f"Page {self.page_no()} / {{nb}}", align="R")


def _render_table(pdf: "_ResearchPDF", headers: list, rows: list) -> None:
    """Render a compact financial table with a shaded header and zebra rows.

    The first column is left-aligned (labels); the remaining columns are
    right-aligned (figures), which matches every table the report emits.
    """
    ncols = len(headers)
    aligns = ["LEFT"] + ["RIGHT"] * (ncols - 1)
    heading = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=_HEADER_FILL)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_INK)
    pdf.set_draw_color(*_RULE)
    with pdf.table(
        borders_layout="HORIZONTAL_LINES",
        headings_style=heading,
        cell_fill_color=_ZEBRA,
        cell_fill_mode="ROWS",
        text_align=tuple(aligns),
        line_height=4.6,
        first_row_as_headings=True,
        width=pdf.w - pdf.l_margin - pdf.r_margin,
    ) as table:
        head = table.row()
        for cell in headers:
            head.cell(_latin1_safe(str(cell)))
        for data_row in rows:
            row = table.row()
            for cell in data_row:
                row.cell(_latin1_safe(str(cell)))
    pdf.ln(2)


def _render_blocks(pdf: "_ResearchPDF", blocks: list) -> None:
    width = pdf.w - pdf.l_margin - pdf.r_margin
    for block in blocks:
        kind = block[0]
        if kind == "h1":
            pdf.set_font("Helvetica", "B", 16)
            pdf.set_text_color(*_SLATE)
            pdf.multi_cell(0, 7, _latin1_safe(block[1]),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(0.5)
        elif kind == "h2":
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 11.5)
            pdf.set_text_color(*_SLATE)
            pdf.multi_cell(0, 6, _latin1_safe(block[1]),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_draw_color(*_RULE)
            pdf.set_line_width(0.3)
            y = pdf.get_y() + 0.4
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(2.5)
        elif kind == "h3":
            pdf.ln(1)
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.set_text_color(*_INK)
            pdf.multi_cell(0, 5, _latin1_safe(block[1]),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        elif kind == "p":
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*_INK)
            pdf.multi_cell(0, 4.8, _latin1_safe(block[1]),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1.5)
        elif kind == "kv":
            pdf.set_text_color(*_INK)
            for key, value in block[1]:
                pdf.set_font("Helvetica", "B", 9)
                pdf.write(4.6, _latin1_safe(f"{key}: "))
                pdf.set_font("Helvetica", "", 9)
                pdf.write(4.6, _latin1_safe(str(value)))
                pdf.ln(4.8)
            pdf.ln(1.5)
        elif kind == "bullets":
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*_INK)
            for item in block[1]:
                x0 = pdf.l_margin
                pdf.set_x(x0)
                pdf.cell(4, 4.8, _latin1_safe("-"))
                pdf.set_x(x0 + 4)
                pdf.multi_cell(width - 4, 4.8, _latin1_safe(item),
                               new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1.5)
        elif kind == "quote":
            pdf.set_font("Helvetica", "I", 8.5)
            pdf.set_text_color(*_GRAY)
            y_start = pdf.get_y()
            pdf.set_x(pdf.l_margin + 4)
            pdf.multi_cell(width - 4, 4.4, _latin1_safe(block[1]),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_draw_color(*_RULE)
            pdf.set_line_width(0.8)
            pdf.line(pdf.l_margin + 1, y_start, pdf.l_margin + 1, pdf.get_y() - 1)
            pdf.ln(1.5)
        elif kind == "table":
            _render_table(pdf, block[1], block[2])
        elif kind == "hr":
            pdf.set_draw_color(*_RULE)
            pdf.set_line_width(0.3)
            y = pdf.get_y() + 1
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(3)


def render_report_pdf(report: dict, local_path: str) -> str:
    """Render the deterministic report's block model to an institutional PDF.

    Lays out the report natively from its intermediate blocks (rather than
    re-parsing HTML), giving a branded header, numbered footer, section
    hierarchy, and shaded financial tables. Returns the local path.
    """
    subtitle = (
        f"{report.get('ticker', '')} - {report.get('report_date', '')}"
    ).strip(" -")
    pdf = _ResearchPDF(subtitle=subtitle)
    pdf.set_title(_latin1_safe(report.get("title", _BRAND)))
    pdf.alias_nb_pages()
    pdf.add_page()
    _render_blocks(pdf, report.get("blocks", []))
    out = Path(local_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))
    return str(out)


def render_pdf(html: str, local_path: str) -> str:
    """Back-compat HTML renderer (no longer used by the storage path).

    Retained so callers passing raw report HTML still work; the institutional
    layout now comes from ``render_report_pdf`` using the block model.
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
        render_report_pdf(report, str(local_pdf))

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
