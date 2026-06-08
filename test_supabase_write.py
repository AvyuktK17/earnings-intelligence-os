import sys

from src.database import get_supabase_client


def main() -> None:
    try:
        supabase = get_supabase_client()

        response = (
            supabase.table("pipeline_runs")
            .insert(
                {
                    "ticker": "QCOM",
                    "status": "success",
                    "trigger_type": "manual_test",
                }
            )
            .execute()
        )

        print("Write test successful.")
        print(response.data)

    except Exception as error:
        print(f"Write test failed: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
