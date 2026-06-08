from datetime import datetime, timezone

from src.database import get_supabase_client


def start_pipeline_run(ticker: str, trigger_type: str) -> dict:
    """Insert a new pipeline run with status 'running' and return the inserted row."""
    supabase = get_supabase_client()

    response = (
        supabase.table("pipeline_runs")
        .insert(
            {
                "ticker": ticker,
                "trigger_type": trigger_type,
                "status": "running",
            }
        )
        .execute()
    )

    return response.data[0]


def complete_pipeline_run(run_id: int) -> dict:
    """Mark a pipeline run as successful and return the updated row."""
    supabase = get_supabase_client()

    now = datetime.now(timezone.utc).isoformat()

    response = (
        supabase.table("pipeline_runs")
        .update(
            {
                "status": "success",
                "completed_at": now,
            }
        )
        .eq("id", run_id)
        .execute()
    )

    return response.data[0]


def fail_pipeline_run(run_id: int, error_message: str) -> dict:
    """Mark a pipeline run as failed, store the error, and return the updated row."""
    supabase = get_supabase_client()

    now = datetime.now(timezone.utc).isoformat()

    response = (
        supabase.table("pipeline_runs")
        .update(
            {
                "status": "failed",
                "completed_at": now,
                "error_message": error_message,
            }
        )
        .eq("id", run_id)
        .execute()
    )

    return response.data[0]
