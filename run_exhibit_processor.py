import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.process_pending_exhibits import process_pending_exhibits

BATCH_SIZE = 3


def main():
    print(
        f"Processing earnings-release exhibits for up to {BATCH_SIZE} "
        "pending 8-K filings...\n"
    )
    results = process_pending_exhibits(limit=BATCH_SIZE)

    if not results:
        print("No chunked 8-K filings are waiting for an exhibit check.")
        return

    for r in results:
        line = f"{r['ticker']:<6} {r['accession_number']:<24} {r['status']}"
        if r["status"] == "processed":
            line += f"  exhibit={r['filename']}  chunks={r['chunk_count']}"
        print(line)
        if r["status"] == "failed":
            print(f"  ERROR: {r.get('error_message', 'unknown error')}")

    processed_count = sum(1 for r in results if r["status"] == "processed")
    not_found_count = sum(1 for r in results if r["status"] == "not_found")
    failed_count = sum(1 for r in results if r["status"] == "failed")

    print()
    print(f"Filings selected : {len(results)}")
    print(f"Processed        : {processed_count}")
    print(f"No exhibit found : {not_found_count}")
    print(f"Failed           : {failed_count}")


if __name__ == "__main__":
    main()
