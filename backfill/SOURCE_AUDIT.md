# Bundle D backfill — source audit

Three lanes, kept visibly separate in `target_fundamentals_v1.csv`:

| Lane | Fields | extraction_method | Who produces it |
|---|---|---|---|
| SOURCED | TTM revenue, prior TTM revenue, TTM gross profit, TTM CFO, TTM capex, cash, STI, total debt, shares outstanding | `sec_xbrl_api` (official SEC companyconcept API; accession numbers + URLs recorded per row) | `fetch_target_facts.py` |
| MANUAL | share_price_usd, share_price_date | `manual` (market data for one chosen snapshot date) | Avyukt |
| DERIVED | gross margin, FCF, FCF margin, YoY TTM growth, market cap, EV, EV/TTM revenue | `derived` (formula in `load_target_backfill.py`; computed only when all inputs exist) | loader, at load time |

A value enters Supabase only after the analyst sets `status = reviewed`,
`reviewed_by`, and `reviewed_at` on the row — the loader refuses anything else.

## Prior-TTM regression fix (2026-06-12)

The original `prior_facts = [f for f in facts if f["end"] < cutoff]` filter
included the most-recent annual period (e.g., LSCC FY2025 ending 2026-01-03)
inside the prior-TTM window, causing `ttm_value` to return FY2025 = 523,262k
instead of TTM-ending-April-2025 = 488,736k. Fix: changed cutoff to
`current_ttm_end − 350 days`, ensuring the prior-TTM base annual is ≥1 year
old. LSCC re-confirmed: all six SOURCE_AUDIT values reproduced exactly.

## Audited entries (full fetch, 2026-06-12)

### LSCC — Lattice Semiconductor (CIK 0000855658) — validated sample

TTM window ends 2026-04-04. All values USD thousands.

| Input | Value (k) | TTM formula |
|---|---|---|
| TTM revenue | 574,009 | FY2025 523,262 + Q1FY26 170,897 − Q1FY25 120,150 |
| Prior TTM revenue | 488,736 | FY2024 509,401 + Q1FY25 120,150 − Q1FY24 140,815 |
| TTM gross profit | 392,847 | same filing set |
| TTM CFO | 193,470 | same |
| TTM capex | 44,444 | same |
| Cash | 139,956 | instant 2026-04-04 |
| STI | 0 | via MarketableSecuritiesCurrent |
| Total debt | **0** — confirmed from Q1 FY26 10-Q R4.htm (accn 0001437749-26-014686); total liabilities $158,820k operating only (AP, payroll, operating lease, other LT) |
| Shares | 137,007,857 | dei tag, 2026-04-30 |

Derived at load time: gross margin 68.4%, FCF 149,026k (26.0%), YoY +17.4%.

### MTSI — MACOM Technology (CIK 0001493594)

TTM ends 2026-04-03. Revenue via `Revenues`.

| Input | Value (k) |
|---|---|
| TTM revenue | 1,073,816 |
| Prior TTM revenue | 845,205 |
| TTM gross profit | 597,949 |
| TTM CFO | 251,611 |
| TTM capex | 55,179 |
| Cash | 98,521 |
| STI | 566,337 (ShortTermInvestments) |
| Total debt | 340,186 (LongTermDebtNoncurrent + LongTermDebtCurrent) |
| Shares | 76,295,774 |

Derived: GM 55.7%, FCF 196,432k (18.3%), YoY +27.0%.

### SLAB — Silicon Laboratories (CIK 0001038074)

TTM ends 2026-04-04. Revenue via `RevenueFromContractWithCustomerExcludingAssessedTax`.

| Input | Value (k) |
|---|---|
| TTM revenue | 820,550 |
| Prior TTM revenue | 655,725 |
| TTM gross profit | 486,204 |
| TTM CFO | 52,514 |
| TTM capex | 34,907 |
| Cash | 383,089 |
| STI | 55,767 (ShortTermInvestments) |
| Total debt | **0** — confirmed from Q1 FY26 10-Q R2.htm (accn 0001038074-26-000020); total liabilities $167,927k operating only; prior concern about ~$400M convert withdrawn (XBRL confirms zero debt; 2023-maturity convert retired) |
| Shares | 32,981,823 |

