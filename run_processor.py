import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.process_detected_filings import process_detected_filings

BATCH_SIZE = 3


def main():
    print(f"Processing up to {BATCH_SIZE} detected filings...\n")
    results = process_detected_filings(limit=BATCH_SIZE)

    if not results:
        print("No filings with status 'detected' were found.")
        return

    col = "{:<6} {:<28} {:<8} {:<42} {:<42}"
    header = col.format("Ticker", "Accession Number", "Status", "HTML Storage Path", "Text Storage Path")
    print(header)
    print("-" * len(header))

    for r in results:
        if r["status"] == "parsed":
            print(col.format(
                r["ticker"],
                r["accession_number"],
                r["status"],
                r.get("html_storage_path", ""),
                r.get("text_storage_path", ""),
            ))
        else:
            print(col.format(
                r["ticker"],
                r["accession_number"],
                r["status"],
                "",
                "",
            ))
            print(f"  ERROR: {r.get('error_message', 'unknown error')}")

    parsed_count = sum(1 for r in results if r["status"] == "parsed")
    failed_count = sum(1 for r in results if r["status"] == "failed")

    print()
    print(f"Filings processed : {len(results)}")
    print(f"Parsed            : {parsed_count}")
    print(f"Failed            : {failed_count}")


if __name__ == "__main__":
    main()
