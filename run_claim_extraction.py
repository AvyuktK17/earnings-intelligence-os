"""Manual entry point for document-specific Gemini claim extraction.

Usage:
    python run_claim_extraction.py
    python run_claim_extraction.py --accession-number 0001730168-26-000051 \\
                                   --document-key exhibit:avgo-05032026x8kxex99.htm \\
                                   --max-claims 5

Gemini is called only when this script runs. No AI calls happen automatically.
Claims are stored with review_status="pending" and must be reviewed manually.
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.claim_extractor import extract_and_store_claims

DEFAULT_ACCESSION = "0001730168-26-000051"
DEFAULT_DOCUMENT_KEY = "exhibit:avgo-05032026x8kxex99.htm"
DEFAULT_MAX_CLAIMS = 5


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract grounded claims from a chunked filing document using Gemini."
    )
    parser.add_argument(
        "--accession-number",
        default=DEFAULT_ACCESSION,
        help=f"SEC accession number (default: {DEFAULT_ACCESSION})",
    )
    parser.add_argument(
        "--document-key",
        default=DEFAULT_DOCUMENT_KEY,
        help=f"Document key within the filing (default: {DEFAULT_DOCUMENT_KEY})",
    )
    parser.add_argument(
        "--max-claims",
        type=int,
        default=DEFAULT_MAX_CLAIMS,
        help=f"Maximum number of claims to request from Gemini (default: {DEFAULT_MAX_CLAIMS})",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    print("Extracting claims from filing document...")
    print(f"  Accession number : {args.accession_number}")
    print(f"  Document key     : {args.document_key}")
    print(f"  Max claims       : {args.max_claims}")
    print()

    try:
        result = extract_and_store_claims(
            accession_number=args.accession_number,
            max_claims=args.max_claims,
            document_key=args.document_key,
        )
    except Exception as exc:
        exc_str = str(exc)
        # Detect quota / rate-limit / availability errors from the Gemini API.
        # These arrive as google.genai.errors.ClientError (429) or ServerError (503).
        # We check the message text because importing the SDK error classes here
        # would add a hard dependency on google-genai to this entry point.
        if any(
            marker in exc_str
            for marker in (
                "429",
                "RESOURCE_EXHAUSTED",
                "quota",
                "rate",
                "503",
                "UNAVAILABLE",
                "high demand",
            )
        ):
            print("Gemini API quota or rate limit reached.")
            print(
                "The free-tier quota may need time to reset "
                "(typically 24 hours for daily limits)."
            )
            print("No existing pending claims were deleted.")
            print("Try again later with: python run_claim_extraction.py")
            sys.exit(0)

        # All other errors (missing filing, no chunks, all claims invalid, etc.)
        print(f"Extraction failed: {exc}")
        sys.exit(1)

    # Print summary
    print(f"Ticker            : {result['ticker']}")
    print(f"Accession number  : {result['accession_number']}")
    print(f"Document key      : {result['document_key']}")
    print(f"Claims saved      : {result['proposed_claim_count']}")
    print(f"Invalid skipped   : {result['skipped_invalid_count']}")
    print()

    # Fetch the stored rows from the DB so we can show source_chunk_id.
    supabase = get_supabase_client()
    stored = (
        supabase.table("proposed_claims")
        .select(
            "theme, claim_text, supporting_excerpt, source_chunk_id, "
            "source_chunk_index, claim_type, confidence, review_status"
        )
        .eq("accession_number", args.accession_number)
        .eq("document_key", args.document_key)
        .eq("review_status", "pending")
        .order("source_chunk_index", desc=False)
        .execute()
        .data
    )

    for i, row in enumerate(stored, 1):
        print(f"Claim {i}:")
        print(f"  theme             : {row['theme']}")
        print(f"  claim_text        : {row['claim_text']}")
        print(f"  supporting_excerpt: {row['supporting_excerpt']}")
        print(f"  source_chunk_id   : {row['source_chunk_id']}")
        print(f"  source_chunk_index: {row['source_chunk_index']}")
        print(f"  claim_type        : {row['claim_type']}")
        print(f"  confidence        : {row['confidence']}")
        print(f"  review_status     : {row['review_status']}")
        print()

    print("Run python review_claims.py to review the grounded pending claims.")


if __name__ == "__main__":
    main()
