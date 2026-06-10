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
