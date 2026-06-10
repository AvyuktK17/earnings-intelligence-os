"""Deterministic professional earnings-update research report.

Builds a structured, human-reviewed report from three trusted sources only:

* trusted promoted claims (``qualitative_claims`` rows that are grounded —
  ``proposed_claim_id`` and ``source_chunk_id`` both non-null);
* deterministic operating fundamentals (``financial_metrics``);
* the latest manually reviewed valuation snapshot (``valuation_snapshots``).

No AI is called. The report never invents target prices, ratings, DCF values,
or forward estimates. Valuation figures are always presented as a dated,
manually reviewed point-in-time snapshot — never as a live market feed.

The generator builds an intermediate list of content *blocks* and renders them
to both Markdown and a simple HTML subset (the HTML feeds the PDF exporter and
the ``html_content`` column), so the two representations never drift.
"""

from __future__ import annotations

import html as html_lib
from datetime import datetime, timezone
from typing import Any

from src.database import get_supabase_client
from src.quantitative import (
    build_metric_series,
    compute_multiples,
    latest_metric_values,
    operating_rows,
    sorted_periods,
)

VALUATION_DISCLAIMER = (
    "Valuation figures are a manually reviewed point-in-time snapshot, not a "
    "live market feed."
)

REPORT_STATUS = "human_reviewed_deterministic"
GENERATOR_TYPE = "deterministic"

# Deterministic keyword routing for the Catalysts / Risks sections. Routing
# only ever moves a human-reviewed claim into a section — it never invents
# content. Every claim also appears in Reviewed Evidence-Linked Takeaways.
_CATALYST_KEYWORDS = (
    "outlook",
    "guidance",
    "forecast",
    "collaboration",
    "partnership",
    "launch",
    "pipeline",
    "expansion",
    "demand",
    "growth",
    "new product",
    "design win",
    "ramp",
    "opportunity",
)
_RISK_KEYWORDS = (
    "risk",
    "headwind",
    "decline",
    "declined",
    "litigation",
    "lawsuit",
    "regulatory",
    "competition",
    "competitive",
    "supply",
    "shortage",
    "pressure",
    "weak",
    "uncertain",
    "macro",
    "tariff",
    "inventory",
)


# --------------------------------------------------------------------------- #
# Block rendering
# --------------------------------------------------------------------------- #


def _render_markdown(blocks: list[tuple]) -> str:
    out: list[str] = []
    for block in blocks:
        kind = block[0]
        if kind in ("h1", "h2", "h3"):
            hashes = {"h1": "#", "h2": "##", "h3": "###"}[kind]
            out.append(f"{hashes} {block[1]}")
            out.append("")
        elif kind == "p":
            out.append(block[1])
            out.append("")
        elif kind == "kv":
            for key, value in block[1]:
                out.append(f"**{key}:** {value}")
            out.append("")
        elif kind == "bullets":
            for item in block[1]:
                out.append(f"- {item}")
            out.append("")
        elif kind == "quote":
            out.append(f"> {block[1]}")
            out.append("")
        elif kind == "table":
            headers, rows = block[1], block[2]
            out.append("| " + " | ".join(headers) + " |")
            out.append("| " + " | ".join("---" for _ in headers) + " |")
            for row in rows:
                out.append("| " + " | ".join(str(c) for c in row) + " |")
            out.append("")
        elif kind == "hr":
            out.append("---")
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def _esc(text: Any) -> str:
    return html_lib.escape(str(text))


