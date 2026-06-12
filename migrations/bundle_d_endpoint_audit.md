# Bundle D — coverage_tier endpoint audit

Once target companies are inserted, every place that reads `companies` and
assumes "the watchlist 5" must filter `coverage_tier = 'acquirer'` — otherwise
the dashboard suddenly shows 19 companies. Audit of `table("companies")` call
sites (line numbers as of the handoff snapshot):

| Location | Endpoint / use | Action |
|---|---|---|
| `app/main.py:267` | `GET /companies` | **Filter to acquirer** (feeds sidebar, filings filter, brief tabs). Add `?tier=` param later if targets should be browsable. |
| `app/main.py:342` | `GET /companies/{ticker}` | Allow both tiers (a target detail page is harmless); include `coverage_tier` in payload. |
| `app/main.py:409` | `GET /overview` | **Filter to acquirer** (totals would otherwise count targets with zero pipeline data). |
| `app/main.py:497` | `GET /admin` area company lookup | Verify usage; default filter to acquirer. |
| `app/main.py:629` | `GET /peers` | **Filter to acquirer** (peer table is the watchlist 5 by design). |
| `app/main.py:673` | `GET /peers/trends` | **Filter to acquirer**. |
| `src/claim_promotion.py:41` | promotion ticker map | Safe either way (keyed by existing claims), but filter to acquirer for clarity. |
| `src/claude_narrative_import.py:187` | import validation | Leave both tiers — a future `ma_screen_memo` import references targets. |
| `src/report_packet.py:163` | packet exporter | Leave both tiers (D4 pair packets need targets). |
| `src/research_report.py:271` | report engine | Leave acquirer-only for now (reports are acquirer products). |

Frontend: ticker tabs (`/briefs/latest`, `/reports/latest`), the filings
filter, and the sidebar Companies section all read `GET /companies`, so the
backend filter covers them. The **static fallback ticker lists** in the
frontend stay as the 5 acquirers — no change needed.

Tests to add/extend: `test_api_companies.py` (acquirer-only default),
`test_api_overview.py` (totals exclude targets), `test_api_peers.py`
(5 rows exactly after target insert).
