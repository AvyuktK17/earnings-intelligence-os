import sys

from src.pipeline_runs import fail_pipeline_run, start_pipeline_run


def main() -> None:
    # Step 1: start a new pipeline run
    print("Starting pipeline run...")
    run = start_pipeline_run(ticker="AMD", trigger_type="manual_test")
    print("Inserted row:")
    print(run)

    run_id = run["id"]

    # Step 2: mark it as failed
    error_msg = "Simulated SEC download failure"
    print(f"\nFailing pipeline run (id={run_id})...")
    updated_run = fail_pipeline_run(run_id, error_msg)
    print("Updated row:")
    print(updated_run)

    # Step 3: verify all three conditions
    failures = []

    if updated_run["status"] != "failed":
        failures.append(f"status: expected 'failed', got '{updated_run['status']}'")

    if not updated_run["completed_at"]:
        failures.append("completed_at is empty")

    if updated_run["error_message"] != error_msg:
        failures.append(
            f"error_message: expected '{error_msg}', got '{updated_run['error_message']}'"
        )

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    print(f"\nPASS: pipeline run {run_id} marked as '{updated_run['status']}'")
    print(f"  completed_at : {updated_run['completed_at']}")
    print(f"  error_message: {updated_run['error_message']}")


if __name__ == "__main__":
    main()
