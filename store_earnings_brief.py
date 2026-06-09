"""Manual entry point: generate, upload, and store a versioned AVGO earnings brief.

Creates the next version for the accession number, saves the markdown locally,
uploads to private Supabase Storage, and records the row in earnings_briefs.
Does not call Gemini. Does not modify trusted claims.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.brief_storage import generate_and_store_earnings_brief

TICKER = "AVGO"
ACCESSION_NUMBER = "0001730168-26-000051"


def main() -> None:
    print(f"Generating and storing earnings brief for {TICKER} / {ACCESSION_NUMBER}...")
    print()

    result = generate_and_store_earnings_brief(
        ticker=TICKER,
        accession_number=ACCESSION_NUMBER,
    )

    print(f"Ticker                  : {result['ticker']}")
    print(f"Accession number        : {result['accession_number']}")
    print(f"Version number          : {result['version_number']}")
    print(f"Trusted claim count     : {result['trusted_claim_count']}")
    print(f"  Factual               : {result['factual_claim_count']}")
    print(f"  Interpretive          : {result['interpretive_claim_count']}")
    print(f"Local output path       : {result['local_output_path']}")
    print(f"Storage path            : {result['storage_path']}")


if __name__ == "__main__":
    main()
