"""Backfill audited static-dashboard data into Supabase (dry run by default).

Parses the locally downloaded copy of the original public semiconductor
research dashboard and backfills only what is missing:

* AVGO rows into the existing financial_metrics table (operating metrics only;
  reviewed rows for the other tickers are never overwritten);
* the five manually reviewed valuation snapshots into valuation_snapshots.

The HTML file is read from a local path and is never committed. Download it
first, e.g.:

    curl -sL https://avyuktk17.github.io/semiconductor-research/ \
        -o /tmp/semiconductor_dashboard.html

Then:

    python run_static_dashboard_backfill.py             # dry run (safe)
    python run_static_dashboard_backfill.py --confirm   # write missing rows

Reruns are idempotent. No AI calls are made and no credentials are printed.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.database import get_supabase_client
from src.static_dashboard_backfill import run_backfill

DEFAULT_SOURCE = "/tmp/semiconductor_dashboard.html"


def _print_summary(summary: dict) -> None:
    mode = "CONFIRMED WRITE" if summary["confirmed"] else "DRY RUN"
    print(f"\n=== Static dashboard backfill — {mode} ===\n")
    for table, label in (
        ("metrics", "financial_metrics (AVGO operating rows)"),
        ("valuations", "valuation_snapshots (all tickers)"),
    ):
        section = summary[table]
        print(f"{label}:")
        print(f"  candidates: {section['candidates']}")
        if summary["confirmed"]:
            print(f"  inserted:   {section['inserted']}")
        else:
            print(f"  to insert:  {section['to_insert']}")
        print(f"  skipped:    {section['skipped']} (already present)")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill audited AVGO metrics and valuation snapshots "
            "(dry run unless --confirm)."
        )
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help=f"Path to the downloaded dashboard HTML (default: {DEFAULT_SOURCE}).",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Write the missing rows. Without it, dry run only.",
    )
    args = parser.parse_args()

    if not os.path.exists(args.source):
        print(
            f"Source HTML not found at {args.source!r}. Download it first, e.g.:\n"
            "  curl -sL https://avyuktk17.github.io/semiconductor-research/ "
            f"-o {DEFAULT_SOURCE}"
        )
        sys.exit(1)

    with open(args.source, encoding="utf-8") as handle:
        html = handle.read()

    supabase = get_supabase_client()
    summary = run_backfill(supabase, html, confirm=args.confirm)
    _print_summary(summary)

    if not summary["confirmed"]:
        print("Dry run — nothing written. Rerun with --confirm to apply.")


if __name__ == "__main__":
    main()
