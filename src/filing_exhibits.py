import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

_USER_AGENT = os.getenv("SEC_USER_AGENT")
if not _USER_AGENT:
    raise EnvironmentError(
        "SEC_USER_AGENT is not set. Add it to your .env file. "
        "Use the format: 'Your Name your@email.com' as required by SEC EDGAR."
    )

_TIMEOUT_SECONDS = 15

# "pr" before the extension catches press-release names like q1fy27pr.htm
# (NVIDIA's convention); "99.1" with no separator catches names like
# q12026991.htm (AMD's convention). Both carry no ex-99/earnings marker.
_EARNINGS_FILENAME_PATTERNS = re.compile(
    r"(ex[_\-]?99|exhibit[_\-]?99|xex99|99[_\-.]?1(?=\D|$)|earnings|"
    r"press[_\-]?release|results|pr\.html?$)",
    re.IGNORECASE,
)

# Quality ranking for earnings-release candidates: prose press releases are
# better extraction sources than slide decks, so document quality decides
# and file size only breaks ties within a tier (lower tier wins).
_SLIDE_DECK_PATTERNS = re.compile(r"(slide|presentation|deck)", re.IGNORECASE)
_QUALITY_TIERS = (
    (1, re.compile(r"(press[_\-]?release|earnings[_\-]?release|pr\.html?$)", re.IGNORECASE)),
    (2, re.compile(r"(financial[_\-]?results|results)", re.IGNORECASE)),
    (3, re.compile(r"(ex[_\-]?99|exhibit[_\-]?99|xex99|99[_\-.]?1(?=\D|$))", re.IGNORECASE)),
)
_SLIDE_DECK_TIER = 4
_FALLBACK_TIER = 5


def _exhibit_quality_tier(exhibit: dict) -> int:
    """Rank an earnings-release candidate; lower is better."""
    text = f"{exhibit.get('filename', '')} {exhibit.get('description', '')}"
    if _SLIDE_DECK_PATTERNS.search(text):
        return _SLIDE_DECK_TIER
    for tier, pattern in _QUALITY_TIERS:
        if pattern.search(text):
            return tier
    return _FALLBACK_TIER


def get_filing_index_url(sec_url: str) -> str:
    """Derive the index.json directory-listing URL from a filing document URL.

    Args:
        sec_url: The SEC EDGAR URL of a filing document.

    Returns:
        The URL of the directory index.json for that filing.
    """
    base_dir = sec_url.rsplit("/", 1)[0]
    return f"{base_dir}/index.json"


def get_filing_exhibits(sec_url: str) -> list[dict]:
    """Fetch and classify all files in a filing's EDGAR directory.

    Args:
        sec_url: The SEC EDGAR URL of a filing document.

    Returns:
        A list of dicts with keys: filename, url, description, size_bytes,
        likely_exhibit_type.

    Raises:
        RuntimeError: If the SEC EDGAR request fails.
    """
    index_url = get_filing_index_url(sec_url)
    headers = {"User-Agent": _USER_AGENT}

    try:
        response = requests.get(index_url, headers=headers, timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise RuntimeError(
            f"SEC EDGAR returned HTTP {exc.response.status_code} for {index_url}."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            f"Failed to reach SEC EDGAR at {index_url}: {exc}"
        ) from exc

    data = response.json()
    directory = data.get("directory", {})
    items = directory.get("item", [])
    dir_path = directory.get("name", "")

    primary_filename = sec_url.rsplit("/", 1)[-1].lower()

    if dir_path and not dir_path.endswith("/"):
        dir_path += "/"

    exhibits = []
    for item in items:
        filename = item.get("name", "")
        if not filename:
            continue
        url = f"https://www.sec.gov{dir_path}{filename}"
        size_bytes = _parse_size(item.get("size", ""))
        exhibit_type = _classify_exhibit(filename, primary_filename)
        exhibits.append(
            {
                "filename": filename,
                "url": url,
                "description": filename,
                "size_bytes": size_bytes,
                "likely_exhibit_type": exhibit_type,
            }
        )

    return exhibits


def select_earnings_release_exhibit(exhibits: list[dict]) -> dict | None:
    """Select the most likely earnings release exhibit (EX-99.1) from a list.

    Prefers HTML files matching earnings release filename patterns, ranked
    press release > financial results > EX-99.1 marker > slide deck, with
    file size breaking ties within a tier. Excludes XML, XBRL, stylesheets,
    scripts, and the primary filing document.

    Args:
        exhibits: The list returned by get_filing_exhibits().

    Returns:
        The best-matching exhibit dict, or None if no suitable exhibit is found.
    """
    candidates = [
        ex for ex in exhibits
        if ex["likely_exhibit_type"] == "earnings_release"
    ]

    if not candidates:
        return None

    candidates.sort(
        key=lambda ex: (_exhibit_quality_tier(ex), -ex.get("size_bytes", 0))
    )
    return candidates[0]


def _classify_exhibit(filename: str, primary_filename: str) -> str:
    lower = filename.lower()

    if lower == primary_filename:
        return "primary_document"

    ext = ""
    if "." in lower:
        ext = "." + lower.rsplit(".", 1)[-1]

    if ext in {".xml", ".xsd"}:
        return "xbrl_or_xml"

    if ext in {".css", ".js", ".zip", ".jpg", ".png", ".gif"}:
        return "other"

    if re.match(r"^r\d+\.htm$", lower):
        return "xbrl_viewer"

    if lower.endswith("-index.htm") or lower.endswith("-index.html"):
        return "index"

    if _EARNINGS_FILENAME_PATTERNS.search(lower):
        return "earnings_release"

    return "other"


def _parse_size(size_str: str) -> int:
    if not size_str:
        return 0
    parts = size_str.strip().split()
    if len(parts) != 2:
        return 0
    try:
        value = float(parts[0].replace(",", ""))
        unit = parts[1].upper()
        multipliers = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3}
        return int(value * multipliers.get(unit, 1))
    except (ValueError, KeyError):
        return 0
