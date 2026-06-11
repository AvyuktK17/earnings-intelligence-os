"""Narrowly scoped cleanup for cosmetic defects in the companies table.

Fixes exactly two classes of issue, both visible in the public API:

1. Leading/trailing whitespace in text fields (e.g. NVDA's business_model
   is stored as "Fabless\n", which renders oddly in the dashboard).
2. AMD's company_name stored as the bare ticker "AMD" instead of the
   full legal name "Advanced Micro Devices".

No other table is read or written; trusted claims, filings, metrics, and
reports are never touched. Idempotent — a rerun after a confirmed run
finds nothing to do.

Default mode is a dry run that prints the planned updates and exits.
Writing requires the explicit --confirm flag:

    python fix_company_records.py            # dry run (always safe)
    python fix_company_records.py --confirm  # actually update

Never run automatically by tests, deployment, or GitHub Actions.
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client

TEXT_FIELDS = ("company_name", "business_model", "cik")

FULL_NAMES = {
    "AMD": "Advanced Micro Devices",
}


def plan_fixes(rows: list[dict]) -> list[dict]:
    """Return one {ticker, updates} entry per row needing changes."""
    fixes = []
    for row in rows:
        updates: dict[str, str] = {}

        for field in TEXT_FIELDS:
            value = row.get(field)
            if isinstance(value, str) and value != value.strip():
                updates[field] = value.strip()

        full_name = FULL_NAMES.get(row["ticker"])
        if full_name:
            current = updates.get("company_name", row.get("company_name") or "")
            if current.strip() == row["ticker"]:
                updates["company_name"] = full_name

        if updates:
            fixes.append({"ticker": row["ticker"], "updates": updates})
    return fixes


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fix whitespace and naming defects in the companies table "
            "(dry run unless --confirm)."
        )
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually apply the listed updates. Without it, dry run only.",
    )
    args = parser.parse_args()

    supabase = get_supabase_client()
    rows = (
        supabase.table("companies")
        .select("ticker, company_name, business_model, cik")
        .order("ticker", desc=False)
        .execute()
        .data
    )

    fixes = plan_fixes(rows)

    if not fixes:
        print("All company records are clean. Nothing to do.")
        return

    print(f"Planned update(s) for {len(fixes)} company record(s):\n")
    for fix in fixes:
        print(f"  {fix['ticker']}:")
        for field, new_value in fix["updates"].items():
            old_value = next(
                r[field] for r in rows if r["ticker"] == fix["ticker"]
            )
            print(f"    {field}: {old_value!r} -> {new_value!r}")
    print()

    if not args.confirm:
        print(
            "Dry run — nothing updated. Rerun with --confirm to apply "
            "these updates."
        )
        return

    updated = 0
    for fix in fixes:
        response = (
            supabase.table("companies")
            .update(fix["updates"])
            .eq("ticker", fix["ticker"])
            .execute()
        )
        updated += len(response.data)

    print(f"Updated {updated} company record(s).")


if __name__ == "__main__":
    main()