def _render_html(blocks: list[tuple], title: str) -> str:
    out: list[str] = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>{_esc(title)}</title>",
        "<style>",
        "body{font-family:Helvetica,Arial,sans-serif;color:#1b1f27;font-size:11px;}",
        "h1{font-size:20px;margin:0 0 4px;} h2{font-size:14px;border-bottom:1px solid "
        "#999;padding-bottom:2px;margin:16px 0 6px;} h3{font-size:12px;margin:10px 0 "
        "4px;}",
        "table{border-collapse:collapse;width:100%;margin:6px 0;} th,td{border:1px "
        "solid #bbb;padding:3px 5px;text-align:left;font-size:10px;} th{background:"
        "#f0f0f0;}",
        "blockquote{border-left:3px solid #ccc;margin:4px 0;padding:2px 8px;color:"
        "#444;}",
        "</style></head><body>",
    ]
    for block in blocks:
        kind = block[0]
        if kind in ("h1", "h2", "h3"):
            out.append(f"<{kind}>{_esc(block[1])}</{kind}>")
        elif kind == "p":
            out.append(f"<p>{_esc(block[1])}</p>")
        elif kind == "kv":
            out.append(
                "<p>"
                + "<br/>".join(
                    f"<b>{_esc(k)}:</b> {_esc(v)}" for k, v in block[1]
                )
                + "</p>"
            )
        elif kind == "bullets":
            out.append("<ul>" + "".join(f"<li>{_esc(i)}</li>" for i in block[1]) + "</ul>")
        elif kind == "quote":
            out.append(f"<blockquote>{_esc(block[1])}</blockquote>")
        elif kind == "table":
            headers, rows = block[1], block[2]
            head = "<tr>" + "".join(f"<th>{_esc(h)}</th>" for h in headers) + "</tr>"
            body = "".join(
                "<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in row) + "</tr>"
                for row in rows
            )
            out.append(f"<table><thead>{head}</thead><tbody>{body}</tbody></table>")
        elif kind == "hr":
            out.append("<hr/>")
    out.append("</body></html>")
    return "".join(out)


# --------------------------------------------------------------------------- #
# Deterministic formatting (self-contained; mirrors the frontend formatters)
# --------------------------------------------------------------------------- #

_DASH = "n/a"


def _usd(value: Any) -> str:
    if value is None:
        return _DASH
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
        return _DASH
    return f"{float(value) * 100:.1f}%"


def _mult(value: Any) -> str:
    if value is None:
        return _DASH
    return f"{float(value):.1f}x"


def _price(value: Any) -> str:
    if value is None:
        return _DASH
    return f"${float(value):.2f}"


# --------------------------------------------------------------------------- #
# Data access (trusted sources only)
# --------------------------------------------------------------------------- #


def _accession_from_reference(source_reference: str | None) -> str | None:
    """Parse the accession number from a trusted claim's source_reference.

    Format is ``"{accession} | {document_key} | chunk:{id}"``.
    """
    if not source_reference:
        return None
    head = source_reference.split("|", 1)[0].strip()
    return head or None


def _trusted_claims(supabase, ticker: str) -> list[dict]:
    """All trusted, grounded, promoted claims for a ticker."""
    return (
        supabase.table("qualitative_claims")
        .select("*")
        .eq("ticker", ticker)
        .not_.is_("proposed_claim_id", "null")
        .not_.is_("source_chunk_id", "null")
        .order("proposed_claim_id", desc=False)
        .execute()
        .data
    )


def _metric_rows(supabase, ticker: str) -> list[dict]:
    rows = (
        supabase.table("financial_metrics")
        .select("ticker, fiscal_year, fiscal_quarter, metric_name, value, unit")
        .eq("ticker", ticker)
        .execute()
        .data
    )
    return operating_rows(rows)


