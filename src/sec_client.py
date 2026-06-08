import os
import requests
from dotenv import load_dotenv

load_dotenv()

_USER_AGENT = os.getenv("SEC_USER_AGENT")
if not _USER_AGENT:
    raise EnvironmentError(
        "SEC_USER_AGENT is not set. Add it to your .env file. "
        "Use the format: 'Your Name your@email.com' as required by SEC EDGAR."
    )

_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_TIMEOUT_SECONDS = 15


def get_recent_filings(cik: str) -> list[dict]:
    """Fetch recent SEC filings for a company by CIK.

    Args:
        cik: The company's CIK number (will be zero-padded to 10 digits).

    Returns:
        A list of filing dicts with keys: accession_number, filing_date,
        report_date, form, primary_document.

    Raises:
        ValueError: If the CIK is not a valid number.
        RuntimeError: If the SEC request fails.
    """
    padded_cik = str(cik).strip().lstrip("0")
    if not padded_cik.isdigit():
        raise ValueError(f"CIK must contain only digits, got: {cik!r}")
    padded_cik = padded_cik.zfill(10)

    url = _SUBMISSIONS_URL.format(cik=padded_cik)
    headers = {"User-Agent": _USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise RuntimeError(
            f"SEC EDGAR returned HTTP {exc.response.status_code} for CIK {padded_cik}. "
            "Check that the CIK is correct."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            f"Failed to reach SEC EDGAR for CIK {padded_cik}: {exc}"
        ) from exc

    data = response.json()
    recent = data.get("filings", {}).get("recent", {})

    accession_numbers = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    forms = recent.get("form", [])
    primary_documents = recent.get("primaryDocument", [])

    filings = []
    for i in range(len(accession_numbers)):
        filings.append(
            {
                "accession_number": accession_numbers[i] if i < len(accession_numbers) else "",
                "filing_date": filing_dates[i] if i < len(filing_dates) else "",
                "report_date": report_dates[i] if i < len(report_dates) else "",
                "form": forms[i] if i < len(forms) else "",
                "primary_document": primary_documents[i] if i < len(primary_documents) else "",
            }
        )

    return filings
