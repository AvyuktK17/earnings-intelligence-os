import os
import re

from src.database import get_supabase_client
from src.filing_exhibits import get_filing_exhibits, select_earnings_release_exhibit
from src.filing_downloader import download_filing
from src.filing_parser import extract_filing_text
from src.storage import upload_file


def _safe_filename(filename: str) -> str:
    """Replace path-unsafe characters with underscores."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", filename)


def process_earnings_release_exhibit(accession_number: str) -> dict:
    """Download, parse, upload, and record the earnings-release exhibit for a filing.

    Looks up the filing by accession number, discovers the EX-99.1 earnings
    release exhibit via the SEC EDGAR index, downloads and parses it locally,
    uploads both files to private Supabase Storage, and upserts one row into
    filing_documents.  Safe to rerun: the upsert on (accession_number, filename)
    prevents duplicate rows.

    Args:
        accession_number: The filing's unique accession number.

    Returns:
        A dict with filing_document_id, filing_id, ticker, accession_number,
        document_type, filename, sec_url, html_storage_path,
        text_storage_path, html_size_bytes, and text_size_bytes.

    Raises:
        ValueError: If the filing is not found or no earnings-release exhibit
            is discovered in the SEC EDGAR directory.
    """
    supabase = get_supabase_client()

    filing_response = (
        supabase.table("filings")
        .select("id, ticker, accession_number, sec_url")
        .eq("accession_number", accession_number)
        .execute()
    )
    if not filing_response.data:
        raise ValueError(f"No filing found with accession_number={accession_number!r}.")

    filing = filing_response.data[0]
    filing_id = filing["id"]
    ticker = filing["ticker"].lower()
    sec_url = filing["sec_url"]

    exhibits = get_filing_exhibits(sec_url)
    exhibit = select_earnings_release_exhibit(exhibits)

    if exhibit is None:
        raise ValueError(
            f"No earnings-release exhibit found for accession_number={accession_number!r}. "
            "The filing may not have an attached EX-99.1 document."
        )

    filename = exhibit["filename"]
    exhibit_url = exhibit["url"]
    safe_acc = accession_number.replace("-", "_")
    safe_fn = _safe_filename(filename)

    html_local = f"data/raw_filings/{ticker}_{safe_acc}_{safe_fn}"
    text_local = f"data/parsed_filings/{ticker}_{safe_acc}_{safe_fn}.txt"

    download_filing(exhibit_url, html_local)
    extract_filing_text(html_local, text_local)

    html_storage_path = f"html/{ticker}/{accession_number}/exhibits/{filename}"
    text_storage_path = f"parsed/{ticker}/{accession_number}/exhibits/{filename}.txt"

    upload_file(html_local, html_storage_path)
    upload_file(text_local, text_storage_path)

    row = {
        "filing_id": filing_id,
        "ticker": ticker,
        "accession_number": accession_number,
        "document_type": "earnings_release",
        "filename": filename,
        "sec_url": exhibit_url,
        "html_storage_path": html_storage_path,
        "text_storage_path": text_storage_path,
    }
    supabase.table("filing_documents").upsert(
        row,
        on_conflict="accession_number,filename",
    ).execute()

    # Read the row id back rather than trusting the upsert response, so both
    # the insert and the duplicate-update paths return the same stable id.
    document_response = (
        supabase.table("filing_documents")
        .select("id")
        .eq("accession_number", accession_number)
        .eq("filename", filename)
        .execute()
    )
    if not document_response.data:
        raise ValueError(
            f"filing_documents row missing after upsert for "
            f"accession_number={accession_number!r}, filename={filename!r}."
        )
    filing_document_id = document_response.data[0]["id"]

    html_size = os.path.getsize(html_local)
    text_size = os.path.getsize(text_local)

    return {
        "filing_document_id": filing_document_id,
        "filing_id": filing_id,
        "ticker": ticker,
        "accession_number": accession_number,
        "document_type": "earnings_release",
        "filename": filename,
        "sec_url": exhibit_url,
        "html_storage_path": html_storage_path,
        "text_storage_path": text_storage_path,
        "html_size_bytes": html_size,
        "text_size_bytes": text_size,
    }
