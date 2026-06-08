from src.database import get_supabase_client
from src.run_filing_check import run_filing_check


def run_all_filing_checks(
    trigger_type: str = "manual",
    limit_per_company: int = 5,
) -> list[dict]:
    """Run a filing check for every company in the Supabase companies table.

    Args:
        trigger_type: How this run was triggered (e.g. "manual", "scheduled").
        limit_per_company: Maximum relevant filings to sync per company.

    Returns:
        A list of result dicts, one per company. Failed companies are included
        with status="failed" and an error_message key.
    """
    supabase = get_supabase_client()

    response = supabase.table("companies").select("ticker, cik").execute()
    companies = response.data

    results = []

    for company in companies:
        ticker = company["ticker"]
        cik = company["cik"]

        try:
            result = run_filing_check(
                ticker=ticker,
                cik=cik,
                trigger_type=trigger_type,
                limit=limit_per_company,
            )
        except Exception as exc:
            results.append(
                {
                    "ticker": ticker,
                    "status": "failed",
                    "error_message": str(exc),
                    "checked_count": 0,
                    "inserted_count": 0,
                    "skipped_count": 0,
                }
            )
            continue

        results.append(result)

    return results
