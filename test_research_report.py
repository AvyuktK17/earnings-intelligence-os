"""Tests for the deterministic research-report engine (no writes).

Verifies the report is deterministic, uses only trusted promoted claims and
deterministic metrics, labels valuation data as a dated snapshot, and never
fabricates forecasts, DCF values, price targets, or ratings. Generation is
read-only here — storage/versioning is covered by test_api_reports.py.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.research_report import generate_research_report

REQUIRED_SECTIONS = [
    "## Executive Summary",
    "## Reported Financial Snapshot",
    "## Historical Operating Trends",
    "## Peer Comparison",
    "## Balance Sheet and Cash Flow",
    "## Valuation Snapshot",
    "## Reviewed Evidence-Linked Takeaways",
    "## Catalysts",
    "## Risks and Watch Items",
    "## Source Appendix",
    "## Methodology and Limitations",
]

# Patterns that would indicate fabricated sell-side outputs being *produced*
# (as opposed to disclaimed). None of these may appear.
FORBIDDEN_PATTERNS = [
    r"implied share price",
    r"price target of \$",
    r"target price of \$",
    r"\btarget price[:=]\s*\$",
    r"\bwe rate\b",
    r"\b(buy|sell|hold|overweight|underweight|outperform) rating\b",
    r"\bdiscount rate\b",
    r"\bterminal (value|fcf)\b",
    r"12-month target",
]


def main() -> None:
    report = generate_research_report("AVGO")

    # Determinism: regenerating yields identical markdown (timestamps aside).
    again = generate_research_report("AVGO")
    md1 = re.sub(r"\*\*Report date:\*\* \d{4}-\d{2}-\d{2}", "", report["markdown"])
    md2 = re.sub(r"\*\*Report date:\*\* \d{4}-\d{2}-\d{2}", "", again["markdown"])
    assert md1 == md2, "report content is not deterministic"
    print("Determinism: identical content across two runs.")

    md = report["markdown"]
    for section in REQUIRED_SECTIONS:
        assert section in md, f"missing section: {section}"
    print(f"Structure: all {len(REQUIRED_SECTIONS)} required sections present.")

    # Only trusted claims: one evidence link per claim used; ids are promoted.
    assert report["source_claim_count"] == len(report["evidence_links"])
    assert report["source_claim_count"] > 0, "expected trusted claims for AVGO"
    for link in report["evidence_links"]:
        assert link["qualitative_claim_id"] is not None
        assert link["source_chunk_id"] is not None
        assert link["section_name"] in ("reviewed_takeaways", "catalysts", "risks")
    print(f"Evidence: {report['source_claim_count']} trusted claims, all grounded.")

    # Valuation is a dated snapshot, clearly disclaimed — never live.
    assert report["valuation_snapshot_date"], "snapshot date must be present"
    assert "not a live market feed" in md
    assert report["valuation_snapshot_date"] in md
    print(f"Valuation: dated snapshot {report['valuation_snapshot_date']}, disclaimed.")

    # No fabricated forecasts / DCF / target price / rating produced.
    low = md.lower()
    for pattern in FORBIDDEN_PATTERNS:
        assert not re.search(pattern, low), f"forbidden content present: {pattern!r}"
    # The methodology must explicitly disclaim these.
    assert "no forward estimates" in low
    assert "price targets" in low and "ratings" in low  # only in disclaimers
    print("Safety: no DCF, target price, rating, or forecast values produced.")

    # HTML is generated alongside markdown for the PDF / html_content column.
    assert report["html"].startswith("<!DOCTYPE html>")
    assert report["source_metric_count"] > 0
    print(f"Render: HTML present ({len(report['html'])} chars), "
          f"{report['source_metric_count']} metrics.")

    # Explicit accession selection is honored.
    pinned = generate_research_report("AVGO", report["accession_number"])
    assert pinned["accession_number"] == report["accession_number"]
    print(f"Anchor: explicit accession {report['accession_number']} honored.")

    print("\nPASS: deterministic report uses only trusted, dated, non-fabricated data.")


if __name__ == "__main__":
    main()