def _latest_valuation(supabase, ticker: str) -> dict | None:
    rows = (
        supabase.table("valuation_snapshots")
        .select("*")
        .eq("ticker", ticker)
        .order("share_price_date", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


def _peer_context(supabase) -> list[dict]:
    """Deterministic latest-period peer rows for the peer-comparison section."""
    companies = (
        supabase.table("companies")
        .select("ticker, company_name, business_model")
        .order("ticker")
        .execute()
        .data
    )
    rows = []
    for company in companies:
        latest = latest_metric_values(_metric_rows(supabase, company["ticker"]))
        snapshot = _latest_valuation(supabase, company["ticker"])
        market_cap = snapshot.get("market_cap") if snapshot else None
        ev = snapshot.get("enterprise_value") if snapshot else None
        multiples = compute_multiples(
            market_cap=market_cap,
            enterprise_value=ev,
            ttm_revenue=latest.get("TTM Revenue"),
            ttm_operating_income=latest.get("TTM Operating Income"),
            ttm_free_cash_flow=latest.get("TTM Free Cash Flow"),
        )
        rows.append(
            {
                "ticker": company["ticker"],
                "business_model": company["business_model"],
                "revenue": latest.get("Revenue"),
                "yoy": latest.get("YoY Revenue Growth"),
                "gross_margin": latest.get("Gross Margin"),
                "operating_margin": latest.get("Operating Margin"),
                "ev_to_ttm_revenue": multiples["ev_to_ttm_revenue"],
                "free_cash_flow_yield": multiples["free_cash_flow_yield"],
            }
        )
    return rows


def _route_section(claim: dict) -> str:
    """Deterministic catalyst/risk routing by keyword over reviewed text."""
    text = f"{claim.get('theme', '')} {claim.get('claim', '')}".lower()
    if any(kw in text for kw in _RISK_KEYWORDS):
        return "risks"
    if any(kw in text for kw in _CATALYST_KEYWORDS):
        return "catalysts"
    return "reviewed_takeaways"


# --------------------------------------------------------------------------- #
# Report generation
# --------------------------------------------------------------------------- #


def generate_research_report(
    ticker: str,
    accession_number: str | None = None,
    report_type: str = "earnings_update",
) -> dict:
    """Generate a deterministic earnings-update research report.

    Args:
        ticker: Company ticker (case-insensitive).
        accession_number: Specific filing to anchor the report on. When None,
            the most recent filing that has trusted claims is selected (falling
            back to the most recent filing overall).
        report_type: Report family; only ``"earnings_update"`` is implemented.

    Returns:
        A dict with the company/filing context, ``markdown``, ``html``,
        ``title``, ``valuation_snapshot_date``, ``source_claim_count``,
        ``source_metric_count``, and ``evidence_links`` (one per trusted claim
        used, ready for report_evidence_links).

    Raises:
        ValueError: If the company or filing cannot be found.
    """
    supabase = get_supabase_client()
    ticker = ticker.upper()

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

    # Resolve the anchor filing.
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

    # Trusted claims scoped to the anchor filing.
    claims = [
        c
        for c in all_claims
        if _accession_from_reference(c.get("source_reference")) == accession_number
    ]

    metric_rows = _metric_rows(supabase, ticker)
    latest = latest_metric_values(metric_rows)
    series = build_metric_series(metric_rows)
    periods = sorted_periods(metric_rows)
    snapshot = _latest_valuation(supabase, ticker)
    peers = _peer_context(supabase)

    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title = f"{company['company_name']} ({ticker}) — Earnings Update"
    snapshot_date = snapshot.get("share_price_date") if snapshot else None

    blocks, evidence_links = _build_blocks(
        company=company,
        ticker=ticker,
        filing=filing,
        report_date=report_date,
        claims=claims,
        latest=latest,
        series=series,
        periods=periods,
        snapshot=snapshot,
        peers=peers,
    )

    markdown = _render_markdown(blocks)
    html = _render_html(blocks, title)

    return {
        "ticker": ticker,
        "company_name": company["company_name"],
        "accession_number": accession_number,
        "report_type": report_type,
        "report_status": REPORT_STATUS,
        "generator_type": GENERATOR_TYPE,
        "title": title,
        "markdown": markdown,
        "html": html,
        "valuation_snapshot_date": snapshot_date,
        "source_claim_count": len(claims),
        "source_metric_count": len(series),
        "evidence_links": evidence_links,
        "filing": filing,
    }


def _select_accession(supabase, ticker: str, claims: list[dict]) -> str:
    """Pick the most recent filing that has trusted claims, else newest filing."""
    accessions = {
        a
        for a in (_accession_from_reference(c.get("source_reference")) for c in claims)
        if a
    }
    if accessions:
        dated = (
            supabase.table("filings")
            .select("accession_number, filing_date")
            .in_("accession_number", list(accessions))
            .order("filing_date", desc=True)
            .limit(1)
            .execute()
            .data
        )
        if dated:
            return dated[0]["accession_number"]
    latest_filing = (
        supabase.table("filings")
        .select("accession_number")
        .eq("ticker", ticker)
        .order("filing_date", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not latest_filing:
        raise ValueError(f"No filing found for ticker={ticker!r}.")
    return latest_filing[0]["accession_number"]


def _build_blocks(
    *,
    company: dict,
    ticker: str,
    filing: dict,
    report_date: str,
    claims: list[dict],
    latest: dict,
    series: dict,
    periods: list[dict],
    snapshot: dict | None,
    peers: list[dict],
) -> tuple[list[tuple], list[dict]]:
    """Assemble the report's content blocks and the evidence-link records."""
    blocks: list[tuple] = []
    snapshot_date = snapshot.get("share_price_date") if snapshot else None

    # --- Front matter --------------------------------------------------------
    blocks.append(("h1", "Earnings Intelligence OS Research"))
    blocks.append(("h2", f"{company['company_name']} ({ticker})"))
    blocks.append(("h3", "Earnings Update"))
    blocks.append(
        (
            "kv",
            [
                ("Report date", report_date),
                (
                    "Selected filing",
                    f"{filing.get('form', '')} {filing['accession_number']} "
                    f"(filed {filing.get('filing_date', 'n/a')})",
                ),
                ("Business model", company.get("business_model") or "n/a"),
                ("Report status", "Human-reviewed deterministic report"),
                (
                    "Valuation data",
                    f"Manually reviewed snapshot as of {snapshot_date or 'n/a'}, "
                    "not a live market feed",
                ),
            ],
        )
    )
    blocks.append(("hr",))

    # --- Executive Summary ---------------------------------------------------
    blocks.append(("h2", "Executive Summary"))
    summary = (
        f"For its most recent reported quarter, {company['company_name']} "
        f"posted revenue of {_usd(latest.get('Revenue'))} "
        f"({_pct(latest.get('YoY Revenue Growth'))} year over year), a gross "
        f"margin of {_pct(latest.get('Gross Margin'))} and an operating margin "
        f"of {_pct(latest.get('Operating Margin'))}, with diluted EPS of "
        f"{_price(latest.get('Diluted EPS'))}. This update is built only from "
        f"{len(claims)} human-reviewed, evidence-linked claim(s) tied to the "
        "selected filing and from deterministic SEC-sourced fundamentals. It "
        "contains no forecasts, price targets, ratings, or DCF analysis."
    )
    blocks.append(("p", summary))

    # --- Reported Financial Snapshot ----------------------------------------
    blocks.append(("h2", "Reported Financial Snapshot"))
    snap_metrics = [
        ("Revenue", _usd(latest.get("Revenue"))),
        ("YoY revenue growth", _pct(latest.get("YoY Revenue Growth"))),
        ("Gross profit", _usd(latest.get("Gross Profit"))),
        ("Gross margin", _pct(latest.get("Gross Margin"))),
        ("Operating income", _usd(latest.get("Operating Income"))),
        ("Operating margin", _pct(latest.get("Operating Margin"))),
        ("Net income", _usd(latest.get("Net Income"))),
        ("Diluted EPS", _price(latest.get("Diluted EPS"))),
        ("R&D expense", _usd(latest.get("R&D Expense"))),
        ("R&D % of revenue", _pct(latest.get("R&D as % of Revenue"))),
    ]
    blocks.append(("table", ["Metric", "Latest quarter"], snap_metrics))

    # --- Historical Operating Trends ----------------------------------------
    blocks.append(("h2", "Historical Operating Trends"))
    trend_metrics = ["Revenue", "Gross Margin", "Operating Margin", "Free-Cash-Flow Margin"]
    period_labels = [p["period"] for p in periods][-6:]
    if period_labels:
        rows = []
        for name in trend_metrics:
            by_period = {pt["period"]: pt["value"] for pt in series.get(name, [])}
            fmt = _pct if ("Margin" in name) else _usd
            rows.append([name] + [fmt(by_period.get(p)) for p in period_labels])
        blocks.append(("table", ["Metric"] + period_labels, rows))
    else:
        blocks.append(("p", "No historical operating metrics are available."))

    # --- Peer Comparison -----------------------------------------------------
    blocks.append(("h2", "Peer Comparison"))
    peer_rows = [
        [
            f"{p['ticker']}*" if p["ticker"] == ticker else p["ticker"],
            _usd(p["revenue"]),
            _pct(p["yoy"]),
            _pct(p["gross_margin"]),
            _pct(p["operating_margin"]),
            _mult(p["ev_to_ttm_revenue"]),
            _pct(p["free_cash_flow_yield"]),
        ]
        for p in peers
    ]
    blocks.append(
        (
            "table",
            ["Ticker", "Revenue", "YoY", "Gross", "Op.", "EV/TTM Rev", "FCF yld"],
            peer_rows,
        )
    )
    blocks.append(
        (
            "p",
            f"* Subject company. EV/TTM Rev and FCF yield use the dated "
            f"valuation snapshot. {VALUATION_DISCLAIMER} Debt measures differ "
            "across issuers, so leverage-sensitive multiples are not strictly "
            "like-for-like.",
        )
    )

    # --- Balance Sheet and Cash Flow ----------------------------------------
    blocks.append(("h2", "Balance Sheet and Cash Flow"))
    bs_rows = [
        ("Cash & equivalents", _usd(latest.get("Cash and Cash Equivalents"))),
        ("Total debt", _usd(latest.get("Total Debt"))),
        ("Net cash (debt)", _usd(latest.get("Net Cash (Debt)"))),
        ("Operating cash flow", _usd(latest.get("Operating Cash Flow"))),
        ("Free cash flow", _usd(latest.get("Free Cash Flow"))),
        ("Capital expenditure", _usd(latest.get("Capital Expenditure"))),
        ("TTM free cash flow", _usd(latest.get("TTM Free Cash Flow"))),
    ]
    blocks.append(("table", ["Item", "Latest quarter"], bs_rows))

    # --- Valuation Snapshot --------------------------------------------------
    blocks.append(("h2", "Valuation Snapshot"))
    if snapshot:
        multiples = compute_multiples(
            market_cap=snapshot.get("market_cap"),
            enterprise_value=snapshot.get("enterprise_value"),
            ttm_revenue=latest.get("TTM Revenue"),
            ttm_operating_income=latest.get("TTM Operating Income"),
            ttm_free_cash_flow=latest.get("TTM Free Cash Flow"),
        )
        val_rows = [
            ("Snapshot date", snapshot_date or "n/a"),
            ("Share price", _price(snapshot.get("share_price"))),
            ("Market capitalization", _usd(snapshot.get("market_cap"))),
            ("Enterprise value", _usd(snapshot.get("enterprise_value"))),
            ("EV / TTM revenue", _mult(multiples["ev_to_ttm_revenue"])),
            ("EV / TTM operating income", _mult(multiples["ev_to_ttm_operating_income"])),
            ("Price / TTM FCF", _mult(multiples["price_to_ttm_fcf"])),
            ("FCF yield", _pct(multiples["free_cash_flow_yield"])),
            ("Debt measure", snapshot.get("debt_measure") or "n/a"),
        ]
        blocks.append(("table", ["Field", "Value"], val_rows))
        blocks.append(
            (
                "p",
                f"{VALUATION_DISCLAIMER} Multiples are computed deterministically "
                "from the stored snapshot and reported TTM fundamentals. No "
                "target price, rating, or DCF is implied.",
            )
        )
        if snapshot.get("notes"):
            blocks.append(("p", f"Snapshot note: {snapshot['notes']}"))
    else:
        blocks.append(
            ("p", "No manually reviewed valuation snapshot is available for this company.")
        )

    # --- Reviewed Evidence-Linked Takeaways, Catalysts, Risks ---------------
    evidence_links: list[dict] = []
    routed = {"reviewed_takeaways": [], "catalysts": [], "risks": []}
    for claim in claims:
        routed[_route_section(claim)].append(claim)

    blocks.append(("h2", "Reviewed Evidence-Linked Takeaways"))
    if claims:
        for i, claim in enumerate(claims, 1):
            blocks.append(("h3", f"{i}. {claim.get('theme', 'Untitled')}"))
            blocks.append(
                (
                    "kv",
                    [
                        ("Claim", claim.get("claim", "")),
                        (
                            "Type",
                            f"{claim.get('factual_or_interpretive', 'n/a')} | "
                            f"confidence {claim.get('confidence', 'n/a')}",
                        ),
                    ],
                )
            )
            blocks.append(("quote", claim.get("supporting_excerpt", "")))
            blocks.append(
                (
                    "p",
                    f"Source: {claim.get('source_reference', 'n/a')} "
                    f"(chunk {claim.get('source_chunk_id', 'n/a')})",
                )
            )
            evidence_links.append(
                {
                    "qualitative_claim_id": claim.get("proposed_claim_id"),
                    "source_chunk_id": claim.get("source_chunk_id"),
                    "accession_number": _accession_from_reference(
                        claim.get("source_reference")
                    ),
                    "document_key": claim.get("document_key"),
                    "section_name": _route_section(claim),
                    "supporting_excerpt": claim.get("supporting_excerpt"),
                }
            )
    else:
        blocks.append(
            (
                "p",
                "No trusted, human-reviewed claims are linked to this filing yet. "
                "Extract, review, and promote claims to populate this section.",
            )
        )

    def _claim_bullets(items: list[dict]) -> list[str]:
        return [
            f"{c.get('theme', 'Untitled')}: {c.get('claim', '')}" for c in items
        ]

    blocks.append(("h2", "Catalysts"))
    blocks.append(
        (
            "p",
            "Catalysts below are drawn verbatim from human-reviewed claims; they "
            "are not forecasts, price targets, or independent projections.",
        )
    )
    if routed["catalysts"]:
        blocks.append(("bullets", _claim_bullets(routed["catalysts"])))
    else:
        blocks.append(
            ("p", "No reviewed claims were classified as catalysts for this filing.")
        )

    blocks.append(("h2", "Risks and Watch Items"))
    if routed["risks"]:
        blocks.append(("bullets", _claim_bullets(routed["risks"])))
    else:
        blocks.append(
            (
                "p",
                "No reviewed claims were classified as risks or watch items for "
                "this filing.",
            )
        )

    # --- Source Appendix -----------------------------------------------------
    blocks.append(("h2", "Source Appendix"))
    blocks.append(
        (
            "kv",
            [
                ("Filing", f"{filing.get('form', '')} {filing['accession_number']}"),
                ("Filing date", filing.get("filing_date", "n/a")),
                ("SEC URL", filing.get("sec_url") or "n/a"),
            ],
        )
    )
    if evidence_links:
        appendix_rows = [
            [
                link["qualitative_claim_id"],
                link["accession_number"] or "n/a",
                link["document_key"] or "n/a",
                link["source_chunk_id"],
                link["section_name"],
            ]
            for link in evidence_links
        ]
        blocks.append(
            (
                "table",
                ["Claim id", "Accession", "Document key", "Chunk id", "Section"],
                appendix_rows,
            )
        )
    blocks.append(
        (
            "p",
            "Fundamentals are sourced from audited SEC filings stored in "
            "financial_metrics; valuation figures from the manually reviewed "
            "valuation_snapshots table.",
        )
    )

    # --- Methodology and Limitations ----------------------------------------
    blocks.append(("h2", "Methodology and Limitations"))
    blocks.append(
        (
            "bullets",
            [
                "Deterministic report: every figure is computed arithmetically "
                "from stored values; no AI narrative is generated.",
                "Only trusted, human-reviewed, evidence-linked claims are used; "
                "pending and rejected drafts are excluded.",
                f"{VALUATION_DISCLAIMER}",
                "No forward estimates, forecasts, DCF valuations, price targets, "
                "or investment ratings are produced.",
                "Peer multiples use dated valuation snapshots and differing debt "
                "measures, so they are indicative rather than strictly "
                "like-for-like.",
                "Missing inputs are labelled rather than estimated.",
            ],
        )
    )

    return blocks, evidence_links
