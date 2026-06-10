"""Idempotent backfill of audited static-dashboard data.

The original public semiconductor research dashboard
(https://avyuktk17.github.io/semiconductor-research/) embeds two manually
reviewed datasets as JavaScript arrays:

* ``METRICS`` — the historical quarterly operating dataset for all five
  monitored tickers, including AVGO (which is missing from the live
  ``financial_metrics`` table);
* ``VALUATIONS`` — point-in-time, manually reviewed valuation snapshots for
  all five tickers.

This module parses those arrays from a locally downloaded copy of the HTML and
backfills only what is missing:

* AVGO rows are inserted into the existing ``financial_metrics`` table, scoped
  to the operating metric names that already exist for the other tickers (the
  valuation-derived metric names and empty-period rows are excluded — valuation
  data belongs in ``valuation_snapshots``);
* all five valuation snapshots are upserted into ``valuation_snapshots``.

Existing reviewed metrics for QCOM, AMD, NVDA, and INTC are never overwritten.
Reruns are idempotent: rows already present are skipped. No AI calls are made
and no credentials are exposed.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Valuation-derived metric names embedded in the dashboard METRICS array that
# are point-in-time (empty fiscal period) and must NOT enter the quarterly
# financial_metrics operating series — they are captured by valuation_snapshots.
VALUATION_METRIC_NAMES = frozenset(
    {
        "Share Price",
        "Market Capitalization",
        "Enterprise Value",
        "EV / TTM Revenue",
        "Price / TTM FCF",
        "FCF Yield",
    }
)

# Columns carried over verbatim from the dashboard METRICS rows. The live
# financial_metrics table has exactly these columns.
FINANCIAL_METRIC_COLUMNS = (
    "company",
    "ticker",
    "fiscal_year",
    "fiscal_quarter",
    "metric_name",
    "value",
    "unit",
    "extraction_method",
    "source_reference",
    "derived_from",
    "requires_manual_review",
    "formula",
)

# Numeric columns on valuation_snapshots that arrive as strings in the
# dashboard VALUATIONS array.
_VALUATION_NUMERIC_COLUMNS = (
    "share_price",
    "shares_outstanding",
    "market_cap",
    "cash",
    "total_debt",
    "enterprise_value",
)

# Date columns on valuation_snapshots.
_VALUATION_DATE_COLUMNS = (
    "share_price_date",
    "shares_outstanding_source_date",
)

# Text columns on valuation_snapshots.
_VALUATION_TEXT_COLUMNS = (
    "ticker",
    "debt_measure",
    "source",
    "manually_reviewed",
    "notes",
)


def extract_js_array(html: str, name: str) -> list[dict]:
    """Extract a ``const <name> = [...]`` JSON array from dashboard HTML.

    The dashboard serializes each dataset as a literal JSON array assigned to a
    ``const``. This balances brackets from the first ``[`` after the
    declaration so embedded ``[``/``]`` inside strings are handled correctly.

    Raises:
        ValueError: If the named array cannot be found or parsed.
    """
    match = re.search(r"const\s+%s\s*=\s*" % re.escape(name), html)
    if not match:
        raise ValueError(f"Could not find a 'const {name} = ...' array in the HTML.")

    start = html.index("[", match.end())
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(html)):
        char = html[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return json.loads(html[start : index + 1])
    raise ValueError(f"Unterminated array literal for '{name}'.")


def parse_dashboard(html: str) -> dict[str, list[dict]]:
    """Parse both audited datasets from the dashboard HTML."""
    return {
        "metrics": extract_js_array(html, "METRICS"),
        "valuations": extract_js_array(html, "VALUATIONS"),
    }


def _normalize_number(raw: Any) -> int | float | None:
    """Convert a dashboard numeric string to int (when whole) or float."""
    if raw is None or raw == "":
        return None
    value = float(raw)
    if value.is_integer():
        return int(value)
    return value


def _clean_text(raw: Any) -> str | None:
    """Map empty dashboard strings to NULL, otherwise keep the text."""
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def build_avgo_metric_rows(
    metrics: list[dict],
    allowed_metric_names: set[str],
) -> list[dict]:
    """Build AVGO ``financial_metrics`` rows from the dashboard METRICS array.

    Only operating rows are kept: ticker AVGO, a non-empty fiscal period, and a
    metric name that already exists in the live table for the other tickers.
    Valuation-derived and empty-period rows are excluded. Source references,
    extraction methods, formulas, derivations, and manual-review flags are
    preserved verbatim.
    """
    rows: list[dict] = []
    for row in metrics:
        if row.get("ticker") != "AVGO":
            continue
        fiscal_year = str(row.get("fiscal_year", "")).strip()
        fiscal_quarter = str(row.get("fiscal_quarter", "")).strip()
        if not fiscal_year or not fiscal_quarter:
            continue
        metric_name = row.get("metric_name")
        if metric_name in VALUATION_METRIC_NAMES:
            continue
        if metric_name not in allowed_metric_names:
            continue
        rows.append(
            {
                "company": _clean_text(row.get("company")),
                "ticker": "AVGO",
                "fiscal_year": int(fiscal_year),
                "fiscal_quarter": fiscal_quarter,
                "metric_name": metric_name,
                "value": _normalize_number(row.get("value")),
                "unit": _clean_text(row.get("unit")),
                "extraction_method": _clean_text(row.get("extraction_method")),
                "source_reference": _clean_text(row.get("source_reference")),
                "derived_from": _clean_text(row.get("derived_from")),
                "requires_manual_review": _clean_text(
                    row.get("requires_manual_review")
                ),
                "formula": _clean_text(row.get("formula")),
            }
        )
    return rows


def build_valuation_rows(valuations: list[dict]) -> list[dict]:
    """Build ``valuation_snapshots`` rows from the dashboard VALUATIONS array.

    Numeric strings are converted to numbers; empty strings become NULL. The
    manual-review flag, source references, debt measure, and notes are
    preserved verbatim.
    """
    rows: list[dict] = []
    for row in valuations:
        built: dict[str, Any] = {}
        for column in _VALUATION_TEXT_COLUMNS:
            built[column] = _clean_text(row.get(column))
        for column in _VALUATION_DATE_COLUMNS:
            built[column] = _clean_text(row.get(column))
        for column in _VALUATION_NUMERIC_COLUMNS:
            built[column] = _normalize_number(row.get(column))
        rows.append(built)
    return rows


def _existing_operating_metric_names(supabase) -> set[str]:
    """Distinct metric names already stored for the non-AVGO tickers."""
    response = (
        supabase.table("financial_metrics")
        .select("metric_name")
        .neq("ticker", "AVGO")
        .execute()
    )
    return {row["metric_name"] for row in response.data}


def _existing_avgo_metric_keys(supabase) -> set[tuple]:
    """Natural keys of AVGO rows already in financial_metrics."""
    response = (
        supabase.table("financial_metrics")
        .select("fiscal_year, fiscal_quarter, metric_name")
        .eq("ticker", "AVGO")
        .execute()
    )
    return {
        (row["fiscal_year"], row["fiscal_quarter"], row["metric_name"])
        for row in response.data
    }


def _existing_valuation_keys(supabase) -> set[tuple]:
    """Natural keys (ticker, share_price_date) of stored valuation snapshots."""
    response = (
        supabase.table("valuation_snapshots")
        .select("ticker, share_price_date")
        .execute()
    )
    return {(row["ticker"], row["share_price_date"]) for row in response.data}


def run_backfill(supabase, html: str, confirm: bool = False) -> dict:
    """Backfill audited AVGO metrics and valuation snapshots idempotently.

    When ``confirm`` is False, no writes occur — the returned summary is a dry
    run describing what would change. When True, only the missing rows are
    inserted; existing AVGO metrics and existing valuation snapshots are never
    overwritten in a way that loses reviewed data.

    Returns:
        A summary dict with per-table inserted / skipped / updated counts and
        the candidate row totals.
    """
    parsed = parse_dashboard(html)

    allowed_metric_names = _existing_operating_metric_names(supabase)
    avgo_rows = build_avgo_metric_rows(parsed["metrics"], allowed_metric_names)
    existing_metric_keys = _existing_avgo_metric_keys(supabase)

    metrics_to_insert: list[dict] = []
    metrics_skipped = 0
    for row in avgo_rows:
        key = (row["fiscal_year"], row["fiscal_quarter"], row["metric_name"])
        if key in existing_metric_keys:
            metrics_skipped += 1
        else:
            metrics_to_insert.append(row)

    valuation_rows = build_valuation_rows(parsed["valuations"])
    existing_valuation_keys = _existing_valuation_keys(supabase)

    valuations_to_insert: list[dict] = []
    valuations_skipped = 0
    for row in valuation_rows:
        key = (row["ticker"], row["share_price_date"])
        if key in existing_valuation_keys:
            valuations_skipped += 1
        else:
            valuations_to_insert.append(row)

    if confirm:
        if metrics_to_insert:
            supabase.table("financial_metrics").insert(metrics_to_insert).execute()
        if valuations_to_insert:
            supabase.table("valuation_snapshots").insert(
                valuations_to_insert
            ).execute()

    return {
        "confirmed": confirm,
        "metrics": {
            "candidates": len(avgo_rows),
            "inserted": len(metrics_to_insert) if confirm else 0,
            "to_insert": len(metrics_to_insert),
            "skipped": metrics_skipped,
        },
        "valuations": {
            "candidates": len(valuation_rows),
            "inserted": len(valuations_to_insert) if confirm else 0,
            "to_insert": len(valuations_to_insert),
            "skipped": valuations_skipped,
        },
    }
