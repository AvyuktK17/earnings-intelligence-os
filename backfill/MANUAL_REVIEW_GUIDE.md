# Bundle D — Manual Review Guide

Snapshot date: **2026-06-11**. Reviewed by: _________________. Reviewed at: _________________.

All sourced values are in `target_fundamentals_v1.csv`. Suggested share prices are in
`suggested_share_prices.csv`. The machine-readable checklist is `manual_review_checklist.csv`.
After completing each section, set `reviewed_yes_no = Y` and fill `reviewer_input` /
`reviewer_note` in the checklist CSV. Then set `status = reviewed`, `reviewed_by`, and
`reviewed_at` in `target_fundamentals_v1.csv` for each approved row.

---

## How to approve a row

1. Complete every checklist item for that ticker (all `reviewed_yes_no = Y`).
2. Open `target_fundamentals_v1.csv`.
3. Enter `share_price_usd` and `share_price_date = 2026-06-11`.
4. If any field was wrong, correct it in the CSV now.
5. Set `status = reviewed`, `reviewed_by = <your name/email>`, `reviewed_at = <ISO timestamp>`.
6. The loader (`load_target_backfill.py`) will refuse any row that skips these three fields.

---

## Section 1 — Share prices (all 14 tickers)

All prices are June 11, 2026 closing prices from Yahoo Finance (retrieved via
stockanalysis.com on 2026-06-12). **`suggested_share_prices.csv` has been updated
with cross-check results.** Key findings:

- **ALAB $367.47 was WRONG → corrected to $337.99.** stockanalysis.com returned a
  value close to the June 3 all-time high ($372.37). Web search confirms June 11
  close was $337.99 (range $334.75–$342.00). This is an ~8.7% error.
- **MTSI $374.76 CONFIRMED** by web search ("MACOM shares rose 5.7% to $374.76").
- **CRDO $264.76 CONFIRMED** by Macrotrends cross-check ($263.66 — delta $1.10).
- **SITM $721.24 PLAUSIBLE** — within second-source range ($670.87–$736.00).
- **LSCC $142.86 UNCONFIRMED** — cross-check shows Jun 12 price ~$131; the Jun 11
  close may be correct (gap-up day) but verify independently before accepting.
- All other 9 tickers: not independently cross-checked. Verify against Yahoo Finance.

| Ticker | Suggested close (2026-06-11) | Flag | YF history URL |
|---|---|---|---|
| LSCC | $142.86 | ⚠ UNCONFIRMED | https://finance.yahoo.com/quote/LSCC/history/ |
| MTSI | $374.76 | ✓ CONFIRMED | https://finance.yahoo.com/quote/MTSI/history/ |
| SLAB | $218.90 | — not cross-checked | https://finance.yahoo.com/quote/SLAB/history/ |
| SYNA | $136.08 | — not cross-checked | https://finance.yahoo.com/quote/SYNA/history/ |
| RMBS | $144.47 | — not cross-checked | https://finance.yahoo.com/quote/RMBS/history/ |
| CRUS | $162.93 | — not cross-checked | https://finance.yahoo.com/quote/CRUS/history/ |
| ALGM | $47.96  | — not cross-checked | https://finance.yahoo.com/quote/ALGM/history/ |
| POWI | $77.76  | — not cross-checked | https://finance.yahoo.com/quote/POWI/history/ |
| SMTC | $163.57 | — not cross-checked | https://finance.yahoo.com/quote/SMTC/history/ |
| AMBA | $65.80  | — not cross-checked | https://finance.yahoo.com/quote/AMBA/history/ |
| MXL  | $81.09  | — not cross-checked | https://finance.yahoo.com/quote/MXL/history/ |
| SITM | $721.24 | ~ PLAUSIBLE | https://finance.yahoo.com/quote/SITM/history/ |
| CRDO | $264.76 | ✓ CONFIRMED | https://finance.yahoo.com/quote/CRDO/history/ |
| ALAB | **$337.99** *(corrected from $367.47)* | ✓ CORRECTED | https://finance.yahoo.com/quote/ALAB/history/ |

---

## Section 2 — Debt = 0 verifications (6 tickers)

XBRL returned no debt tag for these six. The project rule is explicit: **never treat
a missing tag as zero without a balance-sheet check**. For each, open the filing link,
go to the Condensed Consolidated Balance Sheets, and confirm the long-term debt lines.

### LSCC — Lattice Semiconductor (CIK 855658)

- **Filing:** Q1 FY2026 10-Q, ended 2026-04-04
- **EDGAR index:** https://www.sec.gov/Archives/edgar/data/855658/000143774926014686/0001437749-26-014686-index.htm
- **Line item:** "Long-term debt, current portion" + "Long-term debt, net of current portion"
- **Fetched value in CSV:** NULL
- **Expected:** $0 (Lattice has been debt-free since 2022)
- **Reviewer action:** Confirm both lines are $0. If $0, enter `0` in `total_debt_usd_k` and mark reviewed. If non-zero, enter the actual balance.

