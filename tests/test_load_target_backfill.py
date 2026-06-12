"""Regression tests: load_target_backfill idempotency and PostgREST page-cap fix.

Background
----------
The original loader queried *all* financial_metrics rows to build the set of
tickers that already exist:

    supabase.table("financial_metrics").select("ticker").execute()

PostgREST silently caps unfiltered results at 1,000 rows.  The five acquirer
tickers (AMD, AVGO, INTC, NVDA, QCOM) collectively hold 1,000 metric rows.
When the 98 target rows were inserted they sat beyond the cap, so the existence
check returned an empty set for all 14 target tickers — meaning a second
``--confirm`` run would re-insert every row instead of skipping them.

Fix: scope the query to ``ticker IN (csv_tickers)``.  That returns at most 14
rows regardless of total table size, and the cap can never hide them.

These tests verify that contract without a live database.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

CSV_PATH = Path(__file__).parent.parent / "backfill" / "target_fundamentals_v1.csv"

TARGET_TICKERS = [
    "LSCC", "MTSI", "SLAB", "SYNA", "RMBS", "CRUS", "ALGM", "POWI",
    "SMTC", "AMBA", "MXL", "SITM", "CRDO", "ALAB",
]


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _supabase_mock(existing_tickers: list[str]) -> MagicMock:
    """Minimal Supabase mock whose financial_metrics.select().in_() chain
    returns only the rows whose ticker is in *both* existing_tickers and the
    requested filter list — mirroring real PostgREST behaviour."""
    mock_sb = MagicMock()

    def _in_side_effect(col, requested):
        matched = [{"ticker": t} for t in existing_tickers if t in requested]
        chain = MagicMock()
        chain.execute.return_value.data = matched
        return chain

    (mock_sb.table.return_value
             .select.return_value
             .in_.side_effect) = _in_side_effect

    # insert / snapshot insert: return a no-op mock
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()
    return mock_sb


# ---------------------------------------------------------------------------
# Test 1 — the regression: demonstrate that skipping the IN filter causes
# target rows to be invisible when the table holds ≥1,000 unrelated rows
# ---------------------------------------------------------------------------

class TestPageCapRegression:
    """Proves that the old unfiltered query misses target tickers when the
    table already contains 1,000 acquirer rows, and that the fixed query
    does not."""

    def _setup_mock_with_1000_acquirers_and_14_targets(self) -> MagicMock:
        mock_sb = MagicMock()

        # 1,000 acquirer rows (FAKE ticker fills the cap)
        unfiltered_rows = [{"ticker": "FAKE"} for _ in range(1000)]
        # 14 target rows are present in the DB but beyond the cap
        all_target_rows = [{"ticker": t} for t in TARGET_TICKERS]

        def _select_side_effect(cols):
            chain = MagicMock()

            def _in_side_effect(col, requested_tickers):
                # Filtered path: returns the correct subset
                matched = [r for r in all_target_rows
                           if r["ticker"] in requested_tickers]
                inner = MagicMock()
                inner.execute.return_value.data = matched
                return inner

            chain.in_.side_effect = _in_side_effect
            # Unfiltered path: capped at 1,000 acquirer rows, targets invisible
            chain.execute.return_value.data = unfiltered_rows
            return chain

        mock_sb.table.return_value.select.side_effect = _select_side_effect
        return mock_sb

    def test_unfiltered_query_misses_targets_beyond_1000_row_cap(self):
        """Without IN filter, a 1,000-row cap hides the 14 target rows."""
        mock_sb = self._setup_mock_with_1000_acquirers_and_14_targets()

        # Old (broken) path: no .in_() filter
        existing_broken = {
            r["ticker"] for r in (
                mock_sb.table("financial_metrics")
                       .select("ticker")
                       .execute().data or []
            )
        }
        # None of the 1,000 capped rows are target tickers
        assert not (existing_broken & set(TARGET_TICKERS)), (
            "Old unfiltered query must not find any target ticker "
            "when the table has ≥1,000 unrelated rows"
        )

    def test_in_filtered_query_finds_all_targets_regardless_of_cap(self):
        """With IN filter, all 14 target rows are found even when 1,000
        acquirer rows sit ahead of them in the default ordering."""
        mock_sb = self._setup_mock_with_1000_acquirers_and_14_targets()
        csv_tickers = TARGET_TICKERS

        # Fixed path: .in_("ticker", csv_tickers) applied
        existing_fixed = {
            r["ticker"] for r in (
                mock_sb.table("financial_metrics")
                       .select("ticker")
                       .in_("ticker", csv_tickers)
                       .execute().data or []
            )
        }
        assert existing_fixed == set(TARGET_TICKERS), (
            "Fixed IN-filtered query must detect all 14 target tickers"
        )


# ---------------------------------------------------------------------------
# Test 2 — verify main() calls .in_() with exactly the CSV tickers
# ---------------------------------------------------------------------------

class TestInFilterContract:
    def test_existence_check_calls_in_with_csv_tickers(self):
        """main() must call .in_('ticker', csv_tickers) — not a bare .execute()
        with no filter — so the page cap can never hide existing rows.

        Reload the module BEFORE entering the patch context so the patch is not
        overwritten by the ``from src.database import get_supabase_client``
        re-execution that reload triggers."""
        import load_target_backfill, importlib
        importlib.reload(load_target_backfill)

        mock_sb = _supabase_mock(existing_tickers=[])

        with patch("load_target_backfill.get_supabase_client", return_value=mock_sb), \
             patch("sys.argv", ["load_target_backfill.py"]):
            load_target_backfill.main()

        select_chain = mock_sb.table.return_value.select.return_value
        in_calls = select_chain.in_.call_args_list
        assert len(in_calls) == 1, (
            f"Expected exactly one .in_() call; got {len(in_calls)}"
        )
        col_arg, tickers_arg = in_calls[0].args
        assert col_arg == "ticker"
        assert set(tickers_arg) == set(TARGET_TICKERS), (
            "IN filter must cover exactly the 14 CSV target tickers"
        )


# ---------------------------------------------------------------------------
# Test 3 — idempotency: all tickers already present → zero inserts
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_all_tickers_present_inserts_zero_rows(self):
        """When all 14 target tickers already have financial_metrics rows,
        main() with --confirm must insert nothing."""
        import load_target_backfill, importlib
        importlib.reload(load_target_backfill)

        mock_sb = _supabase_mock(existing_tickers=TARGET_TICKERS)

        with patch("load_target_backfill.get_supabase_client", return_value=mock_sb), \
             patch("sys.argv", ["load_target_backfill.py", "--confirm"]):
            load_target_backfill.main()

        insert_calls = mock_sb.table.return_value.insert.call_args_list
        assert insert_calls == [], (
            f"Expected zero inserts when all tickers exist; "
            f"got {len(insert_calls)} insert call(s)"
        )

    def test_dry_run_never_inserts_regardless_of_existing_rows(self):
        """Dry-run mode (no --confirm) must never call insert even when
        all rows are new."""
        import load_target_backfill, importlib
        importlib.reload(load_target_backfill)

        mock_sb = _supabase_mock(existing_tickers=[])  # nothing exists yet

        with patch("load_target_backfill.get_supabase_client", return_value=mock_sb), \
             patch("sys.argv", ["load_target_backfill.py"]):  # no --confirm
            load_target_backfill.main()

        insert_calls = mock_sb.table.return_value.insert.call_args_list
        assert insert_calls == [], (
            "Dry-run must never call insert; "
            f"got {len(insert_calls)} insert call(s)"
        )
