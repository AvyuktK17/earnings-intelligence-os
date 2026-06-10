"""Research API for the Earnings Intelligence OS dashboard.

Read endpoints serve the filing feed, filing detail, stored briefs, the
analyst review queue, and the extraction-ready exhibit queue. Write endpoints drive the analyst workflow: approve,
edit, or reject proposed claims, promote reviewed claims into trusted
qualitative_claims, and generate versioned earnings briefs. Write endpoints
require the X-Admin-Token header matching ADMIN_API_TOKEN; read endpoints
are public. No AI calls. Run locally with:

    uvicorn app.main:app --reload
"""

import os
import secrets
from functools import lru_cache

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.brief_storage import generate_and_store_earnings_brief
from src.claim_promotion import promote_reviewed_claims
from src.claim_review import approve_claim, approve_claim_with_edits, reject_claim
from src.database import get_supabase_client
from src.quantitative import (
    PEER_METRIC_FIELDS,
    build_metric_series,
    compute_multiples,
    latest_metric_values,
    operating_rows,
    period_label,
    period_sort_key,
    sorted_periods,
)
from src.ready_filing_extraction import (
    ClaimExtractionError,
    ClaimExtractionQuotaError,
    extract_claims_for_ready_filing,
)

load_dotenv()

app = FastAPI(title="Earnings Intelligence OS API")

# Comma-separated list of allowed browser origins for local frontend
# development. Defaults to the local Next.js dev server.
_allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FILING_COLUMNS = (
    "id, ticker, accession_number, form, filing_date, report_date, "
    "processing_status, sec_url, html_storage_path, text_storage_path, "
    "downloaded_at, parsed_at, chunked_at, processing_error"
)

DOCUMENT_COLUMNS = (
    "id, document_type, filename, sec_url, html_storage_path, text_storage_path"
)

BRIEF_COLUMNS = (
    "id, ticker, accession_number, version_number, markdown_content, "
    "storage_path, trusted_claim_count, factual_claim_count, "
    "interpretive_claim_count, generated_at"
)

# Brief metadata without the full markdown body, for summary payloads.
BRIEF_META_COLUMNS = (
    "id, ticker, accession_number, version_number, storage_path, "
    "trusted_claim_count, factual_claim_count, interpretive_claim_count, "
    "generated_at"
)

CLAIM_COLUMNS = (
    "id, ticker, accession_number, document_key, theme, claim_text, "
    "supporting_excerpt, source_chunk_id, source_chunk_index, claim_type, "
    "confidence, review_status, created_at"
)

# Quarterly operating metrics (excludes the embedded valuation-derived rows,
# which are filtered out by src.quantitative). Queried per-ticker so the
# PostgREST 1000-row cap is never reached.
METRIC_COLUMNS = "ticker, fiscal_year, fiscal_quarter, metric_name, value, unit"

VALUATION_SNAPSHOT_COLUMNS = (
    "id, ticker, share_price_date, share_price, shares_outstanding, "
    "shares_outstanding_source_date, market_cap, cash, total_debt, "
    "enterprise_value, debt_measure, source, manually_reviewed, notes"
)

# Valuation data is a manually reviewed point-in-time snapshot, never a live
# market feed. Every valuation payload carries this so the dashboard can label
# it honestly.
_VALUATION_DISCLAIMER = (
    "Valuation data is a manually reviewed point-in-time snapshot, not a live "
    "market feed."
)


@lru_cache(maxsize=1)
def _supabase():
    """Create the Supabase client once and reuse it across requests."""
    return get_supabase_client()


# ValueError messages from src modules that mean "resource does not exist".
# Everything else (grounding failures, empty edits, no trusted claims) is a
# bad request.
_NOT_FOUND_PREFIXES = ("No proposed claim found", "No filing found")

# Public stand-in for claim_extraction_error: the raw provider text stays in
# Supabase for admin debugging but must never leave through a public GET.
_PUBLIC_EXTRACTION_ERROR = (
    "Claim extraction failed. Retry later or contact the administrator."
)


