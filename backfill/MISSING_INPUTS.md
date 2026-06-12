# Bundle D backfill — missing-input report (updated 2026-06-12 post-refetch)

## Blocking all 14 rows until provided

**Share prices (all 14 targets) — MANUAL.** Pick one snapshot date and enter
`share_price_usd` + `share_price_date` per target in the CSV. Without prices
there is no market cap → no EV → affordability, relative size, and valuation
reasonableness are honest nulls for every target.

---

## Previously critical failures — both resolved by refetch

### RMBS — fixed: revenue now sourced from current filings

Root cause: `RevenueFromContractWithCustomerExcludingAssessedTax` and
`Revenues` returned nothing for Rambus; the chain fell through to
`SalesRevenueNet` which has data only through 2018. Fix: added
`RevenueFromContractWithCustomerIncludingAssessedTax` (Rambus's ASC-606 tag)
as the second entry in the `revenue` fallback chain. Re-fetched TTM ends
2026-03-31; revenue = 721,155k; gross margin = 79.5% (consistent with
licensing-heavy business). RMBS is now `fetched_pending_review`.

### SITM — fixed: identified as SiTime Corporation, not Silicon Motion

SiTime Corp (CIK 0001451809, SIC 3674) is a US issuer filing 10-K/10-Q.
The balance-sheet XBRL gap was an issuer-specific tag choice, not a foreign-
filer issue. SiTime:
- Tags cash as `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents`
  (the ASC-230 cash-flow reconciliation line) rather than the standard
  `CashAndCashEquivalentsAtCarryingValue`. Added to the `cash` fallback chain.
- Tags short-term securities as `DebtSecuritiesHeldToMaturityAmortizedCostAfterAllowanceForCreditLossCurrent`
  (held-to-maturity, current portion). Added to the `sti` fallback chain.

Re-fetched: cash = 498,476k; STI = 290,188k. Both values are noted in the CSV
with the tag names for analyst verification (verify restricted cash is minimal;
HTM is at amortized cost not fair value). SITM is now `fetched_pending_review`.

### SLAB — clarified: debt-free; prior concern withdrawn

My note about "~$400M convertible notes issued March 2025" was incorrect.
XBRL shows `ProceedsFromIssuanceOfLongTermDebt = 0` for all of FY2025
(ending Jan 3, 2026) and no convertible balance with a post-2023 date. Their
prior 2023-maturity convert was retired. `ConvertibleNotesPayable`, `SeniorNotes`,
and `NotesPayable` were added to the fallback chain for completeness; re-fetch
confirmed zero debt, consistent with the prior-period XBRL evidence.

---

## Per-target status after balance-sheet verification (all 14) — updated 2026-06-12

All debt and STI verifications completed against balance-sheet R-pages. Only share prices remain missing.

| Ticker | Missing | Status | Notes |
|---|---|---|---|
| LSCC | price | READY | Debt=0 confirmed R4.htm. STI=0 confirmed. Price $142.86 PLAUSIBLE (AMI acq +7.9% on Jun 11). |
| MTSI | price | READY | All fundamentals confirmed FRESH XBRL. |
| SLAB | price | READY | Debt=0 confirmed R2.htm. Prior convert concern withdrawn. |
| SYNA | price | READY | STI=0 XBRL FRESH lag=0d. Debt $836,700k confirmed. |
| RMBS | price | READY | Debt=0 confirmed R2.htm. STI $651,815k confirmed. |
| CRUS | price | READY | STI CORRECTED 215792→86697 (stale 2013 tag). Debt=0 confirmed. |
| ALGM | price | READY | STI=0 confirmed R2.htm (no STI line). Debt $287,276k gross confirmed. |
| POWI | price | READY | Debt=0 confirmed R2.htm. STI $193,814k confirmed. |
| SMTC | price | READY | STI=0 confirmed. Debt $491,982k confirmed (single LT line; footnote needed for instrument split). |
| AMBA | price | READY | STI CORRECTED 38265→163357 (stale 2014 tag). Debt=0 confirmed. |
| MXL | price | READY | STI=0 confirmed (no STI line; restricted cash only). Debt $123,773k confirmed. |
| SITM | price | READY | Debt=0 confirmed R2.htm (last XBRL debt tags from 2020). Cash $498,476k (restricted negligible). STI $290,188k HTM confirmed. |
| CRDO | price | READY | Debt=0 confirmed R2.htm. TTM +226.1% YoY verified via annual+stub method. |
| ALAB | price | READY | Debt=0 confirmed R2.htm. STI $1,036,189k confirmed. |

## Price cross-check results (2026-06-12)

| Ticker | CSV Price | Cross-check | Flag |
|---|---|---|---|
| LSCC | $142.86 | +7.9% on Jun 11 (AMI acq) from ~$132.38; Jun 12 pulled back to ~$131 | PLAUSIBLE |
| MTSI | $374.76 | Web search confirmed +5.7% to $374.76 | CONFIRMED |
| SLAB | $218.90 | Not cross-checked | NOT CROSS-CHECKED |
| SYNA | $136.08 | Not cross-checked | NOT CROSS-CHECKED |
| RMBS | $144.47 | Jun 10 range $138.37-$149.24; plausible | PLAUSIBLE |
| CRUS | $162.93 | Not cross-checked | NOT CROSS-CHECKED |
| ALGM | **$44.54** | CORRECTED from $47.96; confirmed close $44.54 (range $44.00-$47.05) | CORRECTED |
| POWI | $77.76 | Not cross-checked | NOT CROSS-CHECKED |
| SMTC | **$157.27** | CORRECTED from $163.57; confirmed close $157.27 | CORRECTED |
| AMBA | $65.80 | Cross-check range $63.80-$64.53 (high=$64.53); $65.80 is $1.27 above reported high | **DISCREPANCY — verify** |
| MXL | $81.09 | Not cross-checked | NOT CROSS-CHECKED |
| SITM | $721.24 | Second source range $670.87-$736.00; $721.24 is within range | PLAUSIBLE |
| CRDO | $264.76 | Macrotrends cross-check $263.66 (delta $1.10) | CONFIRMED |
| ALAB | $337.99 | CORRECTED from $367.47; confirmed range $334.75-$342.00 | CORRECTED |

**Remaining price items for analyst**: SLAB, SYNA, CRUS, POWI, MXL (not cross-checked); AMBA (discrepancy — needs second source). All others confirmed or plausible.

---

## Staleness & comparability flags

* **Fiscal-year offsets:** SYNA (Jun), CRUS/ALGM (Mar), SMTC/AMBA (Jan),
  CRDO (Apr) — TTM windows end on different dates. Disclose, don't adjust.
* **ALAB:** prior-TTM YoY growth of 104.2% is the first full comparison year
  post-IPO (TTM ending 2026-03-31 vs prior TTM ending 2025-03-31). Valid.
* **CRDO:** YoY +226.1% consistent with hyper-growth trajectory — cross-check
  against most recent earnings release before reviewing.
* **RMBS GM 79.5%:** normal for an IP licensing business; do not flag as anomalous.
* **SITM cash:** sourced from `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents`
  — confirm restricted cash is negligible on the balance sheet.
* **SITM STI:** sourced from HTM current securities at amortized cost — confirm
  fair value is not materially different (likely immaterial for EV purposes).
* **Unit convention (resolved 2026-06-12):** `MARGIN_AS_PERCENT` in
  `load_target_backfill.py` corrected to `False` (decimals, matching acquirer rows).
  `USD_SCALE = 1_000.0` is correct.

---

## CIK corrections (applied by fetch script from SEC ticker map)

| Ticker | Stub CIK (wrong) | SEC ticker-map CIK (correct) |
|---|---|---|
| ALGM | 0001866001 | 0000866291 |
| ALAB | 0001736946 | 0001736297 |
