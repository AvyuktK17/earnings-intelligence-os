"""Generate, upload, and store a versioned earnings brief.

Each call creates the next version number for the given accession number,
writes a local markdown file, uploads it to private Supabase Storage, and
inserts one row into earnings_briefs. Prior versions are never overwritten.
No AI calls are made.
"""

from datetime import datetime, timezone
from pathlib import Path

from src.database import get_supabase_client
from src.earnings_brief import generate_earnings_brief
from src.storage import upload_file


def generate_and_store_earnings_brief(
    ticker: str,
    accession_number: str,
) -> dict:
    """Generate, upload, and store a versioned earnings brief.

    Args:
        ticker: Company ticker symbol (e.g. "AVGO").
        accession_number: SEC accession number (e.g. "0001730168-26-000051").

    Returns:
        A dict with filing_id, ticker, accession_number, version_number,
        local_output_path, storage_path, trusted_claim_count,
        factual_claim_count, and interpretive_claim_count.

    Raises:
        ValueError: If the filing is not found or no trusted claims exist.
    """
    supabase = get_supabase_client()

    # 1. Fetch the filing id.
    filing_resp = (
        supabase.table("filings")
        .select("id")
        .eq("accession_number", accession_number)
        .execute()
    )
    if not filing_resp.data:
        raise ValueError(f"No filing found with accession_number={accession_number!r}.")
    filing_id = filing_resp.data[0]["id"]

    # 2. Determine the next version number.
    existing = (
        supabase.table("earnings_briefs")
        .select("version_number")
        .eq("accession_number", accession_number)
        .order("version_number", desc=True)
        .limit(1)
        .execute()
        .data
    )
    version_number = (existing[0]["version_number"] + 1) if existing else 1

    # 3. Build paths.
    ticker_lower = ticker.lower()
    safe_accession = accession_number.replace("-", "_")
    local_filename = f"{ticker_lower}_{safe_accession}_v{version_number}.md"
    local_output_path = f"output/briefs/{local_filename}"
    storage_path = f"briefs/{ticker_lower}/{accession_number}/v{version_number}.md"

    # 4. Generate the local markdown file.
    brief_result = generate_earnings_brief(
        ticker=ticker,
        accession_number=accession_number,
        output_path=local_output_path,
    )

    # 5. Upload to private Storage.
    upload_file(local_output_path, storage_path)

    # 6. Read the generated markdown content.
    markdown_content = Path(local_output_path).read_text(encoding="utf-8")

    # 7. Insert into earnings_briefs.
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("earnings_briefs").insert(
        {
            "filing_id": filing_id,
            "ticker": ticker,
            "accession_number": accession_number,
            "version_number": version_number,
            "markdown_content": markdown_content,
            "storage_path": storage_path,
            "trusted_claim_count": brief_result["trusted_claim_count"],
            "factual_claim_count": brief_result["factual_claim_count"],
            "interpretive_claim_count": brief_result["interpretive_claim_count"],
            "generated_at": now,
        }
    ).execute()

    return {
        "filing_id": filing_id,
        "ticker": ticker,
        "accession_number": accession_number,
        "version_number": version_number,
        "local_output_path": local_output_path,
        "storage_path": storage_path,
        "trusted_claim_count": brief_result["trusted_claim_count"],
        "factual_claim_count": brief_result["factual_claim_count"],
        "interpretive_claim_count": brief_result["interpretive_claim_count"],
    }
