"""Read-only research API for the Earnings Intelligence OS dashboard.

Every endpoint only reads from Supabase. No AI calls, no row mutations,
no authentication yet. Run locally with:

    uvicorn app.main:app --reload
"""

from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query

from src.database import get_supabase_client

app = FastAPI(title="Earnings Intelligence OS API")

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
