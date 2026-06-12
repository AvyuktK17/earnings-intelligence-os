"""Insert the Bundle D M&A screener target universe into ``companies``.

Dry-run by default; writes only with ``--confirm``. Idempotent: tickers
already present in ``companies`` are skipped (their coverage_tier is never
changed by this script). CIKs are resolved live from SEC EDGAR's official
ticker mapping (https://www.sec.gov/files/company_tickers.json) at run time
so nothing is hand-typed; the dry run prints every resolved CIK for review.

Requires the ``coverage_tier`` migration (migrations/bundle_d_ma_screen.sql)
to have been applied first. Never calls an LLM; never prints credentials.

Usage:
    python add_screen_targets.py            # dry run
    python add_screen_targets.py --confirm  # insert missing targets
"""

from __future__ import annotations

import argparse
import os
import sys

import requests
from dotenv import load_dotenv

from src.database import get_supabase_client

load_dotenv()

_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_TIMEOUT_SECONDS = 15

# Bundle D target universe (locked 2026-06-11). business_model strings follow
# the existing companies.business_model convention (short descriptor used in
# peer-comparability notes).
TARGETS: list[dict] = [
    {"ticker": "LSCC", "company_name": "Lattice Semiconductor Corporation", "business_model": "Fabless low-power FPGA"},
    {"ticker": "MTSI", "company_name": "MACOM Technology Solutions Holdings, Inc.", "business_model": "Analog/RF and photonic semiconductors"},
    {"ticker": "SLAB", "company_name": "Silicon Laboratories Inc.", "business_model": "Fabless IoT wireless SoC"},
    {"ticker": "SYNA", "company_name": "Synaptics Incorporated", "business_model": "Fabless IoT/edge connectivity and sensing"},
    {"ticker": "RMBS", "company_name": "Rambus Inc.", "business_model": "Memory interface chips and silicon IP licensing"},
    {"ticker": "CRUS", "company_name": "Cirrus Logic, Inc.", "business_model": "Fabless mixed-signal audio/HPMS"},
    {"ticker": "ALGM", "company_name": "Allegro MicroSystems, Inc.", "business_model": "Magnetic sensing and power ICs (auto/industrial)"},
    {"ticker": "POWI", "company_name": "Power Integrations, Inc.", "business_model": "High-voltage power-conversion ICs"},
    {"ticker": "SMTC", "company_name": "Semtech Corporation", "business_model": "Analog/mixed-signal, LoRa and signal integrity"},
    {"ticker": "AMBA", "company_name": "Ambarella, Inc.", "business_model": "Fabless edge-AI vision SoC"},
    {"ticker": "MXL", "company_name": "MaxLinear, Inc.", "business_model": "Fabless RF/mixed-signal connectivity"},
    {"ticker": "SITM", "company_name": "SiTime Corporation", "business_model": "MEMS precision timing"},
    {"ticker": "CRDO", "company_name": "Credo Technology Group Holding Ltd", "business_model": "High-speed connectivity (SerDes, AECs)"},
    {"ticker": "ALAB", "company_name": "Astera Labs, Inc.", "business_model": "Connectivity for AI/cloud infrastructure"},
]


def fetch_cik_map() -> dict[str, str]:
    """Resolve ticker → zero-padded CIK from SEC's official mapping."""
    user_agent = os.getenv("SEC_USER_AGENT")
    if not user_agent:
        raise EnvironmentError(
            "SEC_USER_AGENT is not set. Add it to your .env file. "
            "Use the format: 'Your Name your@email.com' as required by SEC EDGAR."
        )
    response = requests.get(
        _TICKER_MAP_URL, headers={"User-Agent": user_agent}, timeout=_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    mapping: dict[str, str] = {}
    for entry in response.json().values():
        mapping[str(entry["ticker"]).upper()] = str(entry["cik_str"]).zfill(10)
    return mapping


def build_rows(cik_map: dict[str, str]) -> tuple[list[dict], list[str]]:
    """Build insert-ready rows; tickers missing from the SEC map are errors."""
    rows: list[dict] = []
    unresolved: list[str] = []
    for target in TARGETS:
        cik = cik_map.get(target["ticker"])
        if cik is None:
            unresolved.append(target["ticker"])
            continue
        rows.append({**target, "cik": cik, "coverage_tier": "target"})
    return rows, unresolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually insert missing target rows (default is a dry run).",
    )
    args = parser.parse_args()

    cik_map = fetch_cik_map()
    rows, unresolved = build_rows(cik_map)
    if unresolved:
        print(f"ERROR: tickers not found in SEC mapping: {', '.join(unresolved)}")
        return 1

    supabase = get_supabase_client()
    existing_resp = supabase.table("companies").select("ticker").execute()
    existing = {row["ticker"].upper() for row in (existing_resp.data or [])}

    to_insert = [row for row in rows if row["ticker"] not in existing]
    skipped = [row["ticker"] for row in rows if row["ticker"] in existing]

    print(f"Universe: {len(rows)} targets | already present (skipped): {len(skipped)}"
          f"{' (' + ', '.join(skipped) + ')' if skipped else ''}")
    for row in to_insert:
        print(f"  + {row['ticker']:<5} CIK {row['cik']}  {row['company_name']}")

    if not to_insert:
        print("Nothing to insert.")
        return 0

    if not args.confirm:
        print("\nDry run only. Re-run with --confirm to insert.")
        return 0

    supabase.table("companies").insert(to_insert).execute()
    print(f"\nInserted {len(to_insert)} target companies.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
