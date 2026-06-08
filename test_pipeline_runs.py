import sys

from src.pipeline_runs import complete_pipeline_run, start_pipeline_run


def main() -> None:
    # Step 1: start a new pipeline run
    print("Starting pipeline run...")
    run = start_pipeline_run(ticker="QCOM", trigger_type="manual_test")
    print("Inserted row:")
    print(run)

    run_id = run["id"]

    # Step 2: mark it as successful
    print(f"\nCompleting pipeline run (id={run_id})...")
    updated_run = complete_pipeline_run(run_id)
    print("Updated row:")
    print(updated_run)

    # Step 3: verify the final status
    final_status = updated_run["status"]
    if final_status != "success":
        print(f"\nFAIL: expected status 'success', got '{final_status}'")
        sys.exit(1)

    print(f"\nPASS: pipeline run {run_id} completed with status '{final_status}'")


if __name__ == "__main__":
    main()
