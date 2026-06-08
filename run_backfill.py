import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.backfill_missing_storage import backfill_missing_storage_paths

BATCH_SIZE = 3


def main():
    print(f"Backfilling Storage paths for up to {BATCH_SIZE} parsed filings...\n")
    results = backfill_missing_storage_paths(limit=BATCH_SIZE)

    if not results:
        print("No parsed filings with missing Storage paths were found. Nothing to repair.")
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

    repaired = sum(1 for r in results if r["status"] == "parsed")
    failed = sum(1 for r in results if r["status"] == "failed")

    print()
    print(f"Selected  : {len(results)}")
    print(f"Repaired  : {repaired}")
    print(f"Failed    : {failed}")


if __name__ == "__main__":
    main()
