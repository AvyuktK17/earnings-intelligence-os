import os

from src.filing_downloader import download_filing
from src.filing_parser import extract_filing_text
from src.filing_status import mark_filing_downloaded, mark_filing_parsed


def process_filing(filing: dict) -> dict:
    """Download, parse, and record status for a single filing.

    Args:
        filing: A dict containing ticker, accession_number, and sec_url.

    Returns:
        A dict with ticker, accession_number, status, html_path, text_path,
        html_size_bytes, and text_size_bytes.

    Raises:
        ValueError: If required fields are missing from the filing dict.
    """
    for field in ("ticker", "accession_number", "sec_url"):
        if not filing.get(field):
            raise ValueError(f"Filing is missing required field: '{field}'")

    ticker = filing["ticker"].lower()
    accession_number = filing["accession_number"]
    sec_url = filing["sec_url"]

    safe_accession = accession_number.replace("-", "_")

    html_path = f"data/raw_filings/{ticker}_{safe_accession}.html"
    text_path = f"data/parsed_filings/{ticker}_{safe_accession}.txt"

    download_filing(sec_url, html_path)
    mark_filing_downloaded(accession_number)

    extract_filing_text(html_path, text_path)
    mark_filing_parsed(accession_number)

    html_size = os.path.getsize(html_path)
    text_size = os.path.getsize(text_path)

    return {
        "ticker": filing["ticker"],
        "accession_number": accession_number,
        "status": "parsed",
        "html_path": html_path,
        "text_path": text_path,
        "html_size_bytes": html_size,
        "text_size_bytes": text_size,
    }
