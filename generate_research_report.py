"""Generate and store a deterministic earnings-update research report.

    python generate_research_report.py AVGO
    python generate_research_report.py AVGO --accession 0001730168-26-000051
    python generate_research_report.py AVGO --dry-run   # print markdown, no writes

A dry run renders the report and prints the markdown without uploading to
Storage or inserting any rows. The default run versions and persists the
report (Markdown + HTML + PDF + database rows). No AI is called.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.research_report import generate_research_report
from src.research_report_storage import generate_and_store_research_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a research report.")
    parser.add_argument("ticker", help="Company ticker, e.g. AVGO")
    parser.add_argument(
        "--accession",
        default=None,
        help="Specific filing accession number (default: latest with claims).",
    )
    parser.add_argument(
        "--report-type",
        default="earnings_update",
        help="Report type (default: earnings_update).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render and print markdown only; no Storage or database writes.",
    )
    args = parser.parse_args()

    if args.dry_run:
        report = generate_research_report(
            args.ticker, args.accession, args.report_type
        )
        print(report["markdown"])
        print(
            f"\n[dry run] claims={report['source_claim_count']} "
            f"metrics={report['source_metric_count']} "
            f"evidence_links={len(report['evidence_links'])} — nothing written.",
            file=sys.stderr,
        )
        return

    result = generate_and_store_research_report(
        args.ticker, args.accession, args.report_type
    )
    print(
        f"Stored {result['title']} v{result['version_number']} "
        f"(report_id={result['report_id']}).\n"
        f"  claims={result['source_claim_count']} "
        f"metrics={result['source_metric_count']} "
        f"evidence_links={result['evidence_link_count']}\n"
        f"  pdf={result['pdf_storage_path']}"
    )


if __name__ == "__main__":
    main()