### SLAB — Silicon Laboratories (CIK 1038074)

- **Filing:** Q1 FY2026 10-Q, ended 2026-04-04
- **EDGAR index:** https://www.sec.gov/Archives/edgar/data/1038074/000103807426000020/0001038074-26-000020-index.htm
- **Line item:** "Convertible notes, net" (noncurrent) + "Current portion of long-term debt"
- **Fetched value in CSV:** NULL
- **Expected:** $0 (prior 2023-maturity converts were retired; no new issuance in FY2025 XBRL)
- **Reviewer action:** Confirm both lines are $0 or absent. Note: SLAB issued a new revolving credit facility — confirm the revolver is undrawn.

### RMBS — Rambus (CIK 917273)

- **Filing:** Q1 2026 10-Q, ended 2026-03-31
- **EDGAR index:** https://www.sec.gov/Archives/edgar/data/917273/000119312526186931/0001193125-26-186931-index.htm
- **Line item:** "Long-term debt" (noncurrent) + current portion
- **Fetched value in CSV:** NULL
- **Expected:** $0 (Rambus is a licensing company; has not carried financial debt in recent years)
- **Reviewer action:** Confirm $0. If non-zero, enter the amount.

### CRUS — Cirrus Logic (CIK 772406)

- **Filing:** Q4 / FY2026 10-K, ended 2026-03-28
- **EDGAR index:** https://www.sec.gov/Archives/edgar/data/772406/000077240626000018/0000772406-26-000018-index.htm
- **Line item:** "Long-term debt" (noncurrent) + current portion
- **Fetched value in CSV:** NULL
- **Expected:** $0 (Cirrus Logic has been debt-free; has a revolving credit facility that is typically undrawn)
- **Reviewer action:** Confirm $0 and that the revolver is undrawn.

### POWI — Power Integrations (CIK 833640)

- **Filing:** Q1 2026 10-Q, ended 2026-03-31
- **EDGAR index:** https://www.sec.gov/Archives/edgar/data/833640/000083364026000078/0000833640-26-000078-index.htm
- **Line item:** "Long-term debt" (noncurrent) + current portion
- **Fetched value in CSV:** NULL
- **Expected:** $0 (Power Integrations is debt-free)
- **Reviewer action:** Confirm $0.

### AMBA — Ambarella (CIK 1280263)

- **Filing:** Q1 FY2027 10-Q, ended 2026-04-30
- **EDGAR index:** https://www.sec.gov/Archives/edgar/data/1280263/000119312526253198/0001193125-26-253198-index.htm
- **Line item:** "Long-term debt" (noncurrent) + current portion
- **Fetched value in CSV:** NULL
- **Expected:** $0 (Ambarella is debt-free)
- **Reviewer action:** Confirm $0.

---

## Section 3 — STI = 0 verifications (4 tickers)

XBRL returned a literal value of `0.0` for these four. Confirm the balance sheet
does not carry short-term investments under a different line name.

### LSCC — Q1 FY26 10-Q (same filing as Section 2)

- **Line item:** "Short-term investments" or "Marketable securities, current"
- **Fetched value:** 0.0 (via `MarketableSecuritiesCurrent` tag)
- **Reviewer action:** Confirm the balance sheet shows no current investment balance. If $0, set reviewed. If non-zero under a different label, enter the amount.

### SYNA — Q3 FY26 10-Q, ended 2026-03-28 (CIK 817720)

- **EDGAR index:** https://www.sec.gov/Archives/edgar/data/817720/000081772026000036/0000817720-26-000036-index.htm
- **Line item:** "Short-term investments"
- **Fetched value:** 0.0 (via `ShortTermInvestments` tag)
- **Reviewer action:** Confirm $0. Synaptics historically held some short-term securities — verify the current quarter.

### SMTC — Q1 FY27 10-Q, ended 2026-04-26 (CIK 88941)

- **EDGAR index:** https://www.sec.gov/Archives/edgar/data/88941/000008894126000013/0000088941-26-000013-index.htm
- **Line item:** "Short-term investments" or "Available-for-sale securities, current"
- **Fetched value:** 0.0 (via `AvailableForSaleSecuritiesDebtSecuritiesCurrent` tag)
- **Reviewer action:** Confirm $0.

### MXL — Q1 2026 10-Q, ended 2026-03-31 (CIK 1288469)

- **EDGAR index:** https://www.sec.gov/Archives/edgar/data/1288469/000128846926000029/0001288469-26-000029-index.htm
- **Line item:** "Short-term investments"
- **Fetched value:** 0.0 (via `ShortTermInvestments` tag)
- **Reviewer action:** Confirm $0. MaxLinear is cash-constrained; zero STI is expected.

