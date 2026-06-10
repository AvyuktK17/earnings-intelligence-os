"""Export a deterministic equity-research report packet for one filing.

A report packet bundles every trusted, human-reviewed claim and every audited
deterministic figure for a company filing into a single Markdown file (plus a
machine-readable JSON sibling). It is the input you hand to the
``/semiconductor-equity-research-report`` Claude Code skill so Claude can draft
an analyst narrative grounded *only* in vetted facts.

No AI is called, no database rows are written, and no secrets are printed.

Examples:

    # Most recent filing with trusted claims for AVGO
    python export_report_packet.py --ticker AVGO

    # A specific filing
    python export_report_packet.py --ticker AVGO --accession-number 0001730168-26-000051

    # Custom output directory
    python export_report_packet.py --ticker AVGO --output-dir /tmp/packets

After exporting, open the printed Markdown path and invoke the skill:

    /semiconductor-equity-research-report

then provide the Markdown packet path when prompted.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.report_packet import export_report_packet


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a deterministic report packet (Markdown + JSON).",
    )
    parser.add_argument(
        "--ticker",
        required=True,
        help="Company ticker, e.g. AVGO (case-insensitive).",
    )
    parser.add_argument(
        "--accession-number",
        default=None,
        help=(
            "Specific filing accession number. Omit to use the most recent "
            "filing that has trusted claims."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="output/report_packets",
        help="Directory for the packet files (default: output/report_packets).",
    )
    args = parser.parse_args()

    try:
        result = export_report_packet(
            ticker=args.ticker,
            accession_number=args.accession_number,
            output_dir=args.output_dir,
        )
    except ValueError as exc:
        # Friendly, non-sensitive error for beginners (bad ticker / accession).
        print(f"Could not export packet: {exc}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Exported report packet for {result['ticker']} "
        f"({result['accession_number']}).\n"
        f"  trusted_claims={result['trusted_claim_count']} "
        f"metrics={result['metric_count']} "
        f"evidence_links={result['evidence_link_count']} "
        f"valuation_snapshot_date={result['valuation_snapshot_date']}\n"
        f"  markdown: {result['markdown_path']}\n"
        f"  json:     {result['json_path']}\n"
        f"\nNext: run /semiconductor-equity-research-report and provide the "
        f"markdown path above."
    )


if __name__ == "__main__":
    main()
