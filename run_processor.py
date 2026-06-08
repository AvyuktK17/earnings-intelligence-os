import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.process_detected_filings import process_detected_filings


def main():
    print("Processing one detected filing...\n")
    results = process_detected_filings(limit=1)

    if not results:
        print("No filings with status 'detected' were found.")
        return

    for r in results:
        print(f"  Ticker           : {r['ticker']}")
        print(f"  Accession number : {r['accession_number']}")
        print(f"  Status           : {r['status']}")

        if r["status"] == "parsed":
            print(f"  HTML path        : {r['html_path']}")
            print(f"  Text path        : {r['text_path']}")
            print(f"  HTML size        : {r['html_size_bytes']:,} bytes")
            print(f"  Text size        : {r['text_size_bytes']:,} bytes")
        elif r["status"] == "failed":
            print(f"  Error            : {r['error_message']}")


if __name__ == "__main__":
    main()
