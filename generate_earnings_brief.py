"""Generate the AVGO earnings intelligence brief from promoted trusted claims.

Uses only human-reviewed, grounded claims already in qualitative_claims.
Does not call Gemini. Does not modify any database rows.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.earnings_brief import generate_earnings_brief

TICKER = "AVGO"
ACCESSION_NUMBER = "0001730168-26-000051"
OUTPUT_PATH = "output/briefs/avgo_0001730168_26_000051.md"


def main() -> None:
    print(f"Generating earnings brief for {TICKER} / {ACCESSION_NUMBER}...")
    print()

    result = generate_earnings_brief(
        ticker=TICKER,
        accession_number=ACCESSION_NUMBER,
        output_path=OUTPUT_PATH,
    )

    print(f"Ticker                  : {result['ticker']}")
    print(f"Accession number        : {result['accession_number']}")
    print(f"Trusted claim count     : {result['trusted_claim_count']}")
    print(f"  Factual               : {result['factual_claim_count']}")
    print(f"  Interpretive          : {result['interpretive_claim_count']}")
    print(f"Saved to                : {result['output_path']}")


if __name__ == "__main__":
    main()
