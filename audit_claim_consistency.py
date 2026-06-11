"""Read-only numeric-consistency audit of trusted evidence claims.

For every trusted claim returned by the public GET /evidence endpoint,
extracts the numbers quoted in the claim text (percentages and dollar /
plain figures) and checks that each one literally appears in the claim's
own supporting excerpt. Numbers in a claim that are absent from its
excerpt are flagged for analyst re-review.

This is a heuristic screen, not a verdict: a flagged claim may still be
correct (e.g. a figure legitimately derived from two excerpt numbers).
Every flag should be resolved by a human through the existing review
workflow — typically by re-checking the SEC source and using the
dashboard's edit-and-approve path on a fresh extraction if the claim
text is wrong.

Read-only: calls only the public API over HTTPS. No database access,
no secrets, no writes. Safe to run anytime:

    python audit_claim_consistency.py
    python audit_claim_consistency.py --api-base http://localhost:8000
    python audit_claim_consistency.py --ticker QCOM
"""

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request

DEFAULT_API_BASE = "https://earnings-intelligence-os-api.onrender.com"

# Percentages like "13%", "13 percent", "13.5%".
_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", re.IGNORECASE)

# Figures like "$44,284 million", "44,284", "$1.2 billion".
_FIGURE_RE = re.compile(r"\$?\s*(\d{1,3}(?:,\d{3})+|\d+\.\d+|\d{4,})")


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace for literal matching."""
    return re.sub(r"\s+", " ", text).lower()


_YEAR_RE = re.compile(r"^(19|20)\d{2}$")


def _number_tokens(text: str) -> set[str]:
    """Extract comparable numeric tokens (commas stripped) from text."""
    tokens: set[str] = set()
    for match in _PERCENT_RE.finditer(text):
        tokens.add(f"{match.group(1)}%")
    for match in _FIGURE_RE.finditer(text):
        token = match.group(1).replace(",", "")
        # Bare years (fiscal 2025, Q1 2026, ...) are context, not figures.
        if _YEAR_RE.match(token):
            continue
        tokens.add(token)
    return tokens


def find_mismatches(claim_text: str, excerpt: str) -> list[str]:
    """Return numeric tokens present in the claim but not the excerpt."""
    excerpt_tokens = _number_tokens(_normalize(excerpt))
    # Also accept raw digit-substring presence, so "44,284" in the excerpt
    # satisfies "44284" and vice versa.
    excerpt_digits = _normalize(excerpt).replace(",", "")
    mismatches = []
    for token in sorted(_number_tokens(_normalize(claim_text))):
        if token in excerpt_tokens:
            continue
        bare = token.rstrip("%")
        if not token.endswith("%") and bare in excerpt_digits:
            continue
        mismatches.append(token)
    return mismatches


def fetch_evidence(api_base: str, ticker: str | None) -> list[dict]:
    params = {"limit": "200"}
    if ticker:
        params["ticker"] = ticker
    url = f"{api_base}/evidence?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=120) as response:
        return json.loads(response.read())["evidence"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Flag trusted claims whose quoted numbers do not appear in "
            "their own supporting excerpt (read-only)."
        )
    )
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--ticker", default=None)
    args = parser.parse_args()

    evidence = fetch_evidence(args.api_base.rstrip("/"), args.ticker)
    print(f"Audited {len(evidence)} trusted claim(s).\n")

    flagged = 0
    for item in evidence:
        mismatches = find_mismatches(
            item["claim"], item["supporting_excerpt"]
        )
        if not mismatches:
            continue
        flagged += 1
        print(
            f"FLAG claim_id={item['qualitative_claim_id']}  "
            f"{item['ticker']}  {item['accession_number']}"
        )
        print(f"  claim:    {item['claim']}")
        print(f"  excerpt:  {item['supporting_excerpt']}")
        print(f"  numbers in claim missing from excerpt: {mismatches}")
        print(f"  source:   {item['sec_url']}")
        print()

    if flagged:
        print(
            f"{flagged} claim(s) flagged for analyst re-review. "
            "Heuristic screen only — verify each against the SEC source."
        )
        sys.exit(1)
    print("No numeric inconsistencies detected.")


if __name__ == "__main__":
    main()
