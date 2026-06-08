import sys

from src.database import get_supabase_client


def main() -> None:
    try:
        supabase = get_supabase_client()

        companies_response = (
            supabase.table("companies")
            .select("ticker, company_name, cik, business_model")
            .order("ticker")
            .execute()
        )

        metrics_response = (
            supabase.table("financial_metrics")
            .select("ticker, fiscal_year, fiscal_quarter, metric_name, value")
            .limit(5)
            .execute()
        )

        claims_response = (
            supabase.table("qualitative_claims")
            .select("ticker, theme, claim, confidence, human_reviewed")
            .limit(5)
            .execute()
        )

        companies = companies_response.data
        metrics = metrics_response.data
        claims = claims_response.data

        print(f"Connection successful. Found {len(companies)} companies:\n")

        for company in companies:
            print(
                f"{company['ticker']}: "
                f"{company['company_name']} | "
                f"CIK {company['cik']} | "
                f"{company['business_model']}"
            )

        print("\nSample financial metrics:\n")

        for metric in metrics:
            print(
                f"{metric['ticker']} | "
                f"{metric['fiscal_year']} {metric['fiscal_quarter']} | "
                f"{metric['metric_name']} | "
                f"{metric['value']}"
            )

        print("\nSample qualitative claims:\n")

        for claim in claims:
            print(
                f"{claim['ticker']} | "
                f"{claim['theme']} | "
                f"{claim['confidence']} | "
                f"Reviewed: {claim['human_reviewed']}\n"
                f"{claim['claim']}\n"
            )

    except Exception as error:
        print(f"Connection failed: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
