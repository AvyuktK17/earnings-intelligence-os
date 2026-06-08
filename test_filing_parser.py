"""
Test the filing parser using the previously downloaded Qualcomm 10-Q HTML.
Extracts plain text into data/parsed_filings/qcom_latest_10q.txt.
Does NOT commit parsed output or modify .env.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.filing_parser import extract_filing_text

HTML_PATH = "data/raw_filings/qcom_latest_10q.html"
OUTPUT_PATH = "data/parsed_filings/qcom_latest_10q.txt"


def main():
    if not os.path.exists(HTML_PATH):
        print(f"ERROR: HTML file not found at {HTML_PATH}")
        print("Please run:  python test_filing_downloader.py")
        sys.exit(1)

    print(f"Parsing: {HTML_PATH}")
    saved_path = extract_filing_text(HTML_PATH, OUTPUT_PATH)

    assert os.path.exists(saved_path), f"Output file not found at {saved_path}."

    with open(saved_path, "r", encoding="utf-8") as f:
        text = f.read()

    char_count = len(text)
    assert char_count > 0, "Extracted text file is empty."
    assert char_count >= 10_000, (
        f"Expected at least 10,000 characters but got {char_count}."
    )
    assert "form 10-q" in text.lower(), (
        "Could not find 'Form 10-Q' in the extracted text."
    )

    print(f"Output path      : {saved_path}")
    print(f"Character count  : {char_count:,}")
    print()
    print("--- Preview (first 500 characters) ---")
    print(text[:500])
    print("--------------------------------------")
    print()
    print("PASS: filing parser is working correctly.")


if __name__ == "__main__":
    main()
