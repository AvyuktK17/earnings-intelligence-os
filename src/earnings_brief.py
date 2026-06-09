"""Generate an evidence-linked earnings brief from trusted qualitative_claims.

Only human-reviewed, grounded claims (proposed_claim_id and source_chunk_id
both non-null) that reference the selected accession number are included.
Pending and rejected AI drafts are never used. No AI calls are made.
"""

from datetime import datetime, timezone
from pathlib import Path

from src.database import get_supabase_client


def generate_earnings_brief(
    ticker: str,
    accession_number: str,
    output_path: str,
) -> dict:
    """Generate a markdown earnings brief from trusted promoted claims.

    Args:
        ticker: Company ticker symbol (e.g. "AVGO").
        accession_number: SEC accession number (e.g. "0001730168-26-000051").
        output_path: Local file path where the markdown will be saved.

    Returns:
        A dict with ticker, accession_number, output_path, trusted_claim_count,
        factual_claim_count, and interpretive_claim_count.

    Raises:
        ValueError: If the filing is not found or no trusted grounded claims exist.
    """
    supabase = get_supabase_client()

    # 1. Fetch the filing row for metadata.
    filing_resp = (
        supabase.table("filings")
        .select("ticker, form, filing_date, report_date, accession_number")
        .eq("accession_number", accession_number)
        .execute()
    )
    if not filing_resp.data:
        raise ValueError(f"No filing found with accession_number={accession_number!r}.")
    filing = filing_resp.data[0]

    # 2. Fetch trusted grounded claims for this ticker + accession number.
    claims = (
        supabase.table("qualitative_claims")
        .select("*")
        .eq("ticker", ticker)
        .not_.is_("proposed_claim_id", "null")
        .not_.is_("source_chunk_id", "null")
        .like("source_reference", f"%{accession_number}%")
        .execute()
        .data
    )

    if not claims:
        raise ValueError(
            f"No trusted grounded claims found for ticker={ticker!r} "
            f"and accession_number={accession_number!r}. "
            "Promote reviewed claims first with: python promote_claims.py"
        )

    factual_count = sum(1 for c in claims if c.get("factual_or_interpretive") == "factual")
    interpretive_count = sum(1 for c in claims if c.get("factual_or_interpretive") == "interpretive")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 3. Build the markdown brief.
    lines = [
        f"# {ticker} Earnings Intelligence Brief",
        "",
        f"**Filing accession number:** {filing['accession_number']}",
        f"**Filing form:** {filing['form']}",
        f"**Filing date:** {filing['filing_date']}",
        f"**Report date:** {filing['report_date']}",
        f"**Generated at:** {generated_at}",
        "",
        "*This brief contains only human-reviewed claims linked to SEC filing evidence.*",
        "",
        "---",
        "",
        "## Reviewed Takeaways",
        "",
    ]

    for i, claim in enumerate(claims, 1):
        trusted_text = claim.get("claim", "")
        lines += [
            f"### {i}. {claim.get('theme', 'Untitled')}",
            "",
            f"**Claim:** {trusted_text}",
            "",
            f"**Confidence:** {claim.get('confidence', '')} "
            f"| **Type:** {claim.get('factual_or_interpretive', '')}",
            "",
            "**Supporting excerpt:**",
            f"> {claim.get('supporting_excerpt', '')}",
            "",
            f"**Source reference:** {claim.get('source_reference', '')}",
            f"**Source chunk id:** {claim.get('source_chunk_id', '')}",
            f"**Document key:** {claim.get('document_key', '')}",
            "",
        ]

    lines += [
        "---",
        "",
        "## Audit Summary",
        "",
        f"- Total trusted grounded claims used: {len(claims)}",
        f"- Factual claims: {factual_count}",
        f"- Interpretive claims: {interpretive_count}",
        "- Pending and rejected AI drafts were excluded from this brief.",
        "",
    ]

    markdown = "\n".join(lines)

    # 4. Save the file, creating parent directories if needed.
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")

    return {
        "ticker": ticker,
        "accession_number": accession_number,
        "output_path": str(out),
        "trusted_claim_count": len(claims),
        "factual_claim_count": factual_count,
        "interpretive_claim_count": interpretive_count,
    }