---

## Section 4 — Debt amount verifications (3 tickers)

XBRL resolved a debt value for these three. Confirm the amount matches the
balance sheet total (noncurrent + current portions).

### MTSI — MACOM Technology (CIK 1493594)

- **Filing:** Q1 FY2026 10-Q, ended 2026-04-03
- **EDGAR index:** https://www.sec.gov/Archives/edgar/data/1493594/000149359426000028/0001493594-26-000028-index.htm
- **Fetched value:** 340,186k USD (LongTermDebtNoncurrent + LongTermDebtCurrent)
- **Line item:** "Long-term debt, net" (noncurrent) + "Current portion of long-term debt"
- **Reviewer action:** Sum the two balance sheet lines and confirm total ≈ $340,186k. Note the debt instrument name (e.g., term loan, senior notes) in reviewer_note.

### SMTC — Semtech (CIK 88941)

- **Filing:** Q1 FY2027 10-Q, ended 2026-04-26 (same filing as Section 3)
- **EDGAR index:** https://www.sec.gov/Archives/edgar/data/88941/000008894126000013/0000088941-26-000013-index.htm
- **Fetched value:** 491,982k USD
- **Line item:** Sum all debt-like lines: term loan, convertible notes (noncurrent + current)
- **Reviewer action:** Confirm the total (noncurrent + current) matches $491,982k. Semtech has a complex capital structure (term loan + converts) — make sure both are captured.

### ALGM — Allegro MicroSystems (CIK 866291)

- **Filing:** Q1 FY2026 10-Q, ended 2026-03-27
- **EDGAR index:** https://www.sec.gov/Archives/edgar/data/866291/000119312526233537/0001193125-26-233537-index.htm
- **Fetched value:** 287,276k USD (LongTermDebtNoncurrent)
- **Line item:** "Long-term debt, net of current portion" + "Current portion of long-term debt"
- **Reviewer action:** Confirm total ≈ $287,276k. Note: ALGM has a term loan; confirm current-portion is included (if current portion was separately tagged, the script would have captured it via `LongTermDebtCurrent` — confirm it is reflected in this total or add separately).

---

## Section 5 — ALGM STI (missing tag)

- **Filing:** Q1 FY2026 10-Q (same as Section 4)
- **EDGAR index:** https://www.sec.gov/Archives/edgar/data/866291/000119312526233537/0001193125-26-233537-index.htm
- **Line item:** "Short-term investments" or "Marketable securities, current"
- **Fetched value:** NULL (no XBRL tag resolved)
- **Reviewer action:** Open the balance sheet. If the line is absent or $0, enter `0` in `sti_usd_k`. If non-zero, enter the amount.

---

## Section 6 — SITM balance sheet (4 items)

SiTime Corp uses non-standard XBRL tags; all four items need confirmation against
the actual 10-Q balance sheet.

- **Filing:** Q1 2026 10-Q, ended 2026-03-31 (CIK 1451809)
- **EDGAR index:** https://www.sec.gov/Archives/edgar/data/1451809/000145180926000041/0001451809-26-000041-index.htm

### 6a. Cash (498,476k) — restricted cash component

- **Tag used:** `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents`
- **Line item:** "Cash and cash equivalents" + any "Restricted cash" line on the balance sheet
- **Reviewer action:** Note the unrestricted cash + equivalents line separately. If restricted cash > $5M, subtract it and enter the adjusted figure in `cash_usd_k`.

### 6b. Cash balance confirmation

- **Line item:** Total cash and cash equivalents balance on the balance sheet
- **Fetched value:** 498,476k
- **Reviewer action:** Confirm the balance sheet line "Cash and cash equivalents" matches $498,476k (or the adjusted unrestricted figure from 6a).

### 6c. STI — held-to-maturity current securities (290,188k)

- **Tag used:** `DebtSecuritiesHeldToMaturityAmortizedCostAfterAllowanceForCreditLossCurrent`
- **Line item:** "Short-term investments" or "Held-to-maturity securities, current" on the balance sheet
- **Fetched value:** 290,188k (amortized cost)
- **Reviewer action:** Confirm the balance sheet carrying value is $290,188k. Check the HTM fair-value disclosure table and note if fair value differs materially from amortized cost (for EV purposes, the difference is usually immaterial).

### 6d. Debt — revolving credit facility

- **Line item:** "Revolving credit facility" or "Long-term debt" on the balance sheet
- **Fetched value:** NULL (appears debt-free)
- **Reviewer action:** Confirm the revolver is $0 drawn and no other financial debt is on the balance sheet. Enter `0` in `total_debt_usd_k`.

---

## Section 7 — CRDO YoY growth sanity check