def _http_error(exc: ValueError) -> HTTPException:
    """Map a ValueError from the workflow modules to a 404 or 400 response."""
    detail = str(exc)
    status_code = 404 if detail.startswith(_NOT_FOUND_PREFIXES) else 400
    return HTTPException(status_code=status_code, detail=detail)


def require_admin_token(
    x_admin_token: str | None = Header(default=None),
) -> None:
    """Guard analyst write endpoints with the shared admin token.

    Read endpoints stay public; every mutating endpoint depends on this.
    The expected token is read per-request so the server never caches a
    stale value and tests can control it through the environment.
    """
    expected = os.getenv("ADMIN_API_TOKEN")
    if not expected:
        # Never reveal which variable is missing or any configuration value.
        raise HTTPException(
            status_code=500,
            detail="Server configuration error.",
        )
    if not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(
            status_code=401,
            detail="Admin token missing or invalid.",
        )


class ReviewNotesRequest(BaseModel):
    reviewer_notes: str | None = None


class EditClaimRequest(BaseModel):
    edited_claim_text: str = Field(min_length=1)
    reviewer_notes: str | None = None


class GenerateBriefRequest(BaseModel):
    ticker: str = Field(min_length=1)
    accession_number: str = Field(min_length=1)


class PromoteClaimsRequest(BaseModel):
    ticker: str | None = None
    accession_number: str | None = None


class ExtractClaimsRequest(BaseModel):
    max_claims: int = Field(default=5, ge=1, le=10)


@app.get("/health")
def health() -> dict:
    """Liveness check for the API service."""
    return {"status": "ok", "service": "earnings-intelligence-os"}


@app.get("/companies")
def list_companies() -> dict:
    """Return the monitored-company watchlist, ordered by ticker."""
    companies = (
        _supabase()
        .table("companies")
        .select("ticker, company_name, cik, business_model")
        .order("ticker", desc=False)
        .execute()
        .data
    )
    return {"count": len(companies), "companies": companies}


def _trusted_promoted_count(supabase, ticker: str | None = None) -> int:
    """Count human-promoted trusted rows (legacy seeded rows excluded)."""
    query = (
        supabase.table("qualitative_claims")
        .select("proposed_claim_id", count="exact")
        .not_.is_("proposed_claim_id", "null")
    )
    if ticker is not None:
        query = query.eq("ticker", ticker)
    return query.execute().count or 0


def _extraction_ready_filings(supabase, ticker: str) -> list[dict]:
    """Compact extraction-ready rows for one company (no per-claim counts)."""
    filings = (
        supabase.table("filings")
        .select(
            "id, accession_number, form, filing_date, "
            "earnings_release_document_id, claim_extraction_status"
        )
        .eq("ticker", ticker)
        .eq("exhibit_processing_status", "processed")
        .not_.is_("earnings_release_document_id", "null")
        .order("filing_date", desc=True)
        .execute()
        .data
    )
    rows = []
    for filing in filings:
        documents = (
            supabase.table("filing_documents")
            .select("filename")
            .eq("id", filing["earnings_release_document_id"])
            .execute()
            .data
        )
        filename = documents[0]["filename"] if documents else None
        chunk_count = (
            supabase.table("filing_chunks")
            .select("id", count="exact")
            .eq("filing_document_id", filing["earnings_release_document_id"])
            .execute()
            .count
            or 0
        )
        rows.append(
            {
                "accession_number": filing["accession_number"],
                "form": filing["form"],
                "filing_date": filing["filing_date"],
                "filename": filename,
                "document_key": f"exhibit:{filename}" if filename else None,
                "chunk_count": chunk_count,
                "claim_extraction_status": filing["claim_extraction_status"],
            }
        )
    return rows


