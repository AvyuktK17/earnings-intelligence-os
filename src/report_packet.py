"""Deterministic equity-research *report packet* exporter.

A report packet is a self-contained, human-readable bundle of the trusted and
deterministic facts for one company filing. It is the **only** input the
``/semiconductor-equity-research-report`` Claude Code skill is allowed to draft
a narrative from — so everything in it must be sourced from already-trusted,
already-deterministic data:

* the company profile (``companies``);
* the selected filing's metadata (``filings``);
* trusted, promoted, grounded claims (``qualitative_claims``) with their source
  references, chunk ids, and supporting excerpts;
* reported operating fundamentals (``financial_metrics``) — latest snapshot and
  historical series;
* the deterministic peer-comparison table;
* the latest manually reviewed valuation snapshot (``valuation_snapshots``);
* metadata for any existing deterministic research report.

No AI is called, no rows are written, and no secrets are emitted. Output is
deterministic: the same inputs always produce byte-identical Markdown and JSON
(stable ordering, sorted JSON keys). Missing values are labelled honestly
rather than guessed.

The packet reuses the same trusted-source accessors as the deterministic report
engine (``src.research_report``) so the two never disagree about what counts as
a trusted claim or an operating metric.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.database import get_supabase_client
from src.quantitative import (
    build_metric_series,
    compute_multiples,
    latest_metric_values,
    sorted_periods,
)
from src.research_report import (
    _accession_from_reference,
    _latest_valuation,
    _metric_rows,
    _peer_context,
    _select_accession,
    _trusted_claims,
)

# Generator identity recorded in the packet so a reader always knows it was
# assembled deterministically (never by an LLM).
GENERATOR = "deterministic-report-packet"

VALUATION_DISCLAIMER = (
    "Valuation figures are a manually reviewed point-in-time snapshot, not a "
    "live market feed."
)

# Honest placeholder for any absent value, used identically in Markdown and as
# a human-readable hint alongside JSON nulls.
_MISSING = "Not available"

# Latest-quarter snapshot fields, in a fixed display order.
_SNAPSHOT_METRICS = [
    ("Revenue", "usd"),
    ("YoY Revenue Growth", "pct"),
    ("Gross Profit", "usd"),
    ("Gross Margin", "pct"),
    ("Operating Income", "usd"),
    ("Operating Margin", "pct"),
    ("Net Income", "usd"),
    ("Diluted EPS", "price"),
    ("R&D Expense", "usd"),
    ("R&D as % of Revenue", "pct"),
]

# Balance-sheet / cash-flow fields, in a fixed display order.
_BALANCE_SHEET_METRICS = [
    ("Cash and Cash Equivalents", "usd"),
    ("Total Debt", "usd"),
    ("Net Cash (Debt)", "usd"),
    ("Operating Cash Flow", "usd"),
    ("Free Cash Flow", "usd"),
    ("Capital Expenditure", "usd"),
    ("TTM Free Cash Flow", "usd"),
]

# Metrics shown as a historical trend table (last N periods), fixed order.
_TREND_METRICS = ["Revenue", "Gross Margin", "Operating Margin", "Free-Cash-Flow Margin"]
_TREND_PERIODS = 8


# --------------------------------------------------------------------------- #
# Display formatting (Markdown only; JSON always carries the raw value)
# --------------------------------------------------------------------------- #


def _usd(value: Any) -> str:
    if value is None:
        return _MISSING
    value = float(value)
    sign = "-" if value < 0 else ""
    a = abs(value)
    if a >= 1e12:
        return f"{sign}${a / 1e12:.2f}T"
    if a >= 1e9:
        return f"{sign}${a / 1e9:.2f}B"
    if a >= 1e6:
        return f"{sign}${a / 1e6:.1f}M"
    return f"{sign}${a:,.0f}"


def _pct(value: Any) -> str:
    if value is None:
        return _MISSING
    return f"{float(value) * 100:.1f}%"


def _mult(value: Any) -> str:
    if value is None:
        return _MISSING
    return f"{float(value):.1f}x"


def _price(value: Any) -> str:
    if value is None:
        return _MISSING
    return f"${float(value):.2f}"


_FORMATTERS = {"usd": _usd, "pct": _pct, "mult": _mult, "price": _price}


def _fmt(value: Any, kind: str) -> str:
    return _FORMATTERS[kind](value)


def _or_missing(value: Any) -> str:
    """Markdown display for a plain scalar, honestly labelling absence."""
    if value is None or value == "":
        return _MISSING
    return str(value)


def _safe_accession(accession: str) -> str:
    """Filesystem-safe form of an accession number for output filenames."""
    return re.sub(r"[^0-9A-Za-z]+", "_", accession).strip("_")


# --------------------------------------------------------------------------- #
# Packet assembly (pure data; no formatting)
# --------------------------------------------------------------------------- #


def _build_packet_data(
    supabase, ticker: str, accession_number: str | None
) -> dict:
    """Gather every trusted/deterministic fact for the packet, deterministically."""
    company_rows = (
        supabase.table("companies")
        .select("ticker, company_name, cik, business_model")
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
        .select("accession_number, form, filing_date, report_date, sec_url")
        .eq("accession_number", accession_number)
        .execute()
        .data
    )
    if not filing_rows:
        raise ValueError(
            f"No filing found with accession_number={accession_number!r}."
        )
    filing = filing_rows[0]

    # Trusted claims scoped to the anchor filing, ordered by claim id (stable).
    claims = [
        c
        for c in all_claims
        if _accession_from_reference(c.get("source_reference")) == accession_number
    ]

    metric_rows = _metric_rows(supabase, ticker)
    latest = latest_metric_values(metric_rows)
    series = build_metric_series(metric_rows)
    periods = [p["period"] for p in sorted_periods(metric_rows)]
    snapshot = _latest_valuation(supabase, ticker)
    peers = _peer_context(supabase)

    multiples = None
    if snapshot:
        multiples = compute_multiples(
            market_cap=snapshot.get("market_cap"),
            enterprise_value=snapshot.get("enterprise_value"),
            ttm_revenue=latest.get("TTM Revenue"),
            ttm_operating_income=latest.get("TTM Operating Income"),
            ttm_free_cash_flow=latest.get("TTM Free Cash Flow"),
        )

    # Existing deterministic research report metadata (if one has been generated).
    report_rows = (
        supabase.table("research_reports")
        .select(
            "version_number, report_status, generator_type, generated_at, "
            "source_claim_count, source_metric_count, valuation_snapshot_date, "
            "pdf_storage_path"
        )
        .eq("ticker", ticker)
        .eq("report_type", "earnings_update")
        .order("version_number", desc=True)
        .limit(1)
        .execute()
        .data
    )
    existing_report = report_rows[0] if report_rows else None

    # Evidence links derived from the trusted claims (deterministic, ordered).
    evidence_links = [
        {
            "qualitative_claim_id": c.get("proposed_claim_id"),
            "source_chunk_id": c.get("source_chunk_id"),
            "accession_number": _accession_from_reference(c.get("source_reference")),
            "document_key": c.get("document_key"),
            "source_reference": c.get("source_reference"),
            "supporting_excerpt": c.get("supporting_excerpt"),
        }
        for c in claims
    ]

    return {
        "company": company,
        "ticker": ticker,
        "accession_number": accession_number,
        "filing": filing,
        "claims": claims,
        "evidence_links": evidence_links,
        "latest": latest,
        "series": series,
        "periods": periods,
        "snapshot": snapshot,
        "multiples": multiples,
        "peers": peers,
        "existing_report": existing_report,
    }


# --------------------------------------------------------------------------- #
# Renderers
# --------------------------------------------------------------------------- #


def _render_json(data: dict, generated_at: str) -> str:
    """Render the packet as deterministic, sorted-key JSON."""
    company = data["company"]
    filing = data["filing"]
    snapshot = data["snapshot"]
    latest = data["latest"]

    payload = {
        "generator": GENERATOR,
        "generated_at": generated_at,
        "ticker": data["ticker"],
        "accession_number": data["accession_number"],
        "company": {
            "ticker": company.get("ticker"),
            "company_name": company.get("company_name"),
            "cik": company.get("cik"),
            "business_model": company.get("business_model"),
        },
        "filing": {
            "accession_number": filing.get("accession_number"),
            "form": filing.get("form"),
            "filing_date": filing.get("filing_date"),
            "report_date": filing.get("report_date"),
            "sec_url": filing.get("sec_url"),
        },
        "trusted_claims": [
            {
                "qualitative_claim_id": c.get("proposed_claim_id"),
                "theme": c.get("theme"),
                "claim": c.get("claim"),
                "factual_or_interpretive": c.get("factual_or_interpretive"),
                "confidence": c.get("confidence"),
                "document_key": c.get("document_key"),
                "source_reference": c.get("source_reference"),
                "source_chunk_id": c.get("source_chunk_id"),
                "supporting_excerpt": c.get("supporting_excerpt"),
            }
            for c in data["claims"]
        ],
        "evidence_links": data["evidence_links"],
        "financial_metrics": {
            "latest_quarter": latest,
            "periods": data["periods"],
            "series": data["series"],
        },
        "peer_comparison": data["peers"],
        "valuation_snapshot": {
            "snapshot": snapshot,
            "snapshot_date": snapshot.get("share_price_date") if snapshot else None,
            "multiples": data["multiples"],
            "is_live": False,
            "disclaimer": VALUATION_DISCLAIMER,
        },
        "existing_deterministic_report": data["existing_report"],
        "counts": {
            "trusted_claim_count": len(data["claims"]),
            "metric_count": len(data["series"]),
            "evidence_link_count": len(data["evidence_links"]),
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


def _render_markdown(data: dict, generated_at: str) -> str:
    """Render a stable, labelled Markdown packet for the analyst/skill."""
    company = data["company"]
    filing = data["filing"]
    ticker = data["ticker"]
    latest = data["latest"]
    series = data["series"]
    snapshot = data["snapshot"]
    multiples = data["multiples"]
    snapshot_date = snapshot.get("share_price_date") if snapshot else None

    out: list[str] = []
    out.append(f"# Report Packet — {company.get('company_name')} ({ticker})")
    out.append("")
    out.append(
        "> Deterministic report packet assembled from trusted, human-reviewed "
        "claims and audited deterministic data only. No AI was used to build "
        "this packet, and no forecasts, ratings, price targets, DCF values, or "
        "consensus estimates are present."
    )
    out.append("")
    out.append(f"- **Generator:** {GENERATOR}")
    out.append(f"- **Generated at (UTC):** {generated_at}")
    out.append(f"- **Ticker:** {ticker}")
    out.append(f"- **CIK:** {_or_missing(company.get('cik'))}")
    out.append(f"- **Business model:** {_or_missing(company.get('business_model'))}")
    out.append("")

    # --- Selected filing ----------------------------------------------------
    out.append("## Selected Filing")
    out.append("")
    out.append(f"- **Accession number:** {_or_missing(filing.get('accession_number'))}")
    out.append(f"- **Form:** {_or_missing(filing.get('form'))}")
    out.append(f"- **Filing date:** {_or_missing(filing.get('filing_date'))}")
    out.append(f"- **Report date:** {_or_missing(filing.get('report_date'))}")
    out.append(f"- **SEC URL:** {_or_missing(filing.get('sec_url'))}")
    out.append("")

    # --- Reported financial snapshot ---------------------------------------
    out.append("## Reported Financial Snapshot (Latest Quarter)")
    out.append("")
    if latest:
        out.append("| Metric | Latest quarter |")
        out.append("| --- | --- |")
        for name, kind in _SNAPSHOT_METRICS:
            out.append(f"| {name} | {_fmt(latest.get(name), kind)} |")
    else:
        out.append(_MISSING + ": no operating metrics are on file for this company.")
    out.append("")

    # --- Historical operating trends ---------------------------------------
    out.append(f"## Historical Operating Trends (last {_TREND_PERIODS} periods)")
    out.append("")
    period_labels = data["periods"][-_TREND_PERIODS:]
    if period_labels:
        out.append("| Metric | " + " | ".join(period_labels) + " |")
        out.append("| --- " * (len(period_labels) + 1) + "|")
        for name in _TREND_METRICS:
            by_period = {pt["period"]: pt["value"] for pt in series.get(name, [])}
            kind = "pct" if "Margin" in name else "usd"
            cells = [_fmt(by_period.get(p), kind) for p in period_labels]
            out.append(f"| {name} | " + " | ".join(cells) + " |")
    else:
        out.append(_MISSING + ": no historical operating metrics are on file.")
    out.append("")

    # --- Balance sheet and cash flow ---------------------------------------
    out.append("## Balance Sheet and Free Cash Flow")
    out.append("")
    if latest:
        out.append("| Item | Latest quarter |")
        out.append("| --- | --- |")
        for name, kind in _BALANCE_SHEET_METRICS:
            out.append(f"| {name} | {_fmt(latest.get(name), kind)} |")
    else:
        out.append(_MISSING + ": no balance-sheet or cash-flow metrics are on file.")
    out.append("")

    # --- Peer comparison ----------------------------------------------------
    out.append("## Peer Comparison (latest period)")
    out.append("")
    peers = data["peers"]
    if peers:
        out.append(
            "| Ticker | Revenue | YoY | Gross | Operating | EV/TTM Rev | FCF yield |"
        )
        out.append("| --- | --- | --- | --- | --- | --- | --- |")
        for p in peers:
            mark = f"{p['ticker']} (subject)" if p["ticker"] == ticker else p["ticker"]
            out.append(
                f"| {mark} | {_usd(p.get('revenue'))} | {_pct(p.get('yoy'))} | "
                f"{_pct(p.get('gross_margin'))} | {_pct(p.get('operating_margin'))} | "
                f"{_mult(p.get('ev_to_ttm_revenue'))} | "
                f"{_pct(p.get('free_cash_flow_yield'))} |"
            )
        out.append("")
        out.append(
            "EV/TTM Rev and FCF yield use the dated valuation snapshot. "
            f"{VALUATION_DISCLAIMER} Debt measures differ across issuers, so "
            "leverage-sensitive multiples are indicative rather than strictly "
            "like-for-like."
        )
    else:
        out.append(_MISSING + ": no peer rows are on file.")
    out.append("")

    # --- Valuation snapshot -------------------------------------------------
    out.append("## Valuation Snapshot")
    out.append("")
    if snapshot:
        out.append(f"- **Snapshot date:** {_or_missing(snapshot_date)}")
        out.append(f"- **Share price:** {_price(snapshot.get('share_price'))}")
        out.append(f"- **Market capitalization:** {_usd(snapshot.get('market_cap'))}")
        out.append(f"- **Enterprise value:** {_usd(snapshot.get('enterprise_value'))}")
        out.append(f"- **EV / TTM revenue:** {_mult(multiples['ev_to_ttm_revenue'])}")
        out.append(
            "- **EV / TTM operating income:** "
            f"{_mult(multiples['ev_to_ttm_operating_income'])}"
        )
        out.append(f"- **Price / TTM FCF:** {_mult(multiples['price_to_ttm_fcf'])}")
        out.append(f"- **FCF yield:** {_pct(multiples['free_cash_flow_yield'])}")
        out.append(f"- **Debt measure:** {_or_missing(snapshot.get('debt_measure'))}")
        out.append("")
        out.append(
            f"{VALUATION_DISCLAIMER} Multiples are computed deterministically "
            "from the stored snapshot and reported TTM fundamentals. No target "
            "price, rating, or DCF is implied."
        )
        if snapshot.get("notes"):
            out.append("")
            out.append(f"Snapshot note: {snapshot['notes']}")
    else:
        out.append(
            _MISSING + ": no manually reviewed valuation snapshot is on file for "
            "this company."
        )
    out.append("")

    # --- Trusted claims -----------------------------------------------------
    out.append("## Trusted Evidence-Linked Claims")
    out.append("")
    claims = data["claims"]
    if claims:
        for i, c in enumerate(claims, 1):
            out.append(f"### {i}. {_or_missing(c.get('theme'))}")
            out.append("")
            out.append(f"- **Claim:** {_or_missing(c.get('claim'))}")
            out.append(
                "- **Type:** "
                f"{_or_missing(c.get('factual_or_interpretive'))} | confidence "
                f"{_or_missing(c.get('confidence'))}"
            )
            out.append(
                f"- **Source reference:** {_or_missing(c.get('source_reference'))}"
            )
            out.append(f"- **Source chunk id:** {_or_missing(c.get('source_chunk_id'))}")
            out.append(f"- **Document key:** {_or_missing(c.get('document_key'))}")
            out.append("- **Supporting excerpt:**")
            out.append("")
            excerpt = c.get("supporting_excerpt")
            out.append(f"  > {excerpt}" if excerpt else f"  > {_MISSING}")
            out.append("")
    else:
        out.append(
            _MISSING + ": no trusted, human-reviewed claims are linked to this "
            "filing yet. Extract, review, and promote claims to populate this "
            "section."
        )
        out.append("")

    # --- Evidence appendix --------------------------------------------------
    out.append("## Evidence Appendix")
    out.append("")
    links = data["evidence_links"]
    if links:
        out.append("| Claim id | Accession | Document key | Chunk id |")
        out.append("| --- | --- | --- | --- |")
        for link in links:
            out.append(
                f"| {_or_missing(link['qualitative_claim_id'])} | "
                f"{_or_missing(link['accession_number'])} | "
                f"{_or_missing(link['document_key'])} | "
                f"{_or_missing(link['source_chunk_id'])} |"
            )
    else:
        out.append(_MISSING + ": no evidence links (no trusted claims for this filing).")
    out.append("")

    # --- Existing deterministic report -------------------------------------
    out.append("## Existing Deterministic Research Report")
    out.append("")
    existing = data["existing_report"]
    if existing:
        out.append(f"- **Latest version:** v{_or_missing(existing.get('version_number'))}")
        out.append(f"- **Report status:** {_or_missing(existing.get('report_status'))}")
        out.append(f"- **Generator type:** {_or_missing(existing.get('generator_type'))}")
        out.append(f"- **Generated at:** {_or_missing(existing.get('generated_at'))}")
        out.append(
            f"- **Source claim count:** {_or_missing(existing.get('source_claim_count'))}"
        )
        out.append(
            f"- **Source metric count:** {_or_missing(existing.get('source_metric_count'))}"
        )
        out.append(
            "- **Valuation snapshot date:** "
            f"{_or_missing(existing.get('valuation_snapshot_date'))}"
        )
    else:
        out.append(
            _MISSING + ": no deterministic research report has been generated for "
            "this company yet."
        )
    out.append("")

    # --- Methodology and limitations ---------------------------------------
    out.append("## Methodology and Limitations")
    out.append("")
    out.append(
        "- This packet is assembled deterministically from stored values; no AI "
        "narrative is present and no figure is estimated."
    )
    out.append(
        "- Only trusted, human-reviewed, evidence-linked claims are included; "
        "pending and rejected drafts are excluded."
    )
    out.append(f"- {VALUATION_DISCLAIMER}")
    out.append(
        "- No forward estimates, forecasts, DCF valuations, price targets, "
        "consensus estimates, or investment ratings are produced."
    )
    out.append(
        "- Peer multiples use dated valuation snapshots and differing debt "
        "measures, so they are indicative rather than strictly like-for-like."
    )
    out.append(f"- Missing inputs are labelled '{_MISSING}' rather than estimated.")
    out.append("")

    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def export_report_packet(
    ticker: str,
    accession_number: str | None = None,
    output_dir: str = "output/report_packets",
) -> dict:
    """Export a deterministic report packet (Markdown + JSON) for one filing.

    Args:
        ticker: Company ticker (case-insensitive).
        accession_number: Specific filing to anchor on. When ``None``, the most
            recent filing that has trusted claims is selected (falling back to
            the most recent filing overall) — matching the deterministic report
            engine's selection.
        output_dir: Directory the two packet files are written to (created if
            needed; gitignored).

    Returns:
        A dict with ``ticker``, ``accession_number``, ``markdown_path``,
        ``json_path``, ``trusted_claim_count``, ``metric_count``,
        ``evidence_link_count``, and ``valuation_snapshot_date``.

    Raises:
        ValueError: If the company or filing cannot be found.
    """
    supabase = get_supabase_client()
    ticker = ticker.upper()

    data = _build_packet_data(supabase, ticker, accession_number)
    resolved_accession = data["accession_number"]
    generated_at = datetime.now(timezone.utc).isoformat()

    markdown = _render_markdown(data, generated_at)
    json_text = _render_json(data, generated_at)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f"{ticker.lower()}_{_safe_accession(resolved_accession)}_packet"
    md_path = out_dir / f"{base}.md"
    json_path = out_dir / f"{base}.json"
    md_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(json_text, encoding="utf-8")

    snapshot = data["snapshot"]
    return {
        "ticker": ticker,
        "accession_number": resolved_accession,
        "markdown_path": str(md_path),
        "json_path": str(json_path),
        "trusted_claim_count": len(data["claims"]),
        "metric_count": len(data["series"]),
        "evidence_link_count": len(data["evidence_links"]),
        "valuation_snapshot_date": (
            snapshot.get("share_price_date") if snapshot else None
        ),
    }