- **Filing:** FY2026 Q3 10-Q, ended 2026-01-31 (CIK 1807794)
- **EDGAR index:** https://www.sec.gov/Archives/edgar/data/1807794/000162828026014017/0001628280-26-014017-index.htm
- **Fetched TTM revenue:** 1,068,138k (TTM ending 2026-01-31)
- **Fetched prior TTM revenue:** 327,532k (TTM ending 2025-01-31)
- **Computed YoY:** +226.1%
- **Reviewer action:** Open the 10-Q revenue table. Confirm CRDO's revenue for the TTM period ending Jan 2026 is approximately $1.07B and the comparable prior-year TTM (ending Jan 2025) is approximately $328M. This growth rate is consistent with Credo's AI-networking hyper-growth — confirm it reflects real operations, not a restatement or segment change.

---

## Margin convention reminder

Before running `load_target_backfill.py --confirm`, verify once:

```
AVGO Gross Margin in financial_metrics = 0.68  ✓  (decimal, not percent)
```

`MARGIN_AS_PERCENT = False` in `load_target_backfill.py` — **already corrected 2026-06-12**.
`USD_SCALE = 1_000.0` — correct (CSV stores kUSD; Supabase stores full USD).

---

## Section 8 — Data quality corrections (2 tickers)

**These must be corrected in `target_fundamentals_v1.csv` before loading.** The fetch
script's STI fallback chain stopped at an early tag with stale data in both cases.

### AMBA — sti_usd_k: WRONG value, must correct

- **CSV has:** `38,265k` (from `MarketableSecuritiesCurrent`, end=2014-07-31)
- **Correct value:** `163,357k` (from `AvailableForSaleSecuritiesDebtSecuritiesCurrent`,
  end=2026-04-30, accn `0001193125-26-253198` — Q1 FY27 10-Q, CURRENT FILING)
- **Action:** Confirm $163,357k against the Q1 FY27 10-Q balance sheet, then set
  `sti_usd_k = 163357` in `target_fundamentals_v1.csv`.

### CRUS — sti_usd_k: LIKELY WRONG, must verify

- **CSV has:** `215,792k` (from `MarketableSecuritiesCurrent`, end=2013-12-28)
- **Problem:** No STI XBRL tag with current data exists for CRUS in EDGAR. The next
  available tag (`AvailableForSaleSecuritiesDebtSecuritiesCurrent`) was $18,397k in
  2022 — also stale. The 2013 value is almost certainly wrong.
- **Action:** Open the FY2026 10-K (ended 2026-03-28, accn `0000772406-26-000018`),
  find the "Short-term investments" or "Marketable securities, current" line, and
  enter the actual balance in `sti_usd_k`.

---

## Quick-approve candidates (price entry + one balance-sheet look)

After resolving the AMBA and CRUS STI corrections above:

| Ticker | Only remaining items | SEC evidence confidence |
|---|---|---|
| MTSI | Price + confirm debt $340,186k | HIGH — current filing |
| SYNA | Price + confirm STI = 0 | HIGH — current filing |
| SMTC | Price + confirm debt $491,982k + STI = 0 | HIGH — current filing |
| MXL  | Price + confirm debt $123,773k + STI = 0 | MEDIUM — STI last zero Dec 2023 |
| CRUS | Price + confirm debt = 0 + **correct STI** | HIGH for debt; LOW for STI (stale) |
| POWI | Price + confirm debt = 0 | HIGH — FY2025 annual |
| AMBA | Price + confirm debt = 0 + **correct STI to $163,357k** | HIGH |
| CRDO | Price (confirmed) + confirm debt = 0 + verify YoY | HIGH |

ALAB can also be approved quickly once the corrected price ($337.99) is confirmed
and debt = 0 is verified on the balance sheet.

## Rows requiring closer attention

| Ticker | Why | Blocker |
|---|---|---|
| LSCC | Price unconfirmed (~9% above adjacent-day data); STI zero last tagged 2019 | Verify price; check both balance sheet lines |
| SITM | Four balance-sheet items; non-standard XBRL tags | Confirm restricted cash = 0; confirm HTM fair value |
| ALGM | Debt amount sum has fee/gross ambiguity ($287,276k vs $280,884k net); STI unknown | Read debt footnote; read STI balance sheet line |
| SMTC | Debt instrument breakdown not resolvable from XBRL alone | Check 10-Q debt footnote for term loan vs convert split |
| RMBS | Revenue fix applied this session; debt-zero last confirmed Dec 2023 | Verify Q1 2026 10-Q shows no new financing |
| SLAB | Converts retired in 2023; revolving line $0 in FY2025 annual | Confirm Q1 FY26 10-Q shows no new issuance |
| CRUS | STI value is stale 2013 data | Must read FY2026 10-K balance sheet |
| AMBA | STI value is stale 2014 data; correct value is $163,357k | Update CSV before loading |