@app.get("/companies/{ticker}")
def get_company(ticker: str) -> dict:
    """Return one monitored company with its research-pipeline summary."""
    supabase = _supabase()
    normalized = ticker.upper()

    companies = (
        supabase.table("companies")
        .select("ticker, company_name, cik, business_model")
        .eq("ticker", normalized)
        .execute()
        .data
    )
    if not companies:
        raise HTTPException(
            status_code=404,
            detail=f"No monitored company found for ticker={normalized!r}.",
        )

    filings_count = (
        supabase.table("filings")
        .select("id", count="exact")
        .eq("ticker", normalized)
        .execute()
        .count
        or 0
    )
    chunked_count = (
        supabase.table("filings")
        .select("id", count="exact")
        .eq("ticker", normalized)
        .eq("processing_status", "chunked")
        .execute()
        .count
        or 0
    )
    recent_filings = (
        supabase.table("filings")
        .select(FILING_COLUMNS)
        .eq("ticker", normalized)
        .order("filing_date", desc=True)
        .limit(10)
        .execute()
        .data
    )
    extraction_ready = _extraction_ready_filings(supabase, normalized)
    briefs = (
        supabase.table("earnings_briefs")
        .select(BRIEF_META_COLUMNS)
        .eq("ticker", normalized)
        .order("generated_at", desc=True)
        .limit(1)
        .execute()
        .data
    )

    return {
        "company": companies[0],
        "filings_count": filings_count,
        "chunked_filings_count": chunked_count,
        "extraction_ready_count": len(extraction_ready),
        "trusted_claim_count": _trusted_promoted_count(supabase, normalized),
        "latest_brief": briefs[0] if briefs else None,
        "recent_filings": recent_filings,
        "extraction_ready": extraction_ready,
    }


@app.get("/overview")
def get_overview() -> dict:
    """Cross-company research dashboard summary. Public and read-only."""
    supabase = _supabase()

    companies = (
        supabase.table("companies")
        .select("ticker, company_name")
        .order("ticker", desc=False)
        .execute()
        .data
    )
    total_filings = (
        supabase.table("filings").select("id", count="exact").execute().count or 0
    )
    pending_grounded = (
        supabase.table("proposed_claims")
        .select("id", count="exact")
        .eq("review_status", "pending")
        .not_.is_("source_chunk_id", "null")
        .execute()
        .count
        or 0
    )
    total_briefs = (
        supabase.table("earnings_briefs")
        .select("id", count="exact")
        .execute()
        .count
        or 0
    )

    rows = []
    total_extraction_ready = 0
    for company in companies:
        ticker = company["ticker"]
        extraction_ready = (
            supabase.table("filings")
            .select("id", count="exact")
            .eq("ticker", ticker)
            .eq("exhibit_processing_status", "processed")
            .not_.is_("earnings_release_document_id", "null")
            .execute()
            .count
            or 0
        )
        total_extraction_ready += extraction_ready
        latest_filing = (
            supabase.table("filings")
            .select("filing_date")
            .eq("ticker", ticker)
            .order("filing_date", desc=True)
            .limit(1)
            .execute()
            .data
        )
        briefs = (
            supabase.table("earnings_briefs")
            .select("version_number")
            .eq("ticker", ticker)
            .order("version_number", desc=True)
            .limit(1)
            .execute()
            .data
        )
        rows.append(
            {
                "ticker": ticker,
                "company_name": company["company_name"],
                "extraction_ready_count": extraction_ready,
                "trusted_claim_count": _trusted_promoted_count(supabase, ticker),
                "latest_brief_version": (
                    briefs[0]["version_number"] if briefs else None
                ),
                "latest_filing_date": (
                    latest_filing[0]["filing_date"] if latest_filing else None
                ),
            }
        )

    return {
        "companies_count": len(companies),
        "total_filings_count": total_filings,
        "extraction_ready_count": total_extraction_ready,
        "pending_grounded_claim_count": pending_grounded,
        "trusted_claim_count": _trusted_promoted_count(supabase),
        "stored_brief_count": total_briefs,
        "companies": rows,
    }


def _company_or_404(supabase, ticker: str) -> dict:
    """Return one company row by ticker (uppercased) or raise 404."""
    companies = (
        supabase.table("companies")
        .select("ticker, company_name, cik, business_model")
        .eq("ticker", ticker)
        .execute()
        .data
    )
    if not companies:
        raise HTTPException(
            status_code=404,
            detail=f"No monitored company found for ticker={ticker!r}.",
        )
    return companies[0]


