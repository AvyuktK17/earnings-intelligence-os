"""Narrowly scoped cleanup for legacy ungrounded pending proposed claims.

Targets ONLY rows where source_chunk_id is null AND review_status is
"pending" — drafts from the pre-grounding extractor that can never be
approved or promoted. Grounded rows and reviewed rows (approved, edited,
rejected) are never touched, and trusted qualitative_claims are never read
or written.

Default mode is a dry run that prints the matching rows and exits.
Deletion requires the explicit --confirm flag:

    python cleanup_legacy_claims.py            # dry run (always safe)
    python cleanup_legacy_claims.py --confirm  # actually delete

Never run automatically by tests, deployment, or GitHub Actions.
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client


def find_legacy_rows() -> list[dict]:
    """Return ungrounded pending proposed_claims rows, oldest first."""
    supabase = get_supabase_client()
    return (
        supabase.table("proposed_claims")
        .select(
            "id, ticker, accession_number, document_key, theme, "
            "review_status, source_chunk_id, created_at"
        )
        .is_("source_chunk_id", "null")
        .eq("review_status", "pending")
        .order("id", desc=False)
        .execute()
        .data
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Delete legacy ungrounded pending proposed claims "
            "(dry run unless --confirm)."
        )
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually delete the listed rows. Without it, dry run only.",
    )
    args = parser.parse_args()

    rows = find_legacy_rows()

    if not rows:
        print("No legacy ungrounded pending claims found. Nothing to do.")
        return

    print(f"Found {len(rows)} legacy ungrounded pending claim(s):\n")
    for row in rows:
        print(
            f"  id={row['id']}  {row['ticker']}  {row['accession_number']}  "
            f"{row['document_key']}  status={row['review_status']}  "
            f"source_chunk_id={row['source_chunk_id']}"
        )
        print(f"    theme: {row['theme']}")
    print()

    if not args.confirm:
        print(
            "Dry run — nothing deleted. Rerun with --confirm to delete "
            "these rows."
        )
        return

    supabase = get_supabase_client()
    deleted = 0
    for row in rows:
        # Delete strictly by id with the safety predicates repeated, so a
        # row reviewed between listing and deletion is left alone.
        response = (
            supabase.table("proposed_claims")
            .delete()
            .eq("id", row["id"])
            .is_("source_chunk_id", "null")
            .eq("review_status", "pending")
            .execute()
        )
        deleted += len(response.data)

    print(f"Deleted {deleted} legacy ungrounded pending claim(s).")


if __name__ == "__main__":
    main()
