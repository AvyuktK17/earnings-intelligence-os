"""Insert the Bundle D v1 approved acquirer-target pairs into ``ma_screen_pairs``.

Dry-run by default; writes only with ``--confirm``. Idempotent: pairs whose
(acquirer_ticker, target_ticker) combination already exists in the table are
skipped, so this script is safe to rerun at any time.

Only the 15 Avyukt-approved v1 pairs are included here. The 9 holdout pairs
and 3 dropped pairs from the review are intentionally excluded.
``manually_reviewed = true`` is set on every row because each pair was
explicitly signed off before this script was written.

Requires the ``ma_screen_pairs`` table to exist (migrations/bundle_d_ma_screen.sql).
Never calls an LLM. Never prints credentials.

Usage:
    python add_screen_pairs.py            # dry run
    python add_screen_pairs.py --confirm  # insert missing pairs
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from src.database import get_supabase_client

load_dotenv()

# v1 approved pairs (locked 2026-06-12 after Avyukt's review).
# fit_note and regulatory_note are one-liners matching the pairs-review doc;
# they are stored for display and never used in scoring.
PAIRS: list[dict] = [
    # ── AVGO (4 pairs) ────────────────────────────────────────────────────────
    {
        "acquirer_ticker": "AVGO",
        "target_ticker": "CRDO",
        "fit_note": "High-speed SerDes/AEC connectivity adjacent to Tomahawk/Jericho networking",
        "regulatory_note": "China revenue exposure both sides",
        "manually_reviewed": True,
    },
    {
        "acquirer_ticker": "AVGO",
        "target_ticker": "ALAB",
        "fit_note": "AI-cloud retimers/CXL extends data-center franchise",
        "regulatory_note": "Deal-size scrutiny in AI infra",
        "manually_reviewed": True,
    },
    {
        "acquirer_ticker": "AVGO",
        "target_ticker": "MTSI",
        "fit_note": "RF/photonics components complement optical networking",
        "regulatory_note": "Low",
        "manually_reviewed": True,
    },
    {
        "acquirer_ticker": "AVGO",
        "target_ticker": "RMBS",
        "fit_note": "Memory-interface chips and silicon IP licensing fits AVGO's IP economics",
        "regulatory_note": "Low",
        "manually_reviewed": True,
    },
    # ── NVDA (2 pairs) ────────────────────────────────────────────────────────
    {
        "acquirer_ticker": "NVDA",
        "target_ticker": "ALAB",
        "fit_note": "Connectivity for AI servers — direct ecosystem adjacency",
        "regulatory_note": "High: NVDA deals draw global review post-ARM",
        "manually_reviewed": True,
    },
    {
        "acquirer_ticker": "NVDA",
        "target_ticker": "CRDO",
        "fit_note": "AECs/optical DSP in AI clusters complement NVLink/Ethernet strategy",
        "regulatory_note": "High: NVDA deals draw global review post-ARM",
        "manually_reviewed": True,
    },
    # ── AMD (4 pairs) ─────────────────────────────────────────────────────────
    {
        "acquirer_ticker": "AMD",
        "target_ticker": "LSCC",
        "fit_note": "Low-power FPGA complements Xilinx high-end line (Xilinx playbook continuation)",
        "regulatory_note": "China approval risk (Xilinx precedent: cleared)",
        "manually_reviewed": True,
    },
    {
        "acquirer_ticker": "AMD",
        "target_ticker": "ALAB",
        "fit_note": "AI-platform connectivity for Instinct scale-out",
        "regulatory_note": "Moderate",
        "manually_reviewed": True,
    },
    {
        "acquirer_ticker": "AMD",
        "target_ticker": "CRDO",
        "fit_note": "SerDes/connectivity tightens AMD data-center GPU stack",
        "regulatory_note": "Moderate",
        "manually_reviewed": True,
    },
    {
        "acquirer_ticker": "AMD",
        "target_ticker": "RMBS",
        "fit_note": "Memory-interface IP relevant to HBM-heavy roadmap",
        "regulatory_note": "Low",
        "manually_reviewed": True,
    },
    # ── QCOM (4 pairs) ────────────────────────────────────────────────────────
    {
        "acquirer_ticker": "QCOM",
        "target_ticker": "SYNA",
        "fit_note": "IoT/edge connectivity directly overlaps QCOM diversification push",
        "regulatory_note": "China approval risk (NXP precedent: blocked)",
        "manually_reviewed": True,
    },
    {
        "acquirer_ticker": "QCOM",
        "target_ticker": "SLAB",
        "fit_note": "IoT wireless SoC strengthens connected-device franchise",
        "regulatory_note": "China approval risk (NXP-pattern)",
        "manually_reviewed": True,
    },
    {
        "acquirer_ticker": "QCOM",
        "target_ticker": "ALGM",
        "fit_note": "Auto magnetic sensing accelerates automotive ambitions",
        "regulatory_note": "Auto-supplier review likely",
        "manually_reviewed": True,
    },
    {
        "acquirer_ticker": "QCOM",
        "target_ticker": "AMBA",
        "fit_note": "Vision SoC for ADAS/IoT cameras strengthens QCOM ADAS narrative",
        "regulatory_note": "Moderate",
        "manually_reviewed": True,
    },
    # ── INTC (1 pair) ─────────────────────────────────────────────────────────
    {
        "acquirer_ticker": "INTC",
        "target_ticker": "MTSI",
        "fit_note": "Photonics aligns with INTC silicon-photonics strategy and optical interconnect roadmap",
        "regulatory_note": "Low",
        "manually_reviewed": True,
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually insert missing pair rows (default is a dry run).",
    )
    args = parser.parse_args()

    supabase = get_supabase_client()

    existing_resp = (
        supabase.table("ma_screen_pairs")
        .select("acquirer_ticker, target_ticker")
        .execute()
    )
    existing = {
        (r["acquirer_ticker"], r["target_ticker"])
        for r in (existing_resp.data or [])
    }

    to_insert = [
        p for p in PAIRS
        if (p["acquirer_ticker"], p["target_ticker"]) not in existing
    ]
    skipped = [
        p for p in PAIRS
        if (p["acquirer_ticker"], p["target_ticker"]) in existing
    ]

    print(
        f"v1 pairs: {len(PAIRS)} total | "
        f"already present (skipped): {len(skipped)} | "
        f"to insert: {len(to_insert)}"
    )
    if skipped:
        for p in skipped:
            print(f"  = {p['acquirer_ticker']}/{p['target_ticker']}  (already exists)")

    if to_insert:
        print()
        for p in to_insert:
            print(
                f"  + {p['acquirer_ticker']:<5} → {p['target_ticker']:<5} "
                f"manually_reviewed={p['manually_reviewed']}"
            )
            print(f"      fit:        {p['fit_note']}")
            print(f"      regulatory: {p['regulatory_note']}")
    else:
        print("Nothing to insert.")
        return 0

    if not args.confirm:
        print("\nDry run only. Re-run with --confirm to insert.")
        return 0

    supabase.table("ma_screen_pairs").insert(to_insert).execute()
    print(f"\nInserted {len(to_insert)} pairs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
