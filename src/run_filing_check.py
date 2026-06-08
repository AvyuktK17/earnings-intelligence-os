from src.pipeline_runs import start_pipeline_run, complete_pipeline_run, fail_pipeline_run
from src.filing_sync import sync_recent_filings


def run_filing_check(
    ticker: str,
    cik: str,
    trigger_type: str = "manual",
    limit: int = 10,
) -> dict:
    """Orchestrate a filing check: start a pipeline run, sync filings, mark done.

    Args:
        ticker: Stock ticker symbol (e.g. "QCOM").
        cik: SEC CIK number for the company.
        trigger_type: How this run was triggered (e.g. "manual", "scheduled").
        limit: Maximum number of relevant filings to sync.

    Returns:
        A dict with run_id, status, ticker, checked_count, inserted_count,
        skipped_count.

    Raises:
        Any exception raised by sync_recent_filings, after marking the run failed.
    """
    run = start_pipeline_run(ticker, trigger_type)
    run_id = run["id"]

    try:
        sync_result = sync_recent_filings(ticker, cik, limit=limit)
    except Exception as exc:
        fail_pipeline_run(run_id, str(exc))
        raise

    complete_pipeline_run(run_id)

    return {
        "run_id": run_id,
        "status": "success",
        "ticker": sync_result["ticker"],
        "checked_count": sync_result["checked_count"],
        "inserted_count": sync_result["inserted_count"],
        "skipped_count": sync_result["skipped_count"],
    }
