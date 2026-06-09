"""Manual entry point for promoting human-reviewed claims to qualitative_claims.

Run this after reviewing claims with review_claims.py.
Only approved and edited grounded rows are promoted.
Rows already in qualitative_claims are silently skipped.
Does not call Gemini. Does not auto-approve anything.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.claim_promotion import promote_reviewed_claims


def main() -> None:
    print("Promoting reviewed claims to qualitative_claims...")
    print()

    result = promote_reviewed_claims()

    print(f"Eligible reviewed claims : {result['eligible_count']}")
    print(f"Newly promoted           : {result['promoted_count']}")
    print(f"Skipped (already exists) : {result['skipped_existing_count']}")
    print()

    if not result["promoted_claims"]:
        print("No new claims were promoted.")
        print(
            "All eligible reviewed claims may already be in qualitative_claims, "
            "or there are no approved/edited grounded claims yet."
        )
        return

    for i, claim in enumerate(result["promoted_claims"], 1):
        print(f"Promoted claim {i}:")
        print(f"  ticker          : {claim['ticker']}")
        print(f"  theme           : {claim['theme']}")
        print(f"  claim           : {claim['claim']}")
        print(f"  source_chunk_id : {claim['source_chunk_id']}")
        print(f"  document_key    : {claim['document_key']}")
        print()

    print("Run python list_proposed_claims.py to see remaining pending claims.")


if __name__ == "__main__":
    main()
