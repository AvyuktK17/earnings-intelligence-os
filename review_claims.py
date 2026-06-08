"""Interactive terminal review queue for grounded pending claims.

Presents each grounded pending claim one at a time and asks the analyst
to choose an action. Ungrounded legacy rows (source_chunk_id IS NULL)
are excluded automatically and are never modified here.

Actions:
  [A]pprove           -- accept the claim as written
  [E]dit and approve  -- correct the wording, then approve
  [R]eject            -- discard the claim
  [S]kip              -- leave unchanged and move to next claim
  [Q]uit              -- exit without changing remaining claims

Does not call Gemini. Does not modify qualitative_claims.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.claim_review import approve_claim, approve_claim_with_edits, reject_claim


def _divider() -> None:
    print("\n" + "=" * 72)


def _ask(prompt: str) -> str:
    """Read a line from stdin, returning '' on EOF (e.g. when input is piped)."""
    try:
        return input(prompt)
    except EOFError:
        return ""


def _prompt_notes(label: str = "Reviewer notes") -> str | None:
    raw = _ask(f"{label} (press Enter to skip): ").strip()
    return raw if raw else None


def _count_remaining(supabase) -> int:
    return len(
        supabase.table("proposed_claims")
        .select("id")
        .eq("review_status", "pending")
        .not_.is_("source_chunk_id", "null")
        .execute()
        .data
    )


def _print_summary(approved: int, edited: int, rejected: int, skipped: int, supabase) -> None:
    remaining = _count_remaining(supabase)
    print()
    print("=" * 72)
    print("Review session complete.")
    print(f"  Approved : {approved}")
    print(f"  Edited   : {edited}")
    print(f"  Rejected : {rejected}")
    print(f"  Skipped  : {skipped}")
    print(f"  Remaining grounded pending: {remaining}")


def main() -> None:
    supabase = get_supabase_client()

    claims = (
        supabase.table("proposed_claims")
        .select(
            "id, ticker, accession_number, document_key, theme, claim_text, "
            "supporting_excerpt, source_chunk_id, source_chunk_index, "
            "claim_type, confidence, created_at"
        )
        .eq("review_status", "pending")
        .not_.is_("source_chunk_id", "null")
        .order("created_at", desc=False)
        .order("id", desc=False)
        .execute()
        .data
    )

    if not claims:
        print("No grounded pending claims are available for review.")
        return

    total = len(claims)
    approved = edited = rejected = skipped = 0

    for pos, claim in enumerate(claims, 1):
        _divider()
        print(f"Claim {pos} of {total}")
        print(f"  id                : {claim['id']}")
        print(f"  ticker            : {claim['ticker']}")
        print(f"  accession_number  : {claim['accession_number']}")
        print(f"  document_key      : {claim['document_key']}")
        print(f"  theme             : {claim['theme']}")
        print(f"  claim_text        : {claim['claim_text']}")
        print(f"  supporting_excerpt: {claim['supporting_excerpt']}")
        print(f"  source_chunk_id   : {claim['source_chunk_id']}")
        print(f"  source_chunk_index: {claim['source_chunk_index']}")
        print(f"  claim_type        : {claim['claim_type']}")
        print(f"  confidence        : {claim['confidence']}")

        while True:
            print()
            choice = _ask(
                "[A]pprove  [E]dit and approve  [R]eject  [S]kip  [Q]uit: "
            ).strip().upper()

            if choice == "A":
                notes = _prompt_notes()
                approve_claim(claim["id"], reviewer_notes=notes)
                print(f"  -> Approved claim {claim['id']}.")
                approved += 1
                break

            elif choice == "E":
                new_text = ""
                while not new_text:
                    new_text = _ask("Enter edited claim text: ").strip()
                    if not new_text:
                        print("  Edited text cannot be empty. Please try again.")
                notes = _prompt_notes()
                approve_claim_with_edits(claim["id"], new_text, reviewer_notes=notes)
                print(f"  -> Approved with edits, claim {claim['id']}.")
                edited += 1
                break

            elif choice == "R":
                notes = _prompt_notes("Reason for rejection")
                reject_claim(claim["id"], reviewer_notes=notes)
                print(f"  -> Rejected claim {claim['id']}.")
                rejected += 1
                break

            elif choice == "S":
                print(f"  -> Skipped claim {claim['id']}.")
                skipped += 1
                break

            elif choice == "Q":
                print("  -> Quitting review session.")
                _print_summary(approved, edited, rejected, skipped, supabase)
                return

            else:
                print(
                    f"  Invalid input {choice!r}. "
                    "Please enter A, E, R, S, or Q."
                )

    _print_summary(approved, edited, rejected, skipped, supabase)


if __name__ == "__main__":
    main()
