"""Fetch draft target fundamentals from SEC XBRL for the Bundle D screener.

Pulls each target's latest TTM snapshot from the official SEC companyconcept
API (https://data.sec.gov/api/xbrl/companyconcept/...) and writes/updates
``backfill/target_fundamentals_v1.csv``. Every fetched value carries its
accession number, source URL, and fetch timestamp. Nothing touches Supabase —
this script only produces the draft CSV for analyst review.

Lanes (kept visibly separate in the CSV):
* SOURCED  — raw XBRL facts (revenue, gross profit, CFO, capex, cash, STI,
  debt, shares): extraction_method = "sec_xbrl_api"
* MANUAL   — share_price / share_price_date: market data, entered by the
  analyst for one chosen snapshot date; never fetched here
* DERIVED  — margins, growth, market cap, EV, EV/TTM revenue: computed later
  by load_target_backfill.py from the reviewed raw values, never stored here

No value is ever fabricated: a concept that cannot be resolved stays blank
and is listed in the row's missing_fields. Requires SEC_USER_AGENT in .env.

Usage:
    python fetch_target_facts.py                # all 14 targets
    python fetch_target_facts.py --ticker LSCC  # one target
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

CSV_PATH = Path(__file__).parent / "backfill" / "target_fundamentals_v1.csv"
_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_CONCEPT_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{tag}.json"
_TIMEOUT = 20

TARGET_TICKERS = [
    "LSCC", "MTSI", "SLAB", "SYNA", "RMBS", "CRUS", "ALGM",
    "POWI", "SMTC", "AMBA", "MXL", "SITM", "CRDO", "ALAB",
]

# Concept fallback chains, in preference order. (taxonomy, tag)
CONCEPTS: dict[str, list[tuple[str, str]]] = {
    "revenue": [
        ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        # IncludingAssessedTax used by Rambus (RMBS) and some other issuers post-ASC-606
        ("us-gaap", "RevenueFromContractWithCustomerIncludingAssessedTax"),
        ("us-gaap", "Revenues"),
        ("us-gaap", "SalesRevenueNet"),
    ],
    "gross_profit": [("us-gaap", "GrossProfit")],
    "cost_of_revenue": [  # fallback to derive gross profit when GrossProfit is untagged
        ("us-gaap", "CostOfRevenue"),
        ("us-gaap", "CostOfGoodsAndServicesSold"),
    ],
    "cfo": [
        ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
        ("us-gaap", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
    ],
    "capex": [("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment")],
    "cash": [
        ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
        # SiTime (SITM) and some other issuers only tag the ASC-230 reconciliation line;
        # includes restricted cash — analyst should verify restricted portion is negligible.
        ("us-gaap", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
    ],
    "sti": [
        ("us-gaap", "ShortTermInvestments"),
        ("us-gaap", "MarketableSecuritiesCurrent"),
        ("us-gaap", "AvailableForSaleSecuritiesDebtSecuritiesCurrent"),
        # SiTime (SITM) classifies short-term securities as held-to-maturity
        ("us-gaap", "DebtSecuritiesHeldToMaturityAmortizedCostAfterAllowanceForCreditLossCurrent"),
        ("us-gaap", "HeldToMaturitySecuritiesCurrent"),
    ],
    "debt_noncurrent": [
        ("us-gaap", "LongTermDebtNoncurrent"),
        ("us-gaap", "LongTermDebt"),
        ("us-gaap", "ConvertibleDebtNoncurrent"),
        # Convertible notes when tagged at the instrument level rather than the line item
        ("us-gaap", "ConvertibleNotesPayable"),
        ("us-gaap", "SeniorNotes"),
        ("us-gaap", "NotesPayable"),
    ],
    "debt_current": [
        ("us-gaap", "LongTermDebtCurrent"),
        ("us-gaap", "ConvertibleNotesPayableCurrent"),
        ("us-gaap", "SeniorNotesCurrent"),
    ],
    "shares": [("dei", "EntityCommonStockSharesOutstanding")],
}

DURATION_KEYS = {"revenue", "gross_profit", "cost_of_revenue", "cfo", "capex"}
INSTANT_KEYS = {"cash", "sti", "debt_noncurrent", "debt_current", "shares"}

CSV_COLUMNS = [
    "ticker", "cik", "status", "ttm_end_date",
    "ttm_revenue_usd_k", "prior_ttm_revenue_usd_k", "ttm_gross_profit_usd_k",
    "ttm_cfo_usd_k", "ttm_capex_usd_k",
    "cash_usd_k", "sti_usd_k", "total_debt_usd_k",
    "shares_outstanding", "shares_outstanding_date",
    "share_price_usd", "share_price_date",
    "extraction_method", "source_accessions", "source_urls", "fetched_at",
    "missing_fields", "requires_manual_review", "reviewed_by", "reviewed_at",
    "notes",
]


def _headers() -> dict:
    ua = os.getenv("SEC_USER_AGENT")
    if not ua:
        raise EnvironmentError(
            "SEC_USER_AGENT is not set. Add it to your .env file. "
            "Use the format: 'Your Name your@email.com' as required by SEC EDGAR."
        )
    return {"User-Agent": ua}


def fetch_cik_map() -> dict[str, str]:
    resp = requests.get(_TICKER_MAP_URL, headers=_headers(), timeout=_TIMEOUT)
    resp.raise_for_status()
    return {
        str(e["ticker"]).upper(): str(e["cik_str"]).zfill(10)
        for e in resp.json().values()
    }


def fetch_concept(
    cik: str,
    key: str,
    ttm_end: date | None = None,
) -> tuple[list[dict], str | None, str | None]:
    """Return (facts, tag_used, url_used) for the first resolvable fallback.

    For instant keys (balance-sheet items), each fallback tag is tested via
    latest_instant() with the staleness guard. Tags whose most-recent fact is
    stale are skipped and the next fallback is tried, ensuring stale data from
    old XBRL filings never silently wins.
    """
    for taxonomy, tag in CONCEPTS[key]:
        url = _CONCEPT_URL.format(cik=cik, taxonomy=taxonomy, tag=tag)
        resp = requests.get(url, headers=_headers(), timeout=_TIMEOUT)
        if resp.status_code == 404:
            continue
        resp.raise_for_status()
        units = resp.json().get("units", {})
        facts = units.get("USD") or units.get("shares") or []
        if not facts:
            continue
        if key in INSTANT_KEYS and ttm_end is not None:
            val, end, accn = latest_instant(facts, ttm_end=ttm_end,
                                            tag_hint=f"{taxonomy}:{tag}")
            if val is None:
                continue  # stale — try next fallback
        return facts, f"{taxonomy}:{tag}", url
    return [], None, None


def _to_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _duration_days(f: dict) -> int:
    return (_to_date(f["end"]) - _to_date(f["start"])).days


def ttm_value(facts: list[dict]) -> tuple[float | None, str | None, set[str]]:
    """TTM = latest FY + post-FY YTD stub − matching prior-year stub.

    Uses only as-reported durations. Returns (value, ttm_end_date, accessions).
    None when the required pieces are not all present (never interpolated).
    """
    annual = [f for f in facts if 340 <= _duration_days(f) <= 380]
    if not annual:
        return None, None, set()
    fy = max(annual, key=lambda f: f["end"])
    stubs = [f for f in facts if f["start"] > fy["end"] or f["start"] == _next_day(fy["end"])]
    stubs = [f for f in stubs if _duration_days(f) < 340 and f["end"] > fy["end"]]
    if not stubs:  # fiscal year-end is the latest data: TTM = FY
        return float(fy["val"]), fy["end"], {fy["accn"]}
    stub = max(stubs, key=lambda f: f["end"])
    stub_days = _duration_days(stub)
    prior = [
        f for f in facts
        if f["end"] <= fy["end"] and abs(_duration_days(f) - stub_days) <= 10
        and 350 <= (_to_date(stub["end"]) - _to_date(f["end"])).days <= 380
    ]
    if not prior:
        return None, None, set()
    prior_stub = max(prior, key=lambda f: f["end"])
    val = float(fy["val"]) + float(stub["val"]) - float(prior_stub["val"])
    return val, stub["end"], {fy["accn"], stub["accn"], prior_stub["accn"]}


def _next_day(d: str) -> str:
    from datetime import timedelta
    return (_to_date(d) + timedelta(days=1)).isoformat()


MAX_INSTANT_LAG_DAYS = 180  # reject balance-sheet facts older than this relative to TTM end


def latest_instant(
    facts: list[dict],
    ttm_end: date | None = None,
    tag_hint: str = "",
) -> tuple[float | None, str | None, str | None]:
    """Return (value, end_date, accession) for the most recent instant fact.

    When ttm_end is supplied, any fact whose end date is more than
    MAX_INSTANT_LAG_DAYS before ttm_end is rejected as stale rather than
    silently returned. A warning is printed so the caller knows the tag was
    skipped; the caller's fallback chain then tries the next tag.
    """
    if not facts:
        return None, None, None
    f = max(facts, key=lambda x: x["end"])
    if ttm_end is not None:
        lag = (ttm_end - _to_date(f["end"])).days
        if lag > MAX_INSTANT_LAG_DAYS:
            print(
                f"  STALE TAG REJECTED: {tag_hint} end={f['end']} "
                f"is {lag}d before TTM end {ttm_end} "
                f"(threshold {MAX_INSTANT_LAG_DAYS}d) — skipping to next fallback"
            )
            return None, None, None
    return float(f["val"]), f["end"], f["accn"]


def build_row(ticker: str, cik: str) -> dict:
    row: dict = {c: "" for c in CSV_COLUMNS}
    row.update(ticker=ticker, cik=cik, extraction_method="sec_xbrl_api",
               fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    missing: list[str] = []
    accessions: set[str] = set()
    urls: list[str] = []

    def grab_duration(key: str, col: str, prior_col: str | None = None) -> None:
        facts, tag, url = fetch_concept(cik, key)
        if url:
            urls.append(url)
        val, end, accns = ttm_value(facts) if facts else (None, None, set())
        if val is None:
            missing.append(col)
            return
        row[col] = round(val / 1000.0, 1)  # store USD thousands
        accessions.update(accns)
        if not row["ttm_end_date"]:
            row["ttm_end_date"] = end
        if prior_col:  # prior-year TTM for YoY growth (revenue only)
            # Exclude facts from within 350 days of the current TTM end so the
            # prior-TTM base annual is ≥1 year old (avoids FY ending 3 months
            # before current TTM being selected as the "prior" annual).
            from datetime import timedelta
            prior_cutoff = (_to_date(end) - timedelta(days=350)).isoformat()
            prior_facts = [f for f in facts if f["end"] <= prior_cutoff]
            pval, _, paccns = ttm_value(prior_facts)
            if pval is None:
                missing.append(prior_col)
            else:
                row[prior_col] = round(pval / 1000.0, 1)
                accessions.update(paccns)

    grab_duration("revenue", "ttm_revenue_usd_k", "prior_ttm_revenue_usd_k")
    grab_duration("gross_profit", "ttm_gross_profit_usd_k")
    if "ttm_gross_profit_usd_k" in missing and row["ttm_revenue_usd_k"]:
        # fallback: GP = revenue − cost of revenue (flagged in notes)
        facts, tag, url = fetch_concept(cik, "cost_of_revenue")
        if url:
            urls.append(url)
        cor, end, accns = ttm_value(facts) if facts else (None, None, set())
        if cor is not None and end == row["ttm_end_date"]:
            row["ttm_gross_profit_usd_k"] = round(
                float(row["ttm_revenue_usd_k"]) - cor / 1000.0, 1)
            missing.remove("ttm_gross_profit_usd_k")
            accessions.update(accns)
            row["notes"] = (row["notes"] + " GP derived as revenue−CoR"
                            f" ({tag}).").strip()
    grab_duration("cfo", "ttm_cfo_usd_k")
    grab_duration("capex", "ttm_capex_usd_k")

    # ttm_end_date is set by grab_duration("revenue", ...) above
    ttm_end_for_instant: date | None = (
        _to_date(str(row["ttm_end_date"])) if row["ttm_end_date"] else None
    )

    for key, col in (("cash", "cash_usd_k"), ("sti", "sti_usd_k")):
        facts, tag, url = fetch_concept(cik, key, ttm_end=ttm_end_for_instant)
        if url:
            urls.append(url)
        val, end, accn = latest_instant(facts, ttm_end=ttm_end_for_instant,
                                        tag_hint=tag or key)
        if val is None:
            missing.append(col)
        else:
            row[col] = round(val / 1000.0, 1)
            accessions.add(accn)
            if tag and "RestrictedCash" in tag:
                row["notes"] = (row["notes"] +
                    f" Cash via {tag}; includes restricted cash — verify restricted portion is negligible.").strip()
            if tag and "HeldToMaturity" in tag:
                row["notes"] = (row["notes"] +
                    f" STI via {tag} (held-to-maturity, amortized cost, current portion).").strip()

    # Debt: sum noncurrent + current when present; recent absence is flagged,
    # never silently treated as zero.
    debt_total, debt_found = 0.0, False
    for key in ("debt_noncurrent", "debt_current"):
        facts, tag, url = fetch_concept(cik, key, ttm_end=ttm_end_for_instant)
        if url:
            urls.append(url)
        val, end, accn = latest_instant(facts, ttm_end=ttm_end_for_instant,
                                        tag_hint=tag or key)
        if val is not None and end and end >= str(row["ttm_end_date"] or "1900"):
            debt_total += val
            debt_found = True
            accessions.add(accn)
    if debt_found:
        row["total_debt_usd_k"] = round(debt_total / 1000.0, 1)
    else:
        missing.append("total_debt_usd_k")
        row["notes"] = (row["notes"] +
                        " No current-period debt tag found; verify zero debt "
                        "against the latest 10-Q balance sheet.").strip()

    facts, tag, url = fetch_concept(cik, "shares", ttm_end=ttm_end_for_instant)
    if url:
        urls.append(url)
    val, end, accn = latest_instant(facts, ttm_end=ttm_end_for_instant,
                                    tag_hint=tag or "shares")
    if val is None:
        missing.append("shares_outstanding")
    else:
        row["shares_outstanding"] = int(val)
        row["shares_outstanding_date"] = end
        accessions.add(accn)

    missing.extend(["share_price_usd", "share_price_date"])  # always manual
    row["missing_fields"] = ";".join(missing)
    row["source_accessions"] = ";".join(sorted(accessions))
    row["source_urls"] = ";".join(urls)
    row["requires_manual_review"] = "true"
    row["status"] = "fetched_pending_review" if row["ttm_revenue_usd_k"] else "fetch_failed"
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", help="Fetch one ticker only")
    args = parser.parse_args()

    tickers = [args.ticker.upper()] if args.ticker else TARGET_TICKERS
    cik_map = fetch_cik_map()

    existing: dict[str, dict] = {}
    if CSV_PATH.exists():
        with open(CSV_PATH, newline="") as fh:
            existing = {r["ticker"]: r for r in csv.DictReader(fh)}

    for ticker in tickers:
        cik = cik_map.get(ticker)
        if not cik:
            print(f"{ticker}: not in SEC ticker map — skipped")
            continue
        prev = existing.get(ticker, {})
        if prev.get("reviewed_by"):
            print(f"{ticker}: already reviewed — left untouched")
            continue
        print(f"{ticker}: fetching (CIK {cik}) ...")
        row = build_row(ticker, cik)
        # preserve manual fields if the analyst already typed them
        for col in ("share_price_usd", "share_price_date", "notes"):
            if prev.get(col) and not row.get(col):
                row[col] = prev[col]
        existing[ticker] = row
        print(f"  status={row['status']} missing=[{row['missing_fields']}]")

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_PATH, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for ticker in TARGET_TICKERS:
            if ticker in existing:
                writer.writerow({c: existing[ticker].get(c, "") for c in CSV_COLUMNS})
    print(f"\nWrote {CSV_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
