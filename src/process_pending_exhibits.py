from src.database import get_supabase_client
from src.exhibit_status import (
    mark_exhibit_failed,
    mark_exhibit_not_found,
    mark_exhibit_processed,
)
from src.filing_chunker import chunk_and_store_document
from src.filing_exhibits import get_filing_exhibits, select_earnings_release_exhibit
from src.process_filing_exhibit import process_earnings_release_exhibit


def _existing_document_ingestion(
    supabase, accession_number: str, filename: str
) -> dict | None:
    """Return stats when the selected exhibit is already ingested and chunked.

    Reuse requires an exact filename match with the currently selected
    candidate — never an arbitrary earnings-release document — so a filing
    can upgrade to a better-ranked exhibit (e.g. press release over slide
    deck) while a filing whose selected exhibit is unchanged keeps its
    existing chunk ids. Grounded claims reference chunks by id (RESTRICT
    foreign key), so the matched document is never re-chunked.
    """
    documents = (
        supabase.table("filing_documents")
        .select("id, filename")
        .eq("accession_number", accession_number)
        .eq("filename", filename)
        .execute()
        .data
    )
    if not documents:
        return None

    document = documents[0]
    chunks = (
        supabase.table("filing_chunks")
        .select("character_count")
        .eq("filing_document_id", document["id"])
        .execute()
        .data
    )
    if not chunks:
        return None

    total_characters = sum(c["character_count"] for c in chunks)
    return {
        "filing_document_id": document["id"],
        "filename": document["filename"],
        "document_key": f"exhibit:{document['filename']}",
        "chunk_count": len(chunks),
        "average_chunk_characters": round(total_characters / len(chunks)),
    }


def process_pending_exhibits(
    limit: int = 3,
    include_failed: bool = False,
) -> list[dict]:
    """Ingest earnings-release exhibits for chunked 8-K filings not yet checked.

    Selects at most `limit` 8-K filings with processing_status "chunked" and
    exhibit_processing_status "not_checked" (plus "failed" when
    include_failed is True), newest filing_date first. For each filing the
    worker discovers and ranks the likely earnings-release exhibit first;
    if that exact document is already ingested and chunked it is reused,
    otherwise it is downloaded/parsed/uploaded and chunked, and the filing's
    earnings_release_document_id moves to it. Previously ingested
    lower-ranked documents (and their chunks) are kept as secondary
    evidence, never deleted. Rows already marked "processed" or "not_found"
    are never selected again. One filing's failure is recorded and never
    stops the rest of the batch. No AI calls.

    Args:
        limit: Maximum number of filings to process in this run.
        include_failed: Also retry filings whose last attempt failed.

    Returns:
        One result dict per selected filing with ticker, accession_number,
        and status ("processed", "not_found", or "failed"); processed results
        add filing_document_id, filename, document_key, chunk_count, and
        average_chunk_characters; failed results add error_message.
    """
    supabase = get_supabase_client()
    statuses = ["not_checked", "failed"] if include_failed else ["not_checked"]

    filings = (
        supabase.table("filings")
        .select("id, ticker, accession_number, sec_url, filing_date")
        .eq("form", "8-K")
        .eq("processing_status", "chunked")
        .in_("exhibit_processing_status", statuses)
        .order("filing_date", desc=True)
        .limit(limit)
        .execute()
        .data
    )

    results = []
    for filing in filings:
        accession_number = filing["accession_number"]
        base = {"ticker": filing["ticker"], "accession_number": accession_number}

        try:
            exhibits = get_filing_exhibits(filing["sec_url"])
            exhibit = select_earnings_release_exhibit(exhibits)
            if exhibit is None:
                mark_exhibit_not_found(accession_number)
                results.append({**base, "status": "not_found"})
                continue

            existing = _existing_document_ingestion(
                supabase, accession_number, exhibit["filename"]
            )
            if existing is not None:
                mark_exhibit_processed(
                    accession_number, existing["filing_document_id"]
                )
                results.append({**base, "status": "processed", **existing})
                continue

            processed = process_earnings_release_exhibit(accession_number)
            filing_document_id = processed["filing_document_id"]
            chunked = chunk_and_store_document(filing_document_id)
            mark_exhibit_processed(accession_number, filing_document_id)
            results.append(
                {
                    **base,
                    "status": "processed",
                    "filing_document_id": filing_document_id,
                    "filename": processed["filename"],
                    "document_key": chunked["document_key"],
                    "chunk_count": chunked["chunk_count"],
                    "average_chunk_characters": chunked["average_chunk_characters"],
                }
            )
        except Exception as exc:  # one bad filing must not stop the batch
            error_message = str(exc)
            try:
                mark_exhibit_failed(accession_number, error_message)
            except Exception:
                pass  # bookkeeping failure must not mask the original error
            results.append(
                {**base, "status": "failed", "error_message": error_message}
            )

    return results