Derived: GM 59.3%, FCF 17,607k (2.1%), YoY +25.1%.

### SYNA — Synaptics (CIK 0000817720)

TTM ends 2026-03-28 (June FY offset). Revenue via `RevenueFromContractWithCustomerExcludingAssessedTax`.

| Input | Value (k) |
|---|---|
| TTM revenue | 1,172,000 |
| Prior TTM revenue | 1,038,900 |
| TTM gross profit | 511,100 |
| TTM CFO | 139,000 |
| TTM capex | 42,300 |
| Cash | 404,400 |
| STI | 0 (ShortTermInvestments XBRL FRESH lag=0d — confirmed) |
| Total debt | 836,700 (LongTermDebtNoncurrent) |
| Shares | 38,637,685 |

Derived: GM 43.6%, FCF 96,700k (8.3%), YoY +12.8%.

### RMBS — Rambus (CIK 0000917273) — RESOLVED (re-fetched 2026-06-12)

Revenue via `RevenueFromContractWithCustomerIncludingAssessedTax` (Rambus's
ASC-606 tag). Previously broken on `SalesRevenueNet` which has data only
through 2018. TTM ends 2026-03-31.

| Input | Value (k) |
|---|---|
| TTM revenue | 721,155 |
| Prior TTM revenue | 605,417 |
| TTM gross profit | 573,050 |
| TTM CFO | 365,814 |
| TTM capex | 30,605 |
| Cash | 134,324 |
| STI | 651,815 (AvailableForSaleSecuritiesDebtSecuritiesCurrent) |
| Total debt | **0** — confirmed from Q1 2026 10-Q R2.htm (accn 0001193125-26-186931); total liabilities $139,906k operating only (AP, deferred revenue, EDA licenses, lease) |
| Shares | 108,136,967 |

Derived: GM 79.5% (normal for IP-licensing business), FCF 335,209k (46.5%), YoY +19.1%.

### CRUS — Cirrus Logic (CIK 0000772406) — STI CORRECTED 2026-06-12

TTM ends 2026-03-28 (March FY offset). Revenue via `RevenueFromContractWithCustomerExcludingAssessedTax`.

**STI bug**: `MarketableSecuritiesCurrent` chain entry returned end=2013-12-28 (stale; accn 0000772406-14-000004). Root cause: `fetch_concept()` stopped at first chain entry with ANY facts; `latest_instant()` returned max-date fact with no recency check. Stale accession removed from source_accessions. Correct value from FY2026 10-K R3.htm (accn 0000772406-26-000018, balance sheet line "Marketable securities" current = $86,697k). Long-term marketable securities ($266,160k) are excluded from STI — only current portion used for EV.

| Input | Value (k) |
|---|---|
| TTM revenue | 1,997,379 |
| Prior TTM revenue | 1,896,077 |
| TTM gross profit | 1,054,172 |
| TTM CFO | 650,598 |
| TTM capex | 13,988 |
| Cash | 800,930 |
| STI | **86,697** (CORRECTED from 215,792; source: FY2026 10-K R3.htm, accn 0000772406-26-000018) |
| Total debt | **0** — LineOfCredit=$0 in FY2026 10-K (current period, XBRL lag=0d); no other debt line in balance sheet |
| Shares | 50,582,893 |

Derived: GM 52.8%, FCF 636,610k (31.9%), YoY +5.3%.

### ALGM — Allegro MicroSystems (CIK 0000866291, corrected from stub 0001866001)

TTM ends 2026-03-27 (March FY offset). Revenue via `RevenueFromContractWithCustomerExcludingAssessedTax`. Only 2 accessions (one 10-K, one 10-Q) — newer company with less XBRL history.

