"""Unit tests for the audited static-dashboard backfill.

Synthetic inputs only — no network, no live Supabase, no AI calls. A small
fake Supabase client records inserts so idempotency and the never-overwrite
guarantees can be asserted offline.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.static_dashboard_backfill import (
    VALUATION_METRIC_NAMES,
    build_avgo_metric_rows,
    build_valuation_rows,
    extract_js_array,
    run_backfill,
)

# Synthetic dashboard HTML: one operating AVGO metric, one valuation-derived
# AVGO metric (empty period), one operating AVGO metric not in the live set,
# one non-AVGO row, plus two valuation snapshots. The bracket in a string and
# the nested-looking text exercise the bracket-balancing parser.
SYNTHETIC_HTML = """
<html><script>
const METRICS = [
  {"company":"Broadcom Inc.","ticker":"AVGO","fiscal_year":"2025","fiscal_quarter":"Q1","metric_name":"Revenue","value":"14916000000.0","unit":"USD","extraction_method":"reported_standalone","source_reference":"https://sec.gov/avgo [ref]","derived_from":"","requires_manual_review":"","formula":""},
  {"company":"Broadcom Inc.","ticker":"AVGO","fiscal_year":"2025","fiscal_quarter":"Q1","metric_name":"Gross Margin","value":"0.68","unit":"ratio","extraction_method":"calculated","source_reference":"","derived_from":"","requires_manual_review":"yes","formula":"Gross Profit / Revenue"},
  {"company":"Broadcom Inc.","ticker":"AVGO","fiscal_year":"","fiscal_quarter":"","metric_name":"Share Price","value":"418.91","unit":"USD","extraction_method":"market","source_reference":"","derived_from":"","requires_manual_review":"","formula":""},
  {"company":"Broadcom Inc.","ticker":"AVGO","fiscal_year":"2025","fiscal_quarter":"Q1","metric_name":"Some New Metric","value":"123.0","unit":"USD","extraction_method":"","source_reference":"","derived_from":"","requires_manual_review":"","formula":""},
  {"company":"NVIDIA Corp","ticker":"NVDA","fiscal_year":"2025","fiscal_quarter":"Q1","metric_name":"Revenue","value":"26044000000.0","unit":"USD","extraction_method":"reported_standalone","source_reference":"","derived_from":"","requires_manual_review":"","formula":""}
];
const VALUATIONS = [
  {"ticker":"AVGO","share_price_date":"2026-06-04","share_price":"418.91","shares_outstanding":"4734668184","shares_outstanding_source_date":"2026-02-27","market_cap":"1983432750434.44","cash":"16178000000","total_debt":"67120000000","enterprise_value":"2034374750434.44","debt_measure":"gross_principal","source":"Yahoo Finance","manually_reviewed":"Yes","notes":"audited"},
  {"ticker":"NVDA","share_price_date":"2026-06-04","share_price":"218.66","shares_outstanding":"24200000000","shares_outstanding_source_date":"2026-05-15","market_cap":"5291572000000.00","cash":"10605000000","total_debt":"8468000000","enterprise_value":"5289435000000.00","debt_measure":"carrying_value","source":"Yahoo Finance","manually_reviewed":"Yes","notes":""}
];
</script></html>
"""

# The live operating metric set excludes "Some New Metric" and the valuation
# metric names, so only "Revenue" and "Gross Margin" should be eligible.
LIVE_METRIC_NAMES = {"Revenue", "Gross Margin", "Operating Income"}


class _FakeQuery:
    def __init__(self, table):
        self._table = table
        self._ticker = None
        self._not_ticker = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        if column == "ticker":
            self._ticker = value
        return self

    def neq(self, column, value):
        if column == "ticker":
            self._not_ticker = value
        return self

    def insert(self, rows):
        self._table.inserted.extend(rows)
        return self

    def execute(self):
        rows = self._table.rows
        if self._ticker is not None:
            rows = [r for r in rows if r.get("ticker") == self._ticker]
        if self._not_ticker is not None:
            rows = [r for r in rows if r.get("ticker") != self._not_ticker]
        return type("Resp", (), {"data": list(rows)})()


class _FakeTable:
    def __init__(self, rows):
        self.rows = rows
        self.inserted = []

    # Each builder call starts a fresh query but inserts land back on the table.
    def select(self, *a, **k):
        return _FakeQuery(self).select(*a, **k)

    def insert(self, rows):
        return _FakeQuery(self).insert(rows)


class _FakeSupabase:
    def __init__(self):
        # Seed financial_metrics with the non-AVGO row so the allowed-metric
        # query has data; AVGO starts empty. valuation_snapshots starts empty.
        self._tables = {
            "financial_metrics": _FakeTable(
                [
                    {"ticker": "NVDA", "metric_name": "Revenue"},
                    {"ticker": "NVDA", "metric_name": "Gross Margin"},
                    {"ticker": "NVDA", "metric_name": "Operating Income"},
                ]
            ),
            "valuation_snapshots": _FakeTable([]),
        }

    def table(self, name):
        return self._tables[name]

    def commit_inserts(self):
        """Move recorded inserts into the readable row set (simulate a write)."""
        for table in self._tables.values():
            table.rows.extend(table.inserted)
            table.inserted = []


def main() -> None:
    # --- Parsing -------------------------------------------------------------
    metrics = extract_js_array(SYNTHETIC_HTML, "METRICS")
    valuations = extract_js_array(SYNTHETIC_HTML, "VALUATIONS")
    assert len(metrics) == 5, metrics
    assert len(valuations) == 2, valuations
    # Bracket inside a string did not truncate the array.
    assert metrics[0]["source_reference"] == "https://sec.gov/avgo [ref]"
    print("Parsing: METRICS/VALUATIONS extracted; string brackets handled.")

    # --- AVGO operating row filtering ---------------------------------------
    avgo_rows = build_avgo_metric_rows(metrics, LIVE_METRIC_NAMES)
    names = {r["metric_name"] for r in avgo_rows}
    assert names == {"Revenue", "Gross Margin"}, names
    # Valuation-derived and empty-period rows excluded.
    assert not (names & VALUATION_METRIC_NAMES)
    # "Some New Metric" excluded (not in the live operating set).
    assert "Some New Metric" not in names
    # Type normalization: whole number -> int, ratio -> float.
    revenue = next(r for r in avgo_rows if r["metric_name"] == "Revenue")
    assert revenue["value"] == 14916000000 and isinstance(revenue["value"], int)
    assert revenue["fiscal_year"] == 2025 and isinstance(revenue["fiscal_year"], int)
    margin = next(r for r in avgo_rows if r["metric_name"] == "Gross Margin")
    assert margin["value"] == 0.68 and isinstance(margin["value"], float)
    # Empty dashboard strings become NULL; non-empty preserved.
    assert revenue["derived_from"] is None
    assert revenue["formula"] is None
    assert revenue["source_reference"] == "https://sec.gov/avgo [ref]"
    assert margin["requires_manual_review"] == "yes"
    assert margin["formula"] == "Gross Profit / Revenue"
    print("Filtering: only live operating AVGO metrics kept; provenance preserved.")

    # --- Valuation row mapping ----------------------------------------------
    valuation_rows = build_valuation_rows(valuations)
    avgo_val = next(r for r in valuation_rows if r["ticker"] == "AVGO")
    assert avgo_val["share_price"] == 418.91
    assert avgo_val["shares_outstanding"] == 4734668184
    assert avgo_val["market_cap"] == 1983432750434.44
    assert avgo_val["manually_reviewed"] == "Yes"
    assert avgo_val["debt_measure"] == "gross_principal"
    nvda_val = next(r for r in valuation_rows if r["ticker"] == "NVDA")
    assert nvda_val["notes"] is None  # empty string -> NULL
    print("Valuation mapping: numeric strings parsed, manual-review flag kept.")

    # --- Dry run writes nothing ---------------------------------------------
    fake = _FakeSupabase()
    dry = run_backfill(fake, SYNTHETIC_HTML, confirm=False)
    assert dry["confirmed"] is False
    assert dry["metrics"]["to_insert"] == 2, dry
    assert dry["metrics"]["inserted"] == 0
    assert dry["valuations"]["to_insert"] == 2, dry
    assert not fake._tables["financial_metrics"].inserted
    assert not fake._tables["valuation_snapshots"].inserted
    print("Dry run: reports 2 metrics + 2 valuations to insert; writes nothing.")

    # --- Confirmed run inserts the missing rows -----------------------------
    confirmed = run_backfill(fake, SYNTHETIC_HTML, confirm=True)
    assert confirmed["metrics"]["inserted"] == 2, confirmed
    assert confirmed["valuations"]["inserted"] == 2, confirmed
    # Never touched the non-AVGO seed rows.
    inserted_metrics = fake._tables["financial_metrics"].inserted
    assert all(r["ticker"] == "AVGO" for r in inserted_metrics)
    fake.commit_inserts()
    print("Confirmed run: inserted 2 AVGO metrics + 2 valuations; no NVDA writes.")

    # --- Rerun is idempotent -------------------------------------------------
    rerun = run_backfill(fake, SYNTHETIC_HTML, confirm=True)
    assert rerun["metrics"]["inserted"] == 0, rerun
    assert rerun["metrics"]["skipped"] == 2, rerun
    assert rerun["valuations"]["inserted"] == 0, rerun
    assert rerun["valuations"]["skipped"] == 2, rerun
    print("Idempotency: rerun inserts nothing; all rows skipped.")

    print("\nAll static_dashboard_backfill tests passed.")


if __name__ == "__main__":
    main()
