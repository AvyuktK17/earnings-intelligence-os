# Bundle D backfill — instructions for the next Claude Code session

State as of 2026-06-12: D1 schema applied; 5 acquirers + 14 targets in
`companies`; 15 reviewed pairs in `ma_screen_pairs`; backfill machinery built
and LSCC validated end-to-end (see `repo/backfill/SOURCE_AUDIT.md`).

Hard rules carried forward: do not modify the five-company public outputs;
no commits/pushes/deploys; Supabase writes only via `load_target_backfill.py
--confirm` after Avyukt's per-row review; never fabricate a value.

## Exact steps

1. **Export the approved pairs** (read-only): select all rows from
   `ma_screen_pairs` and write them to `backfill/approved_pairs_v1.md`. The
   handoff folder only has the 27-pair draft; the run engine must use the
   real 15. Derive the priority target order = targets appearing in most
   pairs first.
2. **Run the fetch:** `python fetch_target_facts.py` (needs `SEC_USER_AGENT`
   in `.env`; ~10 min, rate-limit friendly). Re-run with `--ticker LSCC`
   first and confirm it reproduces the hand-validated numbers in
   SOURCE_AUDIT.md exactly — that's the regression check on the TTM logic.
   If any ticker reports `fetch_failed` or long `missing_fields`, check the
   tag fallback chains in `CONCEPTS` (issuer-specific debt/STI tags are the
   likely culprits) and extend them narrowly.
3. **Unit-convention check (one-time):** read one acquirer row from
   `financial_metrics` (e.g. AVGO Gross Margin) and set `MARGIN_AS_PERCENT`
   / `USD_SCALE` in `load_target_backfill.py` to match. Also confirm the
   `fiscal_quarter = "TTM"` convention doesn't collide with
   `src.quantitative.is_operating_row` filtering (TTM rows have no real
   quarter — decide with Avyukt whether the run engine reads them via a
   dedicated accessor instead; do NOT let them leak into `/metrics`).
4. **Avyukt's review pass:** he checks each CSV row against the linked
   filings (especially every debt and STI figure), enters share_price /
   share_price_date for one snapshot date across all 14, then sets
   `status=reviewed`, `reviewed_by`, `reviewed_at`.
5. **Load:** `python load_target_backfill.py` (dry run), review the printed
   derived values, then `--confirm`.
6. **Stop.** The run engine (`ma_screen_runs` population + API) is the next
   bundle item, not this one.

## Open flags (from MISSING_INPUTS.md)

Share prices are manual for all 14; ALAB may have an honest-null YoY (recent
IPO); fiscal-year offsets (SYNA/CRUS/ALGM/SMTC/AMBA/CRDO) mean non-aligned
TTM windows — disclose, don't adjust; debt tags for ALGM/SMTC/MXL need extra
care.