| Input | Value (k) |
|---|---|
| TTM revenue | 890,096 |
| Prior TTM revenue | 725,006 |
| TTM gross profit | 411,970 |
| TTM CFO | 163,069 |
| TTM capex | 38,176 |
| Cash | 168,753 |
| STI | **0** — no STI line in Q1 FY26 10-Q R2.htm; only Restricted cash $6,604k present |
| Total debt | 287,276 gross face value: $1,530k current + $285,746k noncurrent (LongTermDebt tag $280,884k is net of issuance costs) |
| Shares | 186,222,406 |

Derived: GM 46.3%, FCF 124,893k (14.0%), YoY +22.8%.

### POWI — Power Integrations (CIK 0000833640)

TTM ends 2026-03-31. Revenue via `Revenues`.

| Input | Value (k) |
|---|---|
| TTM revenue | 446,283 |
| Prior TTM revenue | 432,814 |
| TTM gross profit | 240,352 |
| TTM CFO | 105,177 |
| TTM capex | 20,668 |
| Cash | 63,390 |
| STI | 193,814 (ShortTermInvestments) |
| Total debt | **0** — confirmed from Q1 2026 10-Q R2.htm (accn 0000833640-26-000078); total liabilities $98,881k operating only |
| Shares | 55,719,984 |

Derived: GM 53.9%, FCF 84,509k (18.9%), YoY +3.1%.

### SMTC — Semtech (CIK 0000088941)

TTM ends 2026-04-26 (Jan FY offset). Revenue via `RevenueFromContractWithCustomerExcludingAssessedTax`. STI via `AvailableForSaleSecuritiesDebtSecuritiesCurrent`.

| Input | Value (k) |
|---|---|
| TTM revenue | 1,089,933 |
| Prior TTM revenue | 954,242 |
| TTM gross profit | 562,319 |
| TTM CFO | 189,527 |
| TTM capex | 16,305 |
| Cash | 163,310 |
| STI | 0 (tag resolved, value 0) — verify |
| Total debt | 491,982 (LongTermDebtNoncurrent + LongTermDebtCurrent) |
| Shares | 93,151,168 |

Derived: GM 51.6%, FCF 173,222k (15.9%), YoY +14.2%.

### AMBA — Ambarella (CIK 0001280263) — STI CORRECTED 2026-06-12

TTM ends 2026-04-30 (Jan FY offset). Revenue via `RevenueFromContractWithCustomerExcludingAssessedTax`.

**STI bug**: `MarketableSecuritiesCurrent` chain entry returned end=2014-07-31 (stale; accn 0001193125-14-335010). Same root cause as CRUS: no recency guard in `latest_instant()`. Stale accession removed. Correct value from Q1 FY27 10-Q R2.htm (accn 0001193125-26-253198, balance sheet line "Marketable debt securities" current = $163,357k; XBRL tag `AvailableForSaleSecuritiesDebtSecuritiesCurrent`, lag=0d).

| Input | Value (k) |
|---|---|
| TTM revenue | 405,187 |
| Prior TTM revenue | 316,264 |
| TTM gross profit | 238,319 |
| TTM CFO | 33,092 |
| TTM capex | 1,952 |
| Cash | 114,443 |
| STI | **163,357** (CORRECTED from 38,265; source: Q1 FY27 10-Q R2.htm, accn 0001193125-26-253198) |
| Total debt | **0** — confirmed from Q1 FY27 10-Q R2.htm (accn 0001193125-26-253198); total liabilities $189,020k operating only |
| Shares | 43,868,185 |

Derived: GM 58.8%, FCF 31,140k (7.7%), YoY +28.1%.

### MXL — MaxLinear (CIK 0001288469)

TTM ends 2026-03-31. Revenue via `RevenueFromContractWithCustomerExcludingAssessedTax`.

| Input | Value (k) |
|---|---|
| TTM revenue | 508,896 |
| Prior TTM revenue | 361,192 |
| TTM gross profit | 290,867 |
| TTM CFO | 22,147 |
| TTM capex | 11,993 |
| Cash | 61,077 |
| STI | 0 (no STI line in Q1 2026 10-Q R2.htm; only restricted cash $1,426k current + $27,429k LT — not STI) |
| Total debt | 123,773 (LongTermDebtNoncurrent — confirmed from R2.htm balance sheet) |
| Shares | 89,545,959 |

