# Bundle D backfill — methodology note

## Minimum inputs per scoring component (from `src/ma_screen.py`)

| Component | Target inputs | Acquirer inputs |
|---|---|---|
| Affordability | enterprise_value | cash, ttm_free_cash_flow, ttm_operating_income, total_debt (already in production tables) |
| Relative size | enterprise_value | market_cap (already present) |
| Financial quality | gross_margin, free_cash_flow_margin, yoy_revenue_growth (rank-based vs target universe) | — |
| Valuation reasonableness | ev_to_ttm_revenue (rank-based) | — |

So the **smallest reliable backfill** per target is a single latest-TTM
snapshot — TTM revenue (+ prior TTM for YoY), TTM gross profit, TTM CFO and
capex (→ FCF), cash + STI, total debt, shares outstanding, and one manually
entered share price. **No historical quarterly pipeline is needed for v1**;
the rank-based components compare targets to each other at one point in time.
This is deliberately lighter than the 8-quarter plan in the original scope —
the scoring formula does not require history, so v1 does not build it.

## TTM construction (deterministic, as-reported)

`TTM = latest annual filing value + post-FY YTD stub − matching prior-year
stub`, all three taken directly from XBRL duration facts (340–380-day
durations count as annual). Prior-year TTM for YoY uses the same formula
shifted back one year. No interpolation, no calendarization: if a piece is
absent, the metric is null and the score's `coverage` drops visibly.
Non-December fiscal year-ends produce TTM windows ending on different dates;
this is disclosed, not adjusted away.

## Derived formulas (computed by the loader only from reviewed inputs)

gross_margin = TTM GP / TTM revenue · FCF = TTM CFO − TTM capex ·
fcf_margin = FCF / TTM revenue · yoy = TTM rev / prior TTM rev − 1 ·
market_cap = price × shares · EV = market_cap + total debt − (cash + STI) ·
ev_to_ttm_revenue = EV / TTM revenue. A derived value is computed only when
every input exists.

## Storage mapping (compatible with `src/ma_screen.py`)

* `financial_metrics`: one row per metric, `fiscal_quarter = "TTM"`, metric
  names identical to the acquirer convention (`TTM Revenue`, `Gross Margin`,
  `Free-Cash-Flow Margin`, `YoY Revenue Growth`, `Cash and Cash
  Equivalents`, `Total Debt`) so the run engine builds acquirer and target
  input dicts with the same accessor.
* `valuation_snapshots`: one manually reviewed row per target with
  `market_cap`, `cash`, `total_debt`, `enterprise_value`, dated and flagged
  `manually_reviewed = true` — same discipline as the five acquirer
  snapshots already live.

## Valuation and comparability disclosures

**EV formula — gross debt.**  Enterprise value is computed as
`market_cap + total_debt − (cash + STI)`.  `total_debt` is the gross face
value of outstanding debt (current + non-current long-term debt as reported in
XBRL), not net of unamortised issuance costs.  Where XBRL returns the net
carrying value (e.g. ALGM), the gross face value is used instead; the
difference is noted in the source_audit.

**EV formula — cash deduction includes short-term investments.**  The cash
deduction is `cash_and_cash_equivalents + short_term_investments (STI)`.  Both
are taken from the balance sheet as reported.  Cash and STI are each zero when
the company holds no such asset; they are never imputed.

**SiTime (SITM) — HTM securities treated as cash-like.**  SiTime classifies
its short-term securities as held-to-maturity (HTM) at amortised cost under
`DebtSecuritiesHeldToMaturityAmortizedCostAfterAllowanceForCreditLossCurrent`.
These are included in the STI line and subtracted from EV.  HTM amortised cost
may differ from fair value, but the difference is not separately disclosed in
XBRL and is expected to be immaterial for screening purposes.  Similarly,
SiTime's cash figure is sourced from `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents`;
the balance sheet shows no separate restricted-cash line, so the restricted
component is treated as negligible.

**Strategic-fit and regulatory notes are qualitative only.**  Any commentary
on product-line fit, regulatory risk, or integration complexity in
SOURCE_AUDIT.md or the screener output is a qualitative disclosure.  These
observations do not enter the numeric scoring formula; they are surfaced for
analyst judgement only.

**TTM windows are not calendar-aligned.**  Targets with non-December fiscal
year-ends (SYNA: June; CRUS/ALGM: March; SMTC/AMBA: January; CRDO: April)
produce TTM periods ending on different calendar dates.  The TTM formula is
applied consistently across all companies on a filing-relative basis.  No
calendarisation or stub-period adjustment is made; the date-misalignment is
disclosed in screener output and should be considered when comparing multiples
across the target universe.

## Guardrails carried over

Public SEC filings + clearly labelled manual market data only; sourced /
manual / derived lanes never mixed; nothing fabricated — missing stays
missing and is reported; nothing written to Supabase without `--confirm` and
a per-row analyst review gate; existing acquirer data and the five-company
public outputs untouched.
