"""Import a locally generated Claude-assisted narrative draft as a review record.

Workflow (all manual and local — no Claude API is ever called):

    1. python export_report_packet.py --ticker AVGO --accession-number ...
    2. In Claude Code: /semiconductor-equity-research-report  (drafts a local .md)
    3. python import_claude_narrative.py ... --confirm   (imports the draft)
    4. Review it in the dashboard's Narrative Review page (approve/edit/reject).

This script is a **dry run by default**: it validates the draft and prints what
would be imported without writing anything. Pass ``--confirm`` to insert the
draft into ``research_reports`` as a private ``draft`` row. It never publishes,
never mutates trusted claims, and never prints secrets.

Example:

    python import_claude_narrative.py \\
      --ticker AVGO \\
      --accession-number 0001730168-26-000051 \\
      --markdown-path output/narratives/avgo_0001730168_26_000051_claude_draft.md \\
      --packet-path output/report_packets/avgo_0001730168_26_000051_packet.md \\
      --source-report-id 1 \\
      --confirm
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.claude_narrative_import import (
    _sha256_file,
    import_claude_assisted_narrative,
    validate_draft_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import a local Claude-assisted narrative draft (dry run by default).",
    )
    parser.add_argument("--ticker", required=True, help="Company ticker, e.g. AVGO.")
    parser.add_argument(
        "--markdown-path", required=True, help="Path to the narrative Markdown draft."
    )
    parser.add_argument(
        "--accession-number",
        default=None,
        help="Filing accession (default: most recent filing with trusted claims).",
    )
    parser.add_argument(
        "--packet-path",
        default=None,
        help="Optional report-packet path; its SHA-256 is recorded for provenance.",
    )
    parser.add_argument(
        "--source-report-id",
        type=int,
        default=None,
        help="Optional deterministic source report id whose evidence links are reused.",
    )
    parser.add_argument(
        "--report-type", default="earnings_update", help="Report type."
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually write the draft. Without this flag the script only validates.",
    )
    args = parser.parse_args()

    if not os.path.exists(args.markdown_path):
        print(f"Markdown file not found: {args.markdown_path}", file=sys.stderr)
        sys.exit(1)

    if not args.confirm:
        # Dry run: validate the draft and report what would happen; write nothing.
        try:
            content = open(args.markdown_path, encoding="utf-8").read()
            validate_draft_markdown(content)
        except ValueError as exc:
            print(f"[dry run] Draft would be REJECTED: {exc}", file=sys.stderr)
            sys.exit(1)
        packet_hash = (
            _sha256_file(args.packet_path)
            if args.packet_path and os.path.exists(args.packet_path)
            else None
        )
        print(
            "[dry run] Draft is valid and would be imported as a private draft.\n"
            f"  ticker={args.ticker.upper()} "
            f"accession={args.accession_number or '(auto-select latest)'} "
            f"report_type={args.report_type}\n"
            f"  markdown={args.markdown_path} ({len(content)} chars)\n"
            f"  source_report_id={args.source_report_id} "
            f"source_packet_hash={packet_hash}\n"
            "  Nothing was written. Re-run with --confirm to import."
        )
        return

    try:
        result = import_claude_assisted_narrative(
            ticker=args.ticker,
            markdown_path=args.markdown_path,
            accession_number=args.accession_number,
            source_report_id=args.source_report_id,
            source_packet_path=args.packet_path,
            report_type=args.report_type,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Imported Claude-assisted draft (report_id={result['report_id']}, "
        f"v{result['version_number']}, status={result['report_status']}).\n"
        f"  ticker={result['ticker']} accession={result['accession_number']} "
        f"report_type={result['report_type']}\n"
        f"  source_report_id={result['source_report_id']} "
        f"source_packet_hash={result['source_packet_hash']}\n"
        f"  source_claim_count={result['source_claim_count']} "
        f"evidence_links={result['evidence_link_count']}\n"
        "  This draft is PRIVATE until approved in the Narrative Review page."
    )


if __name__ == "__main__":
    main()