Derived: GM 57.2%, FCF 10,154k (2.0%), YoY +40.9%.

### SITM — SiTime Corporation (CIK 0001451809) — RESOLVED (re-fetched 2026-06-12)

**Prior entry "BALANCE SHEET BLANKED" was incorrect** — SITM is SiTime Corp
(oscillator/timing ICs, Sunnyvale CA), NOT Silicon Motion Technology (flash
controller, Cayman Islands). US issuer filing 10-K/10-Q with XBRL.

SiTime uses non-standard XBRL tags: cash via
`CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents` (ASC-230
reconciliation line; balance sheet R2.htm confirms no separate restricted
cash line — restricted component negligible). STI via
`DebtSecuritiesHeldToMaturityAmortizedCostAfterAllowanceForCreditLossCurrent`
(HTM current portion at amortized cost — fair value not materially different).

TTM ends 2026-03-31.

| Input | Value (k) |
|---|---|
| TTM revenue | 379,913 |
| Prior TTM revenue | 229,989 |
| TTM gross profit | 211,605 |
| TTM CFO | 103,305 |
| TTM capex | 49,034 |
| Cash | 498,476 (pure cash; restricted negligible) |
| STI | 290,188 (HTM current at amortized cost) |
| Total debt | **0** — confirmed from Q1 2026 10-Q R2.htm (accn 0001451809-26-000041); last XBRL debt tags from 2020 (stale/inactive); total liabilities $133,879k operating only |
| Shares | 26,396,828 |

Derived: GM 55.7%, FCF 54,271k (14.3%), YoY +65.2%.

### CRDO — Credo Technology (CIK 0001807794)

TTM ends 2026-01-31 (April FY offset). Revenue via `RevenueFromContractWithCustomerExcludingAssessedTax`. Very high YoY (226%) is consistent with CRDO's hyper-growth trajectory — verify against filings.

| Input | Value (k) |
|---|---|
| TTM revenue | 1,068,138 |
| Prior TTM revenue | 327,532 |
| TTM gross profit | 724,470 |
| TTM CFO | 339,872 |
| TTM capex | 56,178 |
| Cash | 1,220,464 |
| STI | 81,000 (ShortTermInvestments) |
| Total debt | **0** — confirmed from FY26 Q3 10-Q R2.htm (accn 0001628280-26-014017); total liabilities $188,453k operating only |
| Shares | 184,449,940 |

TTM verified: FY2025 $436,775k + 9mo FY2026 $898,113k − 9mo FY2025 $266,750k = **$1,068,138k**. Prior TTM: FY2024 $192,970k + 9mo FY2025 $266,750k − 9mo FY2024 $132,188k = **$327,532k**. YoY **+226.1%** confirmed.

Derived: GM 67.8%, FCF 283,694k (26.6%), YoY +226.1%.

### ALAB — Astera Labs (CIK 0001736297, corrected from stub 0001736946)

TTM ends 2026-03-31. Revenue via `RevenueFromContractWithCustomerExcludingAssessedTax`. STI via `AvailableForSaleSecuritiesDebtSecuritiesCurrent`. YoY 104.2% is the first full comparison year post-IPO — valid.

| Input | Value (k) |
|---|---|
| TTM revenue | 1,001,444 |
| Prior TTM revenue | 490,474 |
| TTM gross profit | 760,991 |
| TTM CFO | 383,400 |
| TTM capex | 40,591 |
| Cash | 148,285 |
| STI | 1,036,189 (AvailableForSaleSecuritiesDebtSecuritiesCurrent — confirmed from Q1 FY26 10-Q R2.htm as "Marketable securities") |
| Total debt | **0** — confirmed from Q1 FY26 10-Q R2.htm (accn 0001736297-26-000020); total liabilities $165,267k operating only |
| Shares | 171,407,939 |

Derived: GM 76.0%, FCF 342,809k (34.2%), YoY +104.2%.
