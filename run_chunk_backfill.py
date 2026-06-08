import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.backfill_missing_chunks import backfill_missing_chunks

BATCH_SIZE = 3


def main():
    print(f"Backfilling chunks for up to {BATCH_SIZE} parsed filings...\n")
    results = backfill_missing_chunks(limit=BATCH_SIZE)

    if not results:
        print("No parsed filings with missing chunks were found. Nothing to do.")
        return

    col = "{:<6} {:<28} {:<10} {:>12} {:>22}"
    header = col.format("Ticker", "Accession Number", "Status", "Chunks", "Avg Chunk (chars)")
    print(header)
    print("-" * len(header))

    for r in results:
        if r["status"] == "chunked":
            print(col.format(
                r["ticker"],
                r["accession_number"],
                r["status"],
                r["chunk_count"],
                r["average_chunk_characters"],
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

    chunked_count = sum(1 for r in results if r["status"] == "chunked")
    failed_count = sum(1 for r in results if r["status"] == "failed")

    print()
    print(f"Selected  : {len(results)}")
    print(f"Chunked   : {chunked_count}")
    print(f"Failed    : {failed_count}")


if __name__ == "__main__":
    main()
