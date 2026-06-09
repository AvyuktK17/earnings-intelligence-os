"""Research API for the Earnings Intelligence OS dashboard.

Read endpoints serve the filing feed, filing detail, stored briefs, and the
analyst review queue. Write endpoints drive the analyst workflow: approve,
edit, or reject proposed claims, promote reviewed claims into trusted
qualitative_claims, and generate versioned earnings briefs. No AI calls,
no authentication yet. Run locally with:

    uvicorn app.main:app --reload
"""

import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.brief_storage import generate_and_store_earnings_brief
from src.claim_promotion import promote_reviewed_claims
from src.claim_review import approve_claim, approve_claim_with_edits, reject_claim
from src.database import get_supabase_client

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


def _http_error(exc: ValueError) -> HTTPException:
    """Map a ValueError from the workflow modules to a 404 or 400 response."""
    detail = str(exc)
    status_code = 404 if detail.startswith(_NOT_FOUND_PREFIXES) else 400
    return HTTPException(status_code=status_code, detail=detail)


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


@app.get("/health")
def health() -> dict:
    """Liveness check for the API service."""
    return {"status": "ok", "service": "earnings-intelligence-os"}


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


@app.post("/review-queue/{claim_id}/approve")
def approve_review_claim(claim_id: int, body: ReviewNotesRequest | None = None) -> dict:
    """Approve a grounded proposed claim as-is."""
    notes = body.reviewer_notes if body else None
    try:
        return approve_claim(claim_id, reviewer_notes=notes)
    except ValueError as exc:
        raise _http_error(exc)


@app.post("/review-queue/{claim_id}/edit")
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


@app.post("/review-queue/{claim_id}/reject")
def reject_review_claim(claim_id: int, body: ReviewNotesRequest | None = None) -> dict:
    """Reject a proposed claim. Ungrounded legacy rows may be rejected."""
    notes = body.reviewer_notes if body else None
    try:
        return reject_claim(claim_id, reviewer_notes=notes)
    except ValueError as exc:
        raise _http_error(exc)


@app.post("/claims/promote")
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


@app.post("/briefs/generate")
def generate_brief(body: GenerateBriefRequest) -> dict:
    """Generate, upload, and store the next versioned earnings brief."""
    try:
        return generate_and_store_earnings_brief(
            ticker=body.ticker.upper(),
            accession_number=body.accession_number,
        )
    except ValueError as exc:
        raise _http_error(exc)
