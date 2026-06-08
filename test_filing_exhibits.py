"""
Test filing exhibit discovery and download for the Broadcom 8-K (0001730168-26-000051).
Downloads the EX-99.1 earnings release exhibit, parses it, and verifies it is
materially longer than the primary 8-K cover document.
Does NOT modify the filings table or upload anything to Supabase Storage.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.filing_exhibits import get_filing_exhibits, select_earnings_release_exhibit
from src.filing_downloader import download_filing
from src.filing_parser import extract_filing_text

ACCESSION_NUMBER = "0001730168-26-000051"

EXHIBIT_HTML_PATH = "data/raw_filings/avgo_0001730168_26_000051_exhibit.html"
EXHIBIT_TXT_PATH = "data/parsed_filings/avgo_0001730168_26_000051_exhibit.txt"

# Primary 8-K cover page is ~33 KB; the earnings release should be much larger
MIN_EXHIBIT_HTML_BYTES = 100_000
MIN_EXHIBIT_TEXT_CHARS = 10_000


def main():
    supabase = get_supabase_client()

    filing_response = (
        supabase.table("filings")
        .select("sec_url, processing_status")
        .eq("accession_number", ACCESSION_NUMBER)
        .execute()
    )
    assert filing_response.data, (
        f"No filing found for accession_number={ACCESSION_NUMBER!r}."
    )
    filing = filing_response.data[0]
    sec_url = filing["sec_url"]

    print(f"Filing        : {ACCESSION_NUMBER}")
    print(f"Status        : {filing['processing_status']}")
    print(f"Primary URL   : {sec_url}")

    # Step 1: Fetch all files in the filing directory
    print("\nFetching filing index...")
    exhibits = get_filing_exhibits(sec_url)
    assert exhibits, "Expected at least one file in the filing directory."
    print(f"  Found {len(exhibits)} files:")
    for ex in exhibits:
        print(
            f"    [{ex['likely_exhibit_type']:20s}] {ex['filename']}"
            f"  ({ex['size_bytes']:,} bytes)"
        )

    # Step 2: Select the earnings release exhibit
    exhibit = select_earnings_release_exhibit(exhibits)
    assert exhibit is not None, (
        "Expected to find an earnings release exhibit (EX-99.1) but none was selected."
    )
    print(f"\nSelected exhibit  : {exhibit['filename']}")
    print(f"  URL             : {exhibit['url']}")
    print(f"  Size (est.)     : {exhibit['size_bytes']:,} bytes")
    print(f"  Exhibit type    : {exhibit['likely_exhibit_type']}")

    assert exhibit["likely_exhibit_type"] == "earnings_release", (
        f"Expected 'earnings_release', got {exhibit['likely_exhibit_type']!r}."
    )

    # Step 3: Download the exhibit HTML
    print(f"\nDownloading to {EXHIBIT_HTML_PATH} ...")
    download_filing(exhibit["url"], EXHIBIT_HTML_PATH)
    html_size = os.path.getsize(EXHIBIT_HTML_PATH)
    print(f"  Downloaded: {html_size:,} bytes")

    assert os.path.exists(EXHIBIT_HTML_PATH), f"File not found: {EXHIBIT_HTML_PATH}"
    assert html_size >= MIN_EXHIBIT_HTML_BYTES, (
        f"Downloaded HTML is {html_size:,} bytes; expected >= {MIN_EXHIBIT_HTML_BYTES:,}."
    )

    # Step 4: Parse the exhibit to plain text
    print(f"\nParsing to {EXHIBIT_TXT_PATH} ...")
    extract_filing_text(EXHIBIT_HTML_PATH, EXHIBIT_TXT_PATH)
    assert os.path.exists(EXHIBIT_TXT_PATH), f"File not found: {EXHIBIT_TXT_PATH}"

    with open(EXHIBIT_TXT_PATH, "r", encoding="utf-8", errors="replace") as f:
        txt_content = f.read()
    print(f"  Parsed text: {len(txt_content):,} characters")

    assert len(txt_content) >= MIN_EXHIBIT_TEXT_CHARS, (
        f"Parsed text is only {len(txt_content):,} chars; "
        f"expected >= {MIN_EXHIBIT_TEXT_CHARS:,}."
    )

    print()
    print("PASS: filing exhibit discovery and download completed successfully.")
    print(f"  Exhibit HTML : {EXHIBIT_HTML_PATH} ({html_size:,} bytes)")
    print(f"  Exhibit text : {EXHIBIT_TXT_PATH} ({len(txt_content):,} chars)")


if __name__ == "__main__":
    main()