def _metric_rows(supabase, ticker: str) -> list[dict]:
    """Operating metric rows for one ticker (valuation rows filtered out)."""
    rows = (
        supabase.table("financial_metrics")
        .select(METRIC_COLUMNS)
        .eq("ticker", ticker)
        .execute()
        .data
    )
    return operating_rows(rows)


def _valuation_snapshot(supabase, ticker: str) -> dict | None:
    """Latest manually reviewed valuation snapshot for one ticker, or None."""
    rows = (
        supabase.table("valuation_snapshots")
        .select(VALUATION_SNAPSHOT_COLUMNS)
        .eq("ticker", ticker)
        .order("share_price_date", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


@app.get("/metrics/{ticker}")
def get_metrics(ticker: str, metric_name: str | None = None) -> dict:
    """Return the historical operating-metric time series for one company.

    Deterministic, AI-free read of ``financial_metrics``. Valuation-derived
    rows are excluded (see ``/valuation-snapshots``). Optional ``metric_name``
    narrows the response to a single metric. 404 for an unknown ticker.
    """
    supabase = _supabase()
    normalized = ticker.upper()
    _company_or_404(supabase, normalized)

    rows = _metric_rows(supabase, normalized)
    if metric_name is not None:
        rows = [row for row in rows if row["metric_name"] == metric_name]

    series = build_metric_series(rows)
    periods = [p["period"] for p in sorted_periods(rows)]
    latest_values = latest_metric_values(rows)
    latest = max(
        (
            (row["fiscal_year"], row["fiscal_quarter"])
            for row in rows
        ),
        key=lambda p: period_sort_key(*p),
        default=None,
    )

    return {
        "ticker": normalized,
        "metric_name": metric_name,
        "metric_count": len(series),
        "period_count": len(periods),
        "periods": periods,
        "metrics": series,
        "latest_period": period_label(*latest) if latest else None,
        "latest_period_summary": latest_values,
    }


def _peer_row(supabase, company: dict) -> dict:
    """Build one latest-period peer-comparison row with valuation multiples."""
    ticker = company["ticker"]
    latest_values = latest_metric_values(_metric_rows(supabase, ticker))

    def metric(name: str):
        return latest_values.get(name)

    snapshot = _valuation_snapshot(supabase, ticker)
    market_cap = snapshot.get("market_cap") if snapshot else None
    enterprise_value = snapshot.get("enterprise_value") if snapshot else None

    multiples = compute_multiples(
        market_cap=market_cap,
        enterprise_value=enterprise_value,
        ttm_revenue=metric("TTM Revenue"),
        ttm_operating_income=metric("TTM Operating Income"),
        ttm_free_cash_flow=metric("TTM Free Cash Flow"),
    )

    row = {
        "ticker": ticker,
        "company_name": company["company_name"],
        "business_model": company["business_model"],
    }
    # Operating metrics at the latest reported quarter (honest null when absent).
    for source_name, field in PEER_METRIC_FIELDS.items():
        row[field] = metric(source_name)
    # Valuation snapshot fields (point-in-time, not live).
    row["valuation_snapshot_date"] = (
        snapshot.get("share_price_date") if snapshot else None
    )
    row["share_price"] = snapshot.get("share_price") if snapshot else None
    row["market_cap"] = market_cap
    row["enterprise_value"] = enterprise_value
    row["debt_measure"] = snapshot.get("debt_measure") if snapshot else None
    row["valuation_notes"] = snapshot.get("notes") if snapshot else None
    row.update(multiples)
    return row


@app.get("/peers")
def get_peers() -> dict:
    """Latest-period peer-comparison table across all monitored companies.

    Operating metrics come from ``financial_metrics``; valuation fields and
    multiples come from the manually reviewed ``valuation_snapshots`` and are
    computed deterministically. Unavailable values are surfaced as ``null``
    rather than fabricated. Valuation data is a dated snapshot, not live.
    """
    supabase = _supabase()
    companies = (
        supabase.table("companies")
        .select("ticker, company_name, cik, business_model")
        .order("ticker", desc=False)
        .execute()
        .data
    )

    rows = [_peer_row(supabase, company) for company in companies]
    snapshot_dates = sorted(
        {row["valuation_snapshot_date"] for row in rows if row["valuation_snapshot_date"]}
    )
    comparability_notes = [
        {
            "ticker": row["ticker"],
            "business_model": row["business_model"],
            "debt_measure": row["debt_measure"],
            "notes": row["valuation_notes"],
        }
        for row in rows
    ]

    return {
        "count": len(rows),
        "peers": rows,
        "valuation_is_live": False,
        "valuation_snapshot_dates": snapshot_dates,
        "valuation_disclaimer": _VALUATION_DISCLAIMER,
        "comparability_notes": comparability_notes,
    }


@app.get("/peers/trends")
def get_peer_trends(
    metric_name: str,
    ticker: str | None = None,
    limit: int = Query(default=0, ge=0, le=100),
) -> dict:
    """Chart-ready time series for one metric across companies.

    ``metric_name`` is required. Optional ``ticker`` restricts to one company;
    optional ``limit`` keeps only the most recent N periods per company.
    """
    supabase = _supabase()
    companies = (
        supabase.table("companies")
        .select("ticker, company_name")
        .order("ticker", desc=False)
        .execute()
        .data
    )
    if ticker is not None:
        normalized = ticker.upper()
        companies = [c for c in companies if c["ticker"] == normalized]

    series = []
    for company in companies:
        rows = _metric_rows(supabase, company["ticker"])
        points = [
            {
                "fiscal_year": row["fiscal_year"],
                "fiscal_quarter": row["fiscal_quarter"],
                "period": period_label(row["fiscal_year"], row["fiscal_quarter"]),
                "value": row.get("value"),
            }
            for row in rows
            if row["metric_name"] == metric_name
        ]
        points.sort(key=lambda p: period_sort_key(p["fiscal_year"], p["fiscal_quarter"]))
        if limit:
            points = points[-limit:]
        series.append(
            {
                "ticker": company["ticker"],
                "company_name": company["company_name"],
                "points": points,
            }
        )

    return {"metric_name": metric_name, "series": series}


@app.get("/valuation-snapshots")
def get_valuation_snapshots() -> dict:
    """Return the manually reviewed point-in-time valuation snapshots.

    These are dated, audited snapshots — never a live market feed. Every row
    carries ``is_live = false``.
    """
    rows = (
        _supabase()
        .table("valuation_snapshots")
        .select(VALUATION_SNAPSHOT_COLUMNS)
        .order("ticker", desc=False)
        .execute()
        .data
    )
    for row in rows:
        row["is_live"] = False
    snapshot_dates = sorted({row["share_price_date"] for row in rows if row.get("share_price_date")})
    return {
        "count": len(rows),
        "snapshots": rows,
        "is_live": False,
        "valuation_snapshot_dates": snapshot_dates,
        "valuation_disclaimer": _VALUATION_DISCLAIMER,
    }


@app.get("/admin/validate", dependencies=[Depends(require_admin_token)])
def validate_admin_token() -> dict:
    """Confirm the supplied X-Admin-Token is valid.

    The only GET route that reads the admin token; the dashboard uses it to
    verify a saved token without performing any mutation.
    """
    return {"status": "ok"}


@app.get("/filings")
def list_filings(
    ticker: str | None = None,
    status: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
) -> dict:
    """Return the recent filing feed, newest filings first."""
    query = _supabase().table("filings").select(FILING_COLUMNS)
    if ticker is not None:
        query = query.eq("ticker", ticker.upper())
    if status is not None:
        query = query.eq("processing_status", status)
    filings = query.order("filing_date", desc=True).limit(limit).execute().data
    return {"count": len(filings), "filings": filings}


@app.get("/filings/{accession_number}")
def get_filing(accession_number: str) -> dict:
    """Return one filing with its documents and total chunk count."""
    supabase = _supabase()

    filings = (
        supabase.table("filings")
        .select(FILING_COLUMNS)
        .eq("accession_number", accession_number)
        .execute()
        .data
    )
    if not filings:
        raise HTTPException(
            status_code=404,
            detail=f"No filing found with accession_number={accession_number!r}.",
        )

    documents = (
        supabase.table("filing_documents")
        .select(DOCUMENT_COLUMNS)
        .eq("accession_number", accession_number)
        .execute()
        .data
    )

    chunk_count = (
        supabase.table("filing_chunks")
        .select("id", count="exact")
        .eq("accession_number", accession_number)
        .execute()
        .count
    )

    return {
        "filing": filings[0],
        "documents": documents,
        "chunk_count": chunk_count or 0,
    }


@app.get("/briefs/latest/{ticker}")
def get_latest_brief(ticker: str) -> dict:
    """Return the most recently generated stored earnings brief for a ticker."""
    briefs = (
        _supabase()
        .table("earnings_briefs")
        .select(BRIEF_COLUMNS)
        .eq("ticker", ticker.upper())
        .order("generated_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not briefs:
        raise HTTPException(
            status_code=404,
            detail=f"No stored earnings brief found for ticker={ticker.upper()!r}.",
        )
    return briefs[0]


@app.get("/review-queue")
def list_review_queue() -> dict:
    """Return grounded pending AI-drafted claims awaiting analyst review.

    Legacy rows without a source_chunk_id are ungrounded and never exposed.
    """
    claims = (
        _supabase()
        .table("proposed_claims")
        .select(CLAIM_COLUMNS)
        .eq("review_status", "pending")
        .not_.is_("source_chunk_id", "null")
        .order("created_at", desc=False)
        .execute()
        .data
    )
    return {"count": len(claims), "claims": claims}


@app.get("/extraction-ready")
def list_extraction_ready() -> dict:
    """Return filings whose earnings-release exhibit is ingested and chunked.

    These filings have a processed EX-99.1 exhibit with stored chunks and are
    ready for the manual grounded-claim extraction step. Read-only; the API
    never triggers extraction itself.
    """
    supabase = _supabase()

    filings = (
        supabase.table("filings")
        .select(
            "id, ticker, accession_number, form, filing_date, "
            "exhibit_processing_status, earnings_release_document_id, "
            "claim_extraction_status, claim_extracted_at, "
            "claim_extraction_error"
        )
        .eq("exhibit_processing_status", "processed")
        .not_.is_("earnings_release_document_id", "null")
        .order("filing_date", desc=True)
        .execute()
        .data
    )

    results = []
    for filing in filings:
        accession_number = filing["accession_number"]
        document_id = filing["earnings_release_document_id"]
        documents = (
            supabase.table("filing_documents")
            .select("id, filename")
            .eq("id", document_id)
            .execute()
            .data
        )
        filename = documents[0]["filename"] if documents else None
        chunk_count = (
            supabase.table("filing_chunks")
            .select("id", count="exact")
            .eq("filing_document_id", document_id)
            .execute()
            .count
            or 0
        )
        pending_grounded = (
            supabase.table("proposed_claims")
            .select("id", count="exact")
            .eq("accession_number", accession_number)
            .eq("review_status", "pending")
            .not_.is_("source_chunk_id", "null")
            .execute()
            .count
            or 0
        )
        # qualitative_claims has no accession column; trusted rows are
        # matched through the proposed_claims they were promoted from.
        claim_ids = [
            row["id"]
            for row in supabase.table("proposed_claims")
            .select("id")
            .eq("accession_number", accession_number)
            .execute()
            .data
        ]
        trusted_promoted = 0
        if claim_ids:
            trusted_promoted = (
                supabase.table("qualitative_claims")
                .select("proposed_claim_id", count="exact")
                .in_("proposed_claim_id", claim_ids)
                .execute()
                .count
                or 0
            )
        briefs = (
            supabase.table("earnings_briefs")
            .select("version_number")
            .eq("accession_number", accession_number)
            .order("version_number", desc=True)
            .limit(1)
            .execute()
            .data
        )
        results.append(
            {
                "filing_id": filing["id"],
                "ticker": filing["ticker"],
                "accession_number": accession_number,
                "form": filing["form"],
                "filing_date": filing["filing_date"],
                "exhibit_processing_status": filing["exhibit_processing_status"],
                "earnings_release_document_id": document_id,
                "filename": filename,
                "document_key": f"exhibit:{filename}" if filename else None,
                "chunk_count": chunk_count,
                "ready_for_extraction": chunk_count > 0,
                "claim_extraction_status": filing["claim_extraction_status"],
                "claim_extracted_at": filing["claim_extracted_at"],
                "claim_extraction_error": (
                    _PUBLIC_EXTRACTION_ERROR
                    if filing["claim_extraction_error"]
                    else None
                ),
                "pending_grounded_claim_count": pending_grounded,
                "trusted_promoted_claim_count": trusted_promoted,
                "latest_brief_version": (
                    briefs[0]["version_number"] if briefs else None
                ),
            }
        )

    return {"count": len(results), "filings": results}


@app.post(
    "/extraction-ready/{accession_number}/extract",
    dependencies=[Depends(require_admin_token)],
)
def extract_claims(
    accession_number: str, body: ExtractClaimsRequest | None = None
) -> dict:
    """Run manual grounded claim extraction on an extraction-ready filing.

    The only route that calls Gemini, and only when an admin triggers it —
    extraction is never scheduled. Quota and rate-limit failures map to 429
    so the analyst can back off without burning more free-tier quota.
    """
    max_claims = body.max_claims if body else 5
    try:
        return extract_claims_for_ready_filing(
            accession_number, max_claims=max_claims
        )
    except ValueError as exc:
        raise _http_error(exc)
    except ClaimExtractionQuotaError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except ClaimExtractionError as exc:
        # The exception message is already caller-safe; never include the
        # underlying provider error here.
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/review-queue/{claim_id}/approve", dependencies=[Depends(require_admin_token)])
def approve_review_claim(claim_id: int, body: ReviewNotesRequest | None = None) -> dict:
    """Approve a grounded proposed claim as-is."""
    notes = body.reviewer_notes if body else None
    try:
        return approve_claim(claim_id, reviewer_notes=notes)
    except ValueError as exc:
        raise _http_error(exc)


@app.post("/review-queue/{claim_id}/edit", dependencies=[Depends(require_admin_token)])
def edit_review_claim(claim_id: int, body: EditClaimRequest) -> dict:
    """Approve a grounded proposed claim with corrected analyst wording."""
    try:
        return approve_claim_with_edits(
            claim_id,
            edited_claim_text=body.edited_claim_text,
            reviewer_notes=body.reviewer_notes,
        )
    except ValueError as exc:
        raise _http_error(exc)


@app.post("/review-queue/{claim_id}/reject", dependencies=[Depends(require_admin_token)])
def reject_review_claim(claim_id: int, body: ReviewNotesRequest | None = None) -> dict:
    """Reject a proposed claim. Ungrounded legacy rows may be rejected."""
    notes = body.reviewer_notes if body else None
    try:
        return reject_claim(claim_id, reviewer_notes=notes)
    except ValueError as exc:
        raise _http_error(exc)


@app.post("/claims/promote", dependencies=[Depends(require_admin_token)])
def promote_claims(body: PromoteClaimsRequest | None = None) -> dict:
    """Promote approved and edited grounded claims into qualitative_claims.

    An optional body scopes promotion to one ticker and/or one filing;
    with no body, every eligible claim is promoted. Pending, rejected,
    and ungrounded claims are never promoted. Safe to rerun:
    already-promoted claims are skipped.
    """
    ticker = body.ticker if body else None
    accession_number = body.accession_number if body else None
    return promote_reviewed_claims(
        ticker=ticker,
        accession_number=accession_number,
    )


@app.post("/briefs/generate", dependencies=[Depends(require_admin_token)])
def generate_brief(body: GenerateBriefRequest) -> dict:
    """Generate, upload, and store the next versioned earnings brief."""
    try:
        return generate_and_store_earnings_brief(
            ticker=body.ticker.upper(),
            accession_number=body.accession_number,
        )
    except ValueError as exc:
        raise _http_error(exc)
