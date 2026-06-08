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

_TIMEOUT_SECONDS = 30


def download_filing(sec_url: str, output_path: str) -> str:
    """Download a filing from SEC EDGAR and save it locally.

    Args:
        sec_url: The direct URL to the filing document on SEC EDGAR.
        output_path: Local file path where the filing will be saved.

    Returns:
        The output_path where the file was saved.

    Raises:
        RuntimeError: If the download request fails.
    """
    headers = {"User-Agent": _USER_AGENT}

    try:
        response = requests.get(sec_url, headers=headers, timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise RuntimeError(
            f"SEC EDGAR returned HTTP {exc.response.status_code} for URL: {sec_url}"
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            f"Failed to download filing from {sec_url}: {exc}"
        ) from exc

    parent_dir = os.path.dirname(output_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    with open(output_path, "wb") as f:
        f.write(response.content)

    return output_path
