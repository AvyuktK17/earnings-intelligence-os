"""Load reviewed target fundamentals into Supabase for the Bundle D screener.

Reads ``backfill/target_fundamentals_v1.csv`` (produced by
fetch_target_facts.py and reviewed by the analyst), computes the DERIVED
fields deterministically, and inserts:

* ``financial_metrics`` rows for the target's latest TTM snapshot
  (metric names match the acquirer convention so ``src.quantitative`` and
  ``src.ma_screen`` read both sides identically)
* one ``valuation_snapshots`` row per target (share price is the analyst's
  MANUAL market-data input for a single chosen snapshot date)

Safety: dry-run by default; ``--confirm`` required to write. A row is loaded
only when ``status = "reviewed"`` and ``reviewed_by``/``reviewed_at`` are
filled — fetched-but-unreviewed rows are refused. Existing rows for a ticker
are never overwritten (idempotent skip). Derived values are computed only
when every input is present; otherwise the metric is skipped and reported
(never fabricated).

NOTE before first confirm-run: verify UNIT_MODE against one existing acquirer
row (are margins stored as 0.684 or 68.4? revenue in USD or thousands?) and
adjust the constants below. This check is listed in the next-session steps.

Usage:
    python load_target_backfill.py            # dry run
    python load_target_backfill.py --confirm  # insert reviewed rows
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from src.database import get_supabase_client

CSV_PATH = Path(__file__).parent / "backfill" / "target_fundamentals_v1.csv"

# --- Unit convention (VERIFY against existing acquirer rows before confirm) --
MARGIN_AS_PERCENT = False  # Acquirer rows use decimals (0.684 not 68.4) — verified 2026-06-12
USD_SCALE = 1_000.0        # CSV stores USD thousands; metric rows store USD
# -----------------------------------------------------------------------------


def _num(v) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def derive_metrics(row: dict) -> tuple[dict[str, float], list[str]]:
    """Deterministic DERIVED fields; skipped (and reported) when inputs missing."""
    out: dict[str, float] = {}
    skipped: list[str] = []
    rev = _num(row["ttm_revenue_usd_k"])
    prior = _num(row["prior_ttm_revenue_usd_k"])
    gp = _num(row["ttm_gross_profit_usd_k"])
    cfo = _num(row["ttm_cfo_usd_k"])
    capex = _num(row["ttm_capex_usd_k"])
    cash = _num(row["cash_usd_k"])
    debt = _num(row["total_debt_usd_k"])
    pct = 100.0 if MARGIN_AS_PERCENT else 1.0

    if rev is not None:
        out["TTM Revenue"] = rev * USD_SCALE
    else:
        skipped.append("TTM Revenue")
    if rev and gp is not None:
        out["Gross Margin"] = round(gp / rev * pct, 4)
    else:
        skipped.append("Gross Margin")
    if rev and cfo is not None and capex is not None:
        out["TTM Free Cash Flow"] = (cfo - capex) * USD_SCALE
        out["Free-Cash-Flow Margin"] = round((cfo - capex) / rev * pct, 4)
    else:
        skipped.extend(["TTM Free Cash Flow", "Free-Cash-Flow Margin"])
    if rev is not None and prior:
        out["YoY Revenue Growth"] = round((rev / prior - 1.0) * pct, 4)
    else:
        skipped.append("YoY Revenue Growth")
    if cash is not None:
        out["Cash and Cash Equivalents"] = cash * USD_SCALE
    else:
        skipped.append("Cash and Cash Equivalents")
    if debt is not None:
        out["Total Debt"] = debt * USD_SCALE
    else:
        skipped.append("Total Debt")
    return out, skipped


def build_valuation_snapshot(row: dict) -> tuple[dict | None, list[str]]:
    """Valuation row; EV computed only when price, shares, cash, debt all exist."""
    missing: list[str] = []
    price = _num(row["share_price_usd"])
    shares = _num(row["shares_outstanding"])
    cash = _num(row["cash_usd_k"])
    sti = _num(row["sti_usd_k"]) or 0.0
    debt = _num(row["total_debt_usd_k"])
    for field, v in (("share_price_usd", price), ("shares_outstanding", shares),
                     ("cash_usd_k", cash), ("total_debt_usd_k", debt)):
        if v is None:
            missing.append(field)
    if missing or not row.get("share_price_date"):
        return None, missing or ["share_price_date"]
    market_cap = price * shares
    cash_total = (cash + sti) * 1_000.0
    ev = market_cap + debt * 1_000.0 - cash_total
    return {
        "ticker": row["ticker"],
        "share_price_date": row["share_price_date"],
        "share_price": price,
        "shares_outstanding": shares,
        "shares_outstanding_source_date": row["shares_outstanding_date"] or None,
        "market_cap": market_cap,
        "cash": cash_total,
        "total_debt": debt * 1_000.0,
        "enterprise_value": ev,
        "debt_measure": "long-term debt incl. current portion (SEC XBRL)",
        "source": "Bundle D target backfill (SEC XBRL + manual share price); "
                  f"accessions {row['source_accessions']}",
        "manually_reviewed": True,
        "notes": (f"Cash includes short-term investments ({sti:,.1f}k). "
                  f"TTM end {row['ttm_end_date']}. {row['notes']}").strip(),
    }, []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true",
                        help="Actually insert (default is a dry run).")
    args = parser.parse_args()

    with open(CSV_PATH, newline="") as fh:
        rows = list(csv.DictReader(fh))

    supabase = get_supabase_client()
    # Scope the existence check to the tickers in this CSV to avoid the
    # PostgREST 1000-row default page cap silently truncating results when
    # the acquirer rows already fill that window.
    csv_tickers = [r["ticker"] for r in rows]
    existing_metrics = {
        r["ticker"] for r in (supabase.table("financial_metrics")
                              .select("ticker")
                              .in_("ticker", csv_tickers)
                              .execute().data or [])
    }

    loadable, refused = [], []
    for row in rows:
        if (row["status"] == "reviewed" and row["reviewed_by"]
                and row["reviewed_at"]):
            loadable.append(row)
        else:
            refused.append((row["ticker"], row["status"]))

    print(f"CSV rows: {len(rows)} | reviewed & loadable: {len(loadable)} | "
          f"refused (unreviewed): {len(refused)}")
    for ticker, status in refused:
        print(f"  - {ticker}: status={status} (needs review before load)")

    for row in loadable:
        ticker = row["ticker"]
        metrics, skipped = derive_metrics(row)
        snapshot, snap_missing = build_valuation_snapshot(row)
        print(f"\n{ticker}: {len(metrics)} metric rows"
              f"{'; skipped: ' + ', '.join(skipped) if skipped else ''}"
              f"{'; snapshot blocked by: ' + ', '.join(snap_missing) if snap_missing else '; snapshot ready'}")
        if ticker in existing_metrics:
            print(f"  {ticker} already has financial_metrics rows — skipped "
                  "(never overwritten)")
            continue
        if not args.confirm:
            continue
        metric_rows = [
            {
                "company": ticker, "ticker": ticker,
                "fiscal_year": (row["ttm_end_date"] or "")[:4],
                "fiscal_quarter": "TTM",
                "metric_name": name, "value": value,
                "unit": ("percent" if "Margin" in name or "Growth" in name
                         else "USD"),
                "extraction_method": row["extraction_method"],
                "source_reference": f"SEC XBRL accessions {row['source_accessions']}",
                "requires_manual_review": False,  # reviewed_by gate already passed
            }
            for name, value in metrics.items()
        ]
        supabase.table("financial_metrics").insert(metric_rows).execute()
        if snapshot:
            supabase.table("valuation_snapshots").insert(snapshot).execute()
        print(f"  inserted {len(metric_rows)} metric rows"
              f"{' + 1 valuation snapshot' if snapshot else ''}")

    if not args.confirm:
        print("\nDry run only. Re-run with --confirm to insert reviewed rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
