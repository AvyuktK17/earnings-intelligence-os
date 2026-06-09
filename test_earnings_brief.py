"""Test the earnings brief generator for AVGO 0001730168-26-000051.

Verifies that only the 5 trusted promoted claims appear, that the markdown
contains excerpts and source chunk ids, that the audit summary is present,
and that legacy ungrounded primary-document claims are absent.
Does not call Gemini. Does not modify any database rows.
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from src.earnings_brief import generate_earnings_brief
from src.database import get_supabase_client

TICKER = "AVGO"
ACCESSION = "0001730168-26-000051"
OUTPUT_PATH = "output/briefs/avgo_0001730168_26_000051.md"

# Text fragments from the two legacy ungrounded primary-document claims
# (pending, source_chunk_id=None) that must NOT appear in the brief.
LEGACY_FRAGMENTS = [
    "Broadcom Inc. announced its unaudited financial results",
    "The declared quarterly cash dividend is payable on June 30",
]


def main() -> None:
    supabase = get_supabase_client()

    # Fetch the 5 trusted promoted claims so we can check their text.
    trusted = (
        supabase.table("qualitative_claims")
        .select("claim, supporting_excerpt, source_chunk_id")
        .eq("ticker", TICKER)
        .not_.is_("proposed_claim_id", "null")
        .not_.is_("source_chunk_id", "null")
        .like("source_reference", f"%{ACCESSION}%")
        .execute()
        .data
    )
    assert len(trusted) == 5, (
        f"Expected 5 trusted grounded AVGO claims but found {len(trusted)}. "
        "Run promote_claims.py first."
    )

    print(f"Running generate_earnings_brief for {TICKER} / {ACCESSION}...")
    result = generate_earnings_brief(
        ticker=TICKER,
        accession_number=ACCESSION,
        output_path=OUTPUT_PATH,
    )

    # 1. Output file must exist.
    out_path = Path(result["output_path"])
    assert out_path.exists(), f"Output file not found: {out_path}"
    markdown = out_path.read_text(encoding="utf-8")

    # 2. Claim count.
    assert result["trusted_claim_count"] == 5, (
        f"Expected trusted_claim_count=5 but got {result['trusted_claim_count']}."
    )
    print(f"  [OK] trusted_claim_count = {result['trusted_claim_count']}")

    # 3. All 5 trusted claim texts must appear in the markdown.
    for row in trusted:
        claim_text = row["claim"]
        assert claim_text in markdown, (
            f"Claim text missing from brief: {claim_text[:60]!r}"
        )
    print("  [OK] all 5 trusted claim texts present in markdown")

    # 4. Supporting excerpts must appear.
    for row in trusted:
        excerpt = row["supporting_excerpt"]
        assert excerpt in markdown, (
            f"Supporting excerpt missing from brief: {excerpt[:60]!r}"
        )
    print("  [OK] all supporting excerpts present in markdown")

    # 5. Source chunk ids must appear.
    for row in trusted:
        chunk_id_str = str(row["source_chunk_id"])
        assert chunk_id_str in markdown, (
            f"Source chunk id {chunk_id_str} missing from brief."
        )
    print("  [OK] source chunk ids present in markdown")

    # 6. Audit summary section must exist.
    assert "## Audit Summary" in markdown, "Audit Summary section missing."
    assert "Total trusted grounded claims used: 5" in markdown, (
        "Audit summary claim count line missing."
    )
    print("  [OK] audit summary present")

    # 7. The statement about pending/rejected exclusion must appear.
    assert "Pending and rejected AI drafts were excluded" in markdown, (
        "Exclusion statement missing from audit summary."
    )
    print("  [OK] exclusion statement present")

    # 8. Legacy ungrounded primary-document claim fragments must NOT appear.
    for fragment in LEGACY_FRAGMENTS:
        assert fragment not in markdown, (
            f"Legacy ungrounded claim fragment found in brief (must be excluded): "
            f"{fragment[:60]!r}"
        )
    print("  [OK] legacy ungrounded primary-document claims are absent")

    # 9. Print a short preview (first 40 lines).
    print()
    print("--- Brief preview (first 40 lines) ---")
    preview_lines = markdown.splitlines()[:40]
    print("\n".join(preview_lines))
    print("--- end preview ---")

    print()
    print(f"Output saved to: {result['output_path']}")
    print()
    print(
        "PASS: earnings brief generator produces a correct, evidence-linked "
        "brief containing only trusted promoted claims."
    )


if __name__ == "__main__":
    main()
