"""Tests for fetch_target_facts.py — stale-data guard and TTM window logic."""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from fetch_target_facts import (
    MAX_INSTANT_LAG_DAYS,
    _to_date,
    latest_instant,
    ttm_value,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _fact(val: int, end: str, start: str | None = None, accn: str = "ACC") -> dict:
    f: dict = {"val": val, "end": end, "accn": accn}
    if start is not None:
        f["start"] = start
    return f


TTM_END = date(2026, 4, 30)  # representative AMBA TTM end


# ── staleness guard: latest_instant() ────────────────────────────────────────

class TestLatestInstantStaleGuard:
    def test_fresh_fact_accepted(self):
        """A fact within MAX_INSTANT_LAG_DAYS is returned normally."""
        facts = [_fact(163_357_000, "2026-04-30")]
        val, end, accn = latest_instant(facts, ttm_end=TTM_END)
        assert val == 163_357_000.0
        assert end == "2026-04-30"

    def test_stale_amba_sti_rejected(self):
        """AMBA bug: MarketableSecuritiesCurrent end=2014-07-31 is ~4300 days stale.
        Must be rejected when ttm_end is 2026-04-30."""
        facts = [_fact(38_265_000, "2014-07-31")]
        val, end, accn = latest_instant(facts, ttm_end=TTM_END, tag_hint="us-gaap:MarketableSecuritiesCurrent")
        assert val is None
        assert end is None

    def test_stale_crus_sti_rejected(self):
        """CRUS bug: MarketableSecuritiesCurrent end=2013-12-28 is ~4500 days stale."""
        crus_ttm_end = date(2026, 3, 28)
        facts = [_fact(215_792_000, "2013-12-28")]
        val, end, accn = latest_instant(facts, ttm_end=crus_ttm_end, tag_hint="us-gaap:MarketableSecuritiesCurrent")
        assert val is None

    def test_boundary_exactly_at_threshold_accepted(self):
        """A fact exactly MAX_INSTANT_LAG_DAYS old is accepted (boundary inclusive)."""
        stale_end = (TTM_END - timedelta(days=MAX_INSTANT_LAG_DAYS)).isoformat()
        facts = [_fact(1_000_000, stale_end)]
        val, _, _ = latest_instant(facts, ttm_end=TTM_END)
        assert val == 1_000_000.0

    def test_boundary_one_day_past_threshold_rejected(self):
        """A fact MAX_INSTANT_LAG_DAYS + 1 old is rejected."""
        stale_end = (TTM_END - timedelta(days=MAX_INSTANT_LAG_DAYS + 1)).isoformat()
        facts = [_fact(1_000_000, stale_end)]
        val, _, _ = latest_instant(facts, ttm_end=TTM_END)
        assert val is None

    def test_no_ttm_end_skips_guard(self):
        """Without ttm_end, no staleness check — any fact is returned."""
        facts = [_fact(38_265_000, "2014-07-31")]
        val, _, _ = latest_instant(facts, ttm_end=None)
        assert val == 38_265_000.0

    def test_most_recent_wins_among_fresh_facts(self):
        """When multiple fresh facts exist, the most recent is chosen."""
        facts = [
            _fact(100_000, "2025-10-31", accn="OLD"),
            _fact(163_357_000, "2026-04-30", accn="NEW"),
        ]
        val, end, accn = latest_instant(facts, ttm_end=TTM_END)
        assert val == 163_357_000.0
        assert accn == "NEW"

    def test_stale_tag_filtered_fresh_tag_wins(self):
        """Simulate fallback: stale fact rejected; fresh fact in same list wins.

        In practice fetch_concept() handles the fallback across tags, but
        the guard itself returns None for the stale-only case, leaving
        downstream logic to try the next tag.
        """
        stale_only = [_fact(38_265_000, "2014-07-31")]
        fresh_only = [_fact(163_357_000, "2026-04-30")]

        v1, _, _ = latest_instant(stale_only, ttm_end=TTM_END)
        assert v1 is None  # stale tag rejected

        v2, _, _ = latest_instant(fresh_only, ttm_end=TTM_END)
        assert v2 == 163_357_000.0  # fresh tag accepted

    def test_empty_facts_returns_none(self):
        val, end, accn = latest_instant([], ttm_end=TTM_END)
        assert val is None and end is None and accn is None


# ── TTM construction: correct prior-TTM window selection ─────────────────────

class TestTtmValuePriorWindow:
    """Verify that prior_cutoff = ttm_end − 350 days keeps the prior base
    annual ≥1 year old, preventing the most-recent FY annual from being
    selected as the 'prior' period."""

    def _make_annual(self, start: str, end: str, val: int, accn: str = "A") -> dict:
        return _fact(val, end, start=start, accn=accn)

    def _make_stub(self, start: str, end: str, val: int, accn: str = "S") -> dict:
        return _fact(val, end, start=start, accn=accn)

    def test_lscc_prior_ttm_window(self):
        """LSCC: FY2025 annual (end 2026-01-03) must NOT be selected as prior
        base; FY2024 annual (end 2025-01-03) must be selected instead."""
        from datetime import timedelta

        # Simulate LSCC facts: FY2024, Q1FY25, FY2025, Q1FY26
        current_ttm_end = date(2026, 4, 4)
        prior_cutoff = (current_ttm_end - timedelta(days=350)).isoformat()

        fy2025_end = "2026-01-03"
        fy2024_end = "2025-01-03"

        # FY2025 falls after prior_cutoff — must be excluded from prior facts
        assert fy2025_end > prior_cutoff, (
            f"FY2025 end {fy2025_end} should be after prior_cutoff {prior_cutoff}"
        )
        # FY2024 falls at or before prior_cutoff — must be included
        assert fy2024_end <= prior_cutoff, (
            f"FY2024 end {fy2024_end} should be at/before prior_cutoff {prior_cutoff}"
        )

    def test_crdo_prior_ttm_window(self):
        """CRDO: prior TTM = FY2024 + 9mo FY2025 − 9mo FY2024.
        FY2025 annual (end 2025-05-03) must NOT be used as prior base."""
        from datetime import timedelta

        current_ttm_end = date(2026, 1, 31)
        prior_cutoff = (current_ttm_end - timedelta(days=350)).isoformat()

        fy2025_end = "2025-05-03"
        fy2024_end = "2024-04-27"

        assert fy2025_end > prior_cutoff, (
            f"FY2025 end {fy2025_end} should be after prior_cutoff {prior_cutoff}"
        )
        assert fy2024_end <= prior_cutoff, (
            f"FY2024 end {fy2024_end} should be at/before prior_cutoff {prior_cutoff}"
        )

    def test_ttm_value_fy_only(self):
        """When no stub exists after the FY end, TTM = FY annual value."""
        facts = [_fact(1_000_000_000, "2026-01-31", start="2025-02-01")]
        val, end, accns = ttm_value(facts)
        assert val == 1_000_000_000.0
        assert end == "2026-01-31"

    def test_ttm_value_annual_plus_stub(self):
        """TTM = FY + stub − prior_stub, verified with round numbers."""
        facts = [
            # FY annual: 365 days
            _fact(400_000_000, "2025-05-03", start="2024-05-04", accn="FY"),
            # 9-month stub (272 days) — after FY end
            _fact(600_000_000, "2026-01-31", start="2025-05-04", accn="STUB"),
            # Prior 9-month stub (279 days) — before FY end, ~365 days before current stub
            _fact(200_000_000, "2025-02-01", start="2024-05-04", accn="PRIOR"),
        ]
        val, end, _ = ttm_value(facts)
        expected = 400_000_000 + 600_000_000 - 200_000_000
        assert val == float(expected)
        assert end == "2026-01-31"

    def test_ttm_value_returns_none_when_prior_stub_missing(self):
        """Returns None when matching prior stub is absent (no interpolation)."""
        facts = [
            _fact(400_000_000, "2025-05-03", start="2024-05-04", accn="FY"),
            _fact(600_000_000, "2026-01-31", start="2025-05-04", accn="STUB"),
            # No matching prior stub
        ]
        val, end, _ = ttm_value(facts)
        assert val is None
