# Earnings Intelligence OS — Project Status

## Project goal

Build an Earnings Intelligence OS for semiconductor companies:

* monitor SEC EDGAR automatically;
* detect new filings;
* download and parse filings;
* store documents permanently in Supabase Storage;
* split documents into AI-ready chunks;
* extract evidence-linked draft claims;
* require human review before claims enter trusted research outputs;
* publish trusted claims as versioned earnings briefs;
* expose everything through a research API;
* drive the analyst workflow from a web dashboard.

## Companies monitored

* QCOM
* AMD
* NVDA
* INTC
* AVGO

## Supabase tables

Thirteen tables are in use (the last three added in Bundle B1):

* `companies` — ticker → company_name watchlist
* `financial_metrics` — audited quarterly fundamentals, all five tickers
  (AMD, AVGO, INTC, NVDA, QCOM) × 258 rows = 1,290 rows; columns `company,
  ticker, fiscal_year, fiscal_quarter, metric_name, value, unit,
  extraction_method, source_reference, derived_from, requires_manual_review,
  formula`. 252 quarterly operating rows per ticker (21 metrics × 12
  quarters, FY2023–FY2026) plus 6 embedded valuation-derived rows
  (empty-period) that the quantitative API filters out — valuation lives in
  `valuation_snapshots`. The audited dataset (including AVGO) was restored
  from the original public static dashboard; see "Audited static-data
  backfill" below
* `valuation_snapshots` — manually reviewed point-in-time valuation
  snapshots for all five tickers (`ticker, share_price_date, share_price,
  shares_outstanding, shares_outstanding_source_date, market_cap, cash,
  total_debt, enterprise_value, debt_measure, source, manually_reviewed,
  notes`; unique on `(ticker, share_price_date)`). Dated/audited, **not** a
  live market feed; the API surfaces every row with `is_live = false`
* `filings` — one row per detected filing; lifecycle status, Storage paths, timestamps, processing_error; exhibit columns: `exhibit_processing_status` (`not_checked` / `processed` / `not_found` / `failed`, default `not_checked`), `exhibit_checked_at`, `exhibit_processing_error`, `earnings_release_document_id` → `filing_documents(id)`; extraction columns: `claim_extraction_status` (`not_started` / `pending_review` / `approved` / `failed`, default `not_started`), `claim_extracted_at`, `claim_extraction_error`
* `filing_documents` — exhibit documents (e.g. EX-99.1) per filing; unique on `(accession_number, filename)`
* `filing_chunks` — AI-ready chunks; unique on `(accession_number, document_key, chunk_index)`; primary chunks use `document_key = "primary"`, exhibit chunks use `document_key = "exhibit:{filename}"`
* `proposed_claims` — AI-drafted claims awaiting review; `review_status` is `pending` / `approved` / `edited` / `rejected`; grounded rows have `source_chunk_id`
* `qualitative_claims` — trusted human-reviewed claims; promoted rows carry `proposed_claim_id`, `source_chunk_id`, `document_key`, `promoted_at` (note: this table has **no `id` column** — promoted rows are keyed by `proposed_claim_id`)
* `earnings_briefs` — versioned brief rows; unique versions per accession; stores `markdown_content`, `storage_path`, claim counts, `generated_at`
* `pipeline_runs` — run bookkeeping
* `research_reports` — versioned research reports (deterministic **and**
  imported Claude-assisted narratives); stores `report_type`, `report_status`
  (`human_reviewed_deterministic` for deterministic; `draft` / `reviewed` /
  `superseded` / `rejected` for Claude-assisted; plus `failed`),
  `version_number` (one sequence per `(ticker, report_type)`; unique on
  `(ticker, report_type, version_number)`), `title`, `markdown_content`,
  `html_content`, `pdf_storage_path`, `source_claim_count`,
  `source_metric_count`, `valuation_snapshot_date`, `generator_type`
  (`deterministic` / `claude_assisted`), `generated_at`, and the
  Bundle B2.2 columns `source_report_id` (self-FK), `source_packet_hash`,
  `imported_at`, `reviewed_at`, `reviewer_notes`, `rejection_reason`
* `report_evidence_links` — one row per trusted claim used in a report
  (`research_report_id`, `qualitative_claim_id`, `source_chunk_id`,
  `accession_number`, `document_key`, `section_name`, `supporting_excerpt`)
* `report_generation_runs` — audit row per generation
  (`run_status` running → completed/failed, `report_id`, `error_message`,
  `started_at`, `completed_at`)

## Supabase Storage (private bucket: `filing-documents`)

* `html/{ticker}/{accession}/...` — raw primary HTML
* `parsed/{ticker}/{accession}/...` — parsed primary text
* `html/{ticker}/{accession}/exhibits/{filename}` — raw exhibit HTML
* `parsed/{ticker}/{accession}/exhibits/{filename}.txt` — parsed exhibit text
* `briefs/{ticker}/{accession}/v{n}.md` — versioned earnings briefs
* `reports/{ticker}/{report_type}/v{n}.md` / `.html` / `.pdf` — versioned
  deterministic research reports (lowercase ticker; prior versions preserved)

## GitHub Actions (`.github/workflows/run-monitor.yml`)

* manual `workflow_dispatch` + scheduled cron `17 */6 * * *` (every 6 hours)
* concurrency group `sec-filing-monitor`
* steps:
  1. Run filing monitor (`run_monitor.py`)
  2. Process detected filings (`run_processor.py`)
  3. Process earnings-release exhibits (`run_exhibit_processor.py`, max 3
     filings per run)
  4. Backfill missing Storage paths (`run_backfill.py`)
  5. Backfill missing chunks (`run_chunk_backfill.py`)
  6. List detected filings (`list_filings.py`)
* AI extraction, review, promotion, and brief generation are **not** in the
  workflow — they remain manual by design.

## Ingestion pipeline (complete)

Filing lifecycle: `detected → downloaded → parsed → chunked`.
A filing only reaches `chunked` after HTML download, text parsing, HTML+text
Storage upload, Storage-path persistence, and chunk creation. Failures are
recorded in `processing_error`.

Exhibit support (`src/filing_exhibits.py`, `src/process_filing_exhibit.py`):
discovers the SEC filing index, selects the likely earnings-release exhibit
(EX-99.1), downloads/parses/uploads it, and records it in `filing_documents`
(`process_earnings_release_exhibit` returns the row's
`filing_document_id`). The filename matcher recognizes press-release names
ending in `pr.htm` (NVIDIA's convention) and `99.1` names without a
separator like `q12026991.htm` (AMD's convention). Candidates are ranked
press release / earnings release (tier 1) > financial results (2) >
EX-99.1 marker (3) > slide deck / presentation (4) > other (5), with file
size only breaking ties within a tier — so a small press release always
beats a large slide deck.
Multi-document chunking (`src/filing_chunker.py`) chunks both primary
documents and exhibits idempotently.

## Automated exhibit ingestion (complete)

`src/exhibit_status.py` + `src/process_pending_exhibits.py` +
`run_exhibit_processor.py` (GitHub Actions step 3, batch limit 3):

* selects 8-K filings with `processing_status = "chunked"` and
  `exhibit_processing_status = "not_checked"` (plus `"failed"` only with
  `include_failed=True`), newest filing_date first
* per filing: discover exhibit → download/parse/upload → chunk → mark
  `processed` with `earnings_release_document_id`; no exhibit → mark
  `not_found`; any error → mark `failed` with the error message and continue
  the batch
* status lifecycle: `not_checked` → `processed` / `not_found` / `failed`;
  `processed` and `not_found` rows are never re-inspected
* **chunk-preservation rule:** discovery and ranking always run first; an
  existing document is reused only when its filename exactly matches the
  currently selected best-ranked exhibit (so AVGO's EX-99.1 keeps its
  chunk ids — grounded claims reference them with a RESTRICT foreign key —
  while a filing can still upgrade from a slide deck to a press release);
  on upgrade the filing's `earnings_release_document_id` moves to the new
  document and the previously ingested document and its chunks are kept as
  secondary evidence, never deleted
* never calls Gemini; extraction stays manual (free-quota control and
  analyst oversight)
* live results: AVGO `0001730168-26-000051` (17 chunks), NVDA
  `0001045810-26-000051` `q1fy27pr.htm` (13 chunks), AMD
  `0000002488-26-000072` `q12026991.htm` (21 chunks; upgraded from the
  slide deck, which remains stored as a secondary document), and QCOM
  `0000804328-26-000060` are `processed`; non-earnings 8-Ks are
  `not_found`

## Gemini claim extraction (complete, manual)

* `src/llm_client.py` + `src/claim_extractor.py`; run via `run_claim_extraction.py`
* extraction is grounded: each claim must include a `supporting_excerpt` that
  is a literal substring of a chunk (after whitespace normalization) plus the
  matching `source_chunk_index` / `source_chunk_id`
* claims insert into `proposed_claims` with `review_status = "pending"`;
  rerun-safe via a DELETE scoped to `(accession_number, document_key, pending)`
* Gemini API key in `.env` and GitHub Secrets; never called from the API or tests

## Manual dashboard-triggered claim extraction (complete)

`src/claim_extraction_status.py` + `src/ready_filing_extraction.py`:

* `extract_claims_for_ready_filing(accession_number, max_claims=5)` requires
  an extraction-ready filing (processed exhibit + document id), builds the
  exhibit `document_key`, and reuses the existing grounded extractor
  (`extract_and_store_claims`), which replaces pending drafts only after
  valid new claims exist — failed runs never delete drafts
* filing lifecycle: `not_started` → `pending_review` (successful run) /
  `failed` (error stored, truncated to 500 chars) → `approved` (set by
  promotion when no grounded pending rows remain for the filing)
* quota / rate-limit / availability errors raise
  `ClaimExtractionQuotaError`; other provider errors raise a caller-safe
  `ClaimExtractionError` (raw detail only on the filing row, never to
  callers)
* Gemini stays manual and admin-triggered (free-quota control + analyst
  oversight); nothing is scheduled and GitHub Actions never extracts

## Human review workflow (complete)

* `src/claim_review.py`: `approve_claim`, `approve_claim_with_edits`
  (preserves original `claim_text`, stores `edited_claim_text`), `reject_claim`
* approval/editing require a grounded row (`source_chunk_id` non-null);
  rejection is allowed on any row, including ungrounded legacy rows
* interactive CLI: `review_claims.py`; read-only queue: `list_proposed_claims.py`

## Trusted promotion (complete)

* `src/claim_promotion.py`: `promote_reviewed_claims()` promotes `approved` /
  `edited` grounded claims into `qualitative_claims`, using the reviewer's
  edited wording when present; already-promoted claims are skipped by
  `proposed_claim_id`, so reruns never duplicate; after promotion, any
  affected filing with no grounded pending rows left is marked
  `claim_extraction_status = "approved"` (returned as `approved_filings`)
* CLI: `promote_claims.py`
* 5 trusted AVGO claims are live (proposed_claim_ids 30–34)

## Versioned earnings briefs (complete)

* `src/earnings_brief.py`: builds a markdown brief from trusted grounded
  claims only (pending/rejected drafts never appear); no AI calls
* `src/brief_storage.py`: `generate_and_store_earnings_brief()` assigns the
  next version number, writes `output/briefs/` locally (gitignored), uploads
  to Storage, and inserts an `earnings_briefs` row; prior versions are never
  overwritten
* CLIs: `generate_earnings_brief.py`, `store_earnings_brief.py`
* AVGO 8-K `0001730168-26-000051` brief v1 is persisted (5 trusted claims)

## FastAPI research API (complete)

`app/main.py` — `FastAPI(title="Earnings Intelligence OS API")`; run locally
with `uvicorn app.main:app --reload`. Uses
`src.database.get_supabase_client()` via a single `lru_cache`d client.
Deployed on Render at `https://earnings-intelligence-os-api.onrender.com`.

Authentication (MVP admin token): every write endpoint requires the
`X-Admin-Token` header to match the `ADMIN_API_TOKEN` env var, compared
with `secrets.compare_digest`. Missing/wrong header → 401
("Admin token missing or invalid."); server token unconfigured → generic
500 ("Server configuration error.") that never names the variable. Read
endpoints are public. No user accounts yet.

Read endpoints (public):

* `GET /health` — liveness
* `GET /companies` — watchlist (ticker, company_name, cik, business_model)
  ordered by ticker; feeds the dashboard's filings filter, sidebar
  Companies section, and brief tabs
* `GET /companies/{ticker}` — one company's research-pipeline summary:
  filing + chunked counts, extraction-ready filings (compact rows),
  trusted promoted claim count, latest brief metadata (no markdown body),
  recent filings (10); ticker uppercased; 404 for unknown companies
* `GET /overview` — cross-company dashboard payload: companies/filings/
  extraction-ready/pending-grounded/trusted/brief totals plus one status
  row per company (extraction-ready count, trusted count, latest brief
  version, latest filing date)
* `GET /admin/validate` — the only token-protected GET; returns
  `{"status": "ok"}` for a valid `X-Admin-Token`, 401 otherwise, safe 500
  when the server token is unconfigured; used by the Admin Access panel
  to verify saved tokens without mutations
* `GET /filings?ticker=&status=&limit=` — filing feed, newest first; ticker
  uppercased; `limit` validated with `Query(ge=1, le=100)` (422 outside range)
* `GET /filings/{accession_number}` — filing + `filing_documents` + chunk
  count; 404 if unknown
* `GET /briefs/latest/{ticker}` — latest stored brief; 404 if none
* `GET /review-queue` — grounded pending claims only; ungrounded legacy rows
  (`source_chunk_id` null) are never exposed
* `GET /extraction-ready` — filings with a processed, chunked
  earnings-release exhibit, newest first; each row carries the exhibit
  filename, `document_key`, `chunk_count`, `ready_for_extraction`, plus
  the extraction lifecycle (`claim_extraction_status`,
  `claim_extracted_at`, `claim_extraction_error` — publicly redacted to
  the generic "Claim extraction failed. Retry later or contact the
  administrator." while the raw provider text stays only in Supabase and
  backend logs),
  `pending_grounded_claim_count`, `trusted_promoted_claim_count`, and
  `latest_brief_version` — the queue for manual grounded-claim extraction

Write endpoints (analyst workflow; all require `X-Admin-Token`):

* `POST /review-queue/{claim_id}/approve` — optional `{"reviewer_notes"}`;
  404 unknown claim, 400 ungrounded
* `POST /review-queue/{claim_id}/edit` — requires `{"edited_claim_text"}`
  (422 if empty/missing), optional notes; 404 unknown, 400 ungrounded
* `POST /review-queue/{claim_id}/reject` — optional notes; works on
  ungrounded legacy rows; 404 unknown
* `POST /claims/promote` — runs `promote_reviewed_claims()`; idempotent;
  accepts an optional body `{"ticker", "accession_number"}` to scope
  promotion to one ticker and/or one filing (no body = global mode; the
  dashboard only ever calls the scoped form)
* `POST /briefs/generate` — requires `{"ticker", "accession_number"}`;
  ticker uppercased; 404 unknown filing, 400 when no trusted claims exist
* `POST /extraction-ready/{accession_number}/extract` — manual grounded
  Gemini extraction on the filing's processed exhibit; optional body
  `{"max_claims": 1–10}` (default 5, 422 outside range); 404 unknown
  filing, 400 not extraction-ready, 429 on Gemini quota/rate-limit, safe
  500 otherwise (no keys, stack traces, or raw provider responses); the
  only route that calls Gemini

CORS: `CORSMiddleware` allows browser calls from the origins in the optional
`ALLOWED_ORIGINS` env var (comma-separated; defaults to
`http://localhost:3000`), with credentials and all methods/headers. Verified
with a preflight test (`test_api_cors.py`).

Error mapping: `ValueError` messages starting with "No proposed claim found" /
"No filing found" → 404; other workflow `ValueError`s → 400; Pydantic
validation → 422; unexpected errors → bare 500 with no secrets or stack trace.

Database client hardening: `src/database.py` raises `RuntimeError` (instead
of the old `sys.exit(1)`) when `SUPABASE_URL` / `SUPABASE_SECRET_KEY` are
missing, so a misconfigured API process returns controlled 500s instead of
dying; the message names the variables but never their values.

## Frontend analyst dashboard (complete, deployed)

`frontend/` — Next.js (App Router, stable 16.2.7) + TypeScript + Tailwind v4,
scaffolded with create-next-app (`src/` directory, npm, ESLint). Only extra
runtime dependency: `react-markdown`. Dark, data-dense research-terminal
styling with a left sidebar (Overview / Filings / Review Queue / Latest
Brief). Deployed on Vercel at
`https://earnings-intelligence-os.vercel.app` with
`NEXT_PUBLIC_API_BASE_URL` pointing at the Render API.

* setup: `cd frontend && npm install && cp .env.example .env.local`
* run: `npm run dev` (backend must be running on
  `NEXT_PUBLIC_API_BASE_URL`, default `http://localhost:8000`)
* the browser talks only to the FastAPI service, never to Supabase
* shared typed client in `src/lib/api.ts` with explicit loading and error
  states on every page
* **Admin Access panel** at the bottom of the sidebar: token input with
  Save/Clear. Saved tokens are verified through `GET /admin/validate` and
  the indicator shows `connected` / `invalid token` / `not connected`
  (plus `checking…` / `unverified` transients). The token lives in browser
  session storage only (never committed, never in a `NEXT_PUBLIC_`
  variable) and is attached as `X-Admin-Token` to protected POSTs and the
  validate route only; a 401 surfaces as "Admin token missing or invalid."

Routes:

* `/` — cross-company overview from `GET /overview`: six stat cards
  (companies, filings tracked, extraction ready, pending review, trusted
  claims, stored briefs) + per-company status table (ticker → company
  page, extraction-ready count, trusted count, latest brief link, latest
  filing date) + latest-filings table
* `/companies/[ticker]` — company research page: name/ticker/CIK/business
  model header, four summary cards, latest-brief panel with "View latest
  brief" link, extraction-ready filings table with extraction badges,
  recent filings table; clean states for unknown tickers and missing
  briefs; the sidebar has a dynamic Companies section from
  `GET /companies` and ticker cells in filings tables link here
* `/filings` — feed with ticker/status/limit filters and status badges;
  the ticker list loads dynamically from `GET /companies` (with a static
  fallback if the endpoint fails)
* `/filings/[accessionNumber]` — full filing metadata, timestamps,
  processing error, document list with Storage flags, chunk count
* `/extraction-ready` — per-filing cards with exhibit filename, document
  key, chunk count, an exhibit badge plus a lifecycle trail
  (`not_started › pending_review › approved`, failed shown as a badge),
  pending/trusted claim counts, and latest brief version; admin-only
  **Extract Claims** button (requires a saved token, disabled while
  running) that calls the protected extract endpoint, shows a compact
  success note with a "Review drafted claims" link to `/review-queue`, a
  dedicated quota message on 429, and the redacted extraction error for
  failed filings; an admin-only **Promote reviewed claims** button appears
  when the filing is `pending_review` with zero grounded pending drafts —
  the terminal promotion that flips the filing to `approved` (the Review
  Queue can no longer trigger it because its per-filing group disappears
  once the last draft is reviewed); approved filings with a stored brief
  show a "View latest brief" link; an admin-only **Generate first brief**
  button appears for approved filings with trusted claims but no stored
  brief (calls `POST /briefs/generate` — no Swagger needed for the first
  version); accession numbers link to the filing detail page; clean empty
  state
* `/review-queue` — grounded pending claims grouped by filing; approve /
  edit-and-approve / reject with optional reviewer notes; per-filing
  "Promote reviewed claims for this filing" button (scoped promotion only —
  the frontend never calls global promotion); clean empty state
* `/briefs/latest/[ticker]` — company ticker tabs loaded from
  `GET /companies` (static fallback if it fails) navigate between all
  watched companies with the active ticker highlighted; brief metadata
  cards + rendered markdown; tickers without a stored brief render a clean
  empty state; "Generate new brief version" button refreshes to the new
  version

## Quantitative research terminal (Bundle A, complete)

Restores the quantitative depth of the original static dashboard as a live,
deterministic layer over Supabase. No AI, no external market-data provider.

### Audited static-data backfill

`src/static_dashboard_backfill.py` + `run_static_dashboard_backfill.py` +
`test_static_dashboard_backfill.py`:

* parses the `METRICS` (1,290 rows) and `VALUATIONS` (5 rows) JS arrays from a
  locally downloaded copy of the public static dashboard
  (`https://avyuktk17.github.io/semiconductor-research/`); the HTML is read
  from a temp path (`/tmp/semiconductor_dashboard.html`) and never committed
* idempotent, dry-run-by-default, writes only with `--confirm`
* AVGO `financial_metrics`: inserts only missing operating rows, scoped to the
  metric names already present for the other tickers (valuation-derived and
  empty-period rows excluded); existing reviewed rows for the other four
  tickers are never overwritten. **In practice AVGO's 252 operating rows were
  already present** (the live table already held the full audited dataset; an
  earlier "AVGO missing" reading was a PostgREST 1000-row pagination
  artifact), so the metrics step is a verified no-op
* `valuation_snapshots`: the 5 manually reviewed snapshots were inserted on
  the confirmed run; a rerun skips all 5 (idempotent). Source references,
  extraction methods, formulas, and manual-review flags are preserved
* never calls Gemini; no credentials printed

### Quantitative read endpoints (public, deterministic)

* `GET /metrics/{ticker}` — historical operating-metric series for one
  company (optional `metric_name` filter); returns metric/period counts,
  per-metric time series, and a latest-period summary. Valuation-derived rows
  excluded; ticker uppercased; 404 unknown ticker
* `GET /peers` — latest-period peer table for all five companies: operating
  fundamentals + valuation snapshot fields + deterministically computed
  multiples (EV/TTM revenue, EV/TTM operating income, price/TTM FCF, FCF
  yield). Honest `null` where inputs are missing; carries
  `valuation_is_live = false`, snapshot dates, a disclaimer, and per-ticker
  comparability notes (business model + debt measure)
* `GET /peers/trends?metric_name=&ticker=&limit=` — chart-ready per-ticker
  time series for one metric (optional single ticker / last N periods)
* `GET /valuation-snapshots` — the 5 manually reviewed snapshots, each tagged
  `is_live = false`, with snapshot dates and a disclaimer

Deterministic math lives in `src/quantitative.py` (period sorting, operating
filtering, series building, latest-period summary, multiple computation);
`compute_multiples` returns `None` for any missing or zero denominator. Tests:
`test_api_metrics.py`, `test_api_peers.py`, `test_api_valuation_snapshots.py`.

### Frontend quantitative pages

`recharts` is the only new dependency. The browser still talks only to the
API.

* `/peers` — peer-comparison terminal: ranked horizontal bar chart with a
  metric selector, full fundamentals + valuation table, comparability-note
  panel, a visible "Valuation snapshot as of 2026-06-04" badge, and the
  "not a live market feed" disclaimer
* `/companies/[ticker]` — extended deep dive: financial KPI cards (latest
  quarter + YoY), revenue / gross+operating margin / FCF-margin / R&D-intensity
  / TTM trend charts, a balance-sheet & cash-flow snapshot, and a valuation
  snapshot (badge + disclaimer), above the existing pipeline panels;
  degrades cleanly when fundamentals are unavailable
* `/` — overview now also shows market-leader cards (top revenue growth,
  highest gross margin, strongest FCF margin), a peer-fundamentals table, and
  a link to `/peers`
* shared helpers: `src/lib/format.ts` (null-safe USD/percent/multiple
  formatting, series merge), `src/components/charts.tsx` (themed recharts
  line/bar charts), `src/components/ValuationNote.tsx` (snapshot badge +
  disclaimer); sidebar nav gains a **Peer Comparison** link

Valuation figures are always presented as a dated, manually reviewed
point-in-time snapshot — never implied to be live. Next milestone: **Bundle B
— Evidence Explorer and professional report engine.**

## Evidence Explorer & deterministic report engine (Bundle B1, complete)

A trusted-evidence layer and a deterministic, versioned research-report engine.
No AI is called — not Gemini, not the Claude API. Reports are assembled
arithmetically from three trusted sources only: promoted human-reviewed claims
(`qualitative_claims`, grounded), deterministic `financial_metrics`, and dated
`valuation_snapshots`.

### Evidence Explorer (public reads)

* `GET /evidence` — trusted, promoted, grounded claims (`proposed_claim_id` and
  `source_chunk_id` both non-null). Optional filters `ticker`,
  `accession_number`, `theme`, `claim_type`, `confidence`, `document_key`,
  `limit` (1–200). Provenance (accession, filing date, SEC URL) is recovered
  via `source_chunk_id → filing_chunks → filings`. Pending, rejected, and
  ungrounded legacy rows are never exposed
* `GET /evidence/{claim_id}` — one trusted claim with the **exact source chunk
  text**, document metadata, filing metadata, and SEC URL; `claim_id` is the
  `proposed_claim_id`. 404 when missing

### Deterministic report engine

`src/research_report.py` builds an intermediate block model and renders it to
both Markdown and an HTML subset (so the two never drift). Sections, in order:
Executive Summary · Reported Financial Snapshot · Historical Operating Trends ·
Peer Comparison · Balance Sheet and Cash Flow · Valuation Snapshot · Reviewed
Evidence-Linked Takeaways · Catalysts · Risks and Watch Items · Source Appendix
· Methodology and Limitations. Catalysts/Risks are routed deterministically
from human-reviewed claim text by keyword — nothing is invented; every claim
also appears in Takeaways. The engine **never** produces forecasts, DCF values,
price targets, or ratings, and always labels valuation as a dated snapshot.

`src/research_report_storage.py` versions and persists each report: it brackets
the run with a `report_generation_runs` row (running → completed/failed),
assigns the next `version_number`, renders Markdown + HTML + PDF, uploads all
three to the private bucket under `reports/{ticker}/{report_type}/v{n}.*`
(prior versions preserved), inserts the `research_reports` row plus one
`report_evidence_links` row per trusted claim used. CLI:
`generate_research_report.py` (`--dry-run` prints markdown without writing).

**PDF export: `fpdf2`** (pure-Python, zero system dependencies) — chosen over
WeasyPrint / xhtml2pdf, which pull in cairo/pango and fail to install on
Render. Trade-off: fpdf2's core font is latin-1, so SEC-excerpt punctuation is
transliterated for the PDF only; the stored Markdown and HTML keep full Unicode.

### Report API endpoints

* `GET /reports` (filters `ticker`, `report_type`, `report_status`) — metadata
  only, newest first, with a `pdf_available` flag
* `GET /reports/latest/{ticker}` (optional `report_type`, default
  `earnings_update`) — latest report with content + evidence links; 404 if none
* `GET /reports/{report_id}` — full report (markdown, HTML, evidence links,
  PDF path)
* `GET /reports/{report_id}/pdf` — 307 redirect to a short-lived **signed**
  private-Storage URL (the bucket is never exposed directly)
* `POST /reports/generate` *(admin)* — `{"ticker", "accession_number"?,
  "report_type"?}`; generates, versions, and persists. Errors map to 404
  (unknown company/filing) or a safe 500 (no secrets or provider detail)

### Frontend (Bundle B1)

* `/evidence` — Evidence Explorer: ticker/type/confidence filters + client-side
  text search; cards with classification/reviewed badges, excerpt preview, and
  an expandable exact source-chunk view plus SEC links
* `/reports` — report index: ticker/type filters, status/version, claim &
  metric counts, PDF links
* `/reports/latest/[ticker]` — ticker tabs (from `/companies`), rendered report,
  version selector, **Download PDF** (via the signed-URL route), evidence-link
  table, and an admin-only **Generate new report version** button
* sidebar nav gains **Evidence Explorer** and **Reports** links

### Limitations (Bundle B1)

No live valuation feed (dated snapshots only); no forecasts; no DCF; no target
price; no rating; no automatic Claude/Gemini usage.

## Claude equity-research skill & report packets (Bundle B2.1, complete)

A reusable Claude Code skill plus a deterministic report-packet exporter. **No
Claude API is called and no narrative is generated automatically.** The analyst
exports a trusted-data packet, then invokes the skill in Claude Code to draft a
narrative locally for review. Nothing is uploaded or written to Supabase.

### Deterministic report-packet exporter

`src/report_packet.py` + `export_report_packet.py` + `test_report_packet.py`:

* `export_report_packet(ticker, accession_number=None,
  output_dir="output/report_packets")` bundles one filing's trusted and
  deterministic facts into `{ticker_lower}_{safe_accession}_packet.md` and
  `.json`. Sources only: company profile (`companies`), selected filing
  metadata (`filings`), trusted promoted grounded claims (`qualitative_claims`)
  with source references / chunk ids / supporting excerpts, latest + historical
  `financial_metrics`, the deterministic peer comparison, the dated
  `valuation_snapshots`, and any existing `research_reports` metadata
* reuses the deterministic report engine's trusted-source accessors
  (`src.research_report`) so the two never disagree on what is a trusted claim
* deterministic output (stable ordering, sorted-key JSON); no LLM call, no
  database writes, no secrets; missing values labelled "Not available"
* accession defaults to the most recent filing with trusted claims (same
  selection as the report engine); returns ticker, accession, markdown/JSON
  paths, trusted-claim/metric/evidence-link counts, and valuation snapshot date
* CLI: `python export_report_packet.py --ticker AVGO --accession-number
  0001730168-26-000051`. Live result: AVGO `0001730168-26-000051` packet exports
  5 trusted claims, 21 metric series, 5 evidence links, snapshot date 2026-06-04
* output dir `output/report_packets/` is gitignored

### Claude Code skill

`.claude/skills/semiconductor-equity-research-report/` (`SKILL.md`,
`template.md`, `quality-checklist.md`) — invocable as
`/semiconductor-equity-research-report`. Drafts a professional earnings-update
narrative (Front-page Executive Summary · Quarterly Results · Guidance and
Outlook · Historical Trends · Peer Comparison · Balance Sheet and FCF ·
Valuation Snapshot · Catalysts · Risks and Watch Items · Evidence Appendix ·
Methodology) **only** from a supplied report packet. `template.md` and
`quality-checklist.md` load only when the skill runs, keeping routine Claude
Code sessions token-efficient. Guardrails: never invent a rating, target price,
forecast, DCF output, or consensus estimate; always label valuation as a dated
manually reviewed snapshot; distinguish reported facts from interpretation;
cite source references and chunk ids; preserve missing values honestly; label
the output `Claude-assisted draft for analyst review`; never write to trusted
tables. The result is a local draft only.

The `.gitignore` now ignores all personal `.claude/` state (settings.local.json,
memory, credentials) **except** this shareable skill directory, which is the
only `.claude/` content committed. The Jazz reference PDF stays in `/tmp` and is
never committed.

### Limitations (Bundle B2.1)

No Claude API call, no automatic narrative generation, no persistence of the
drafted narrative (persistence/review arrives in Bundle B2.2).

## Claude-assisted narrative review workflow (Bundle B2.2, complete)

Imports locally drafted Claude-assisted narratives as **private draft reports**
and adds analyst review controls. **Claude generation stays manual and local —
the backend never calls the Claude API or Gemini**, and nothing is published
until a human approves it.

### New `research_reports` columns (in use)

`source_report_id` (self-FK to the deterministic source report),
`source_packet_hash` (SHA-256 of the report packet the narrative was drafted
from), `imported_at`, `rejection_reason`, plus the existing `reviewed_at` /
`reviewer_notes`. Report statuses now span `human_reviewed_deterministic`
(deterministic, published), `draft` / `reviewed` / `superseded` / `rejected`
(Claude-assisted lifecycle), and `failed`. **Version numbers share one sequence
per `(ticker, report_type)`** — the unique constraint is
`(ticker, report_type, version_number)`, so deterministic and Claude-assisted
versions are numbered together (per-generator versioning would collide).

### Import service

`src/claude_narrative_import.py` + `import_claude_narrative.py` +
`test_claude_narrative_import.py`:

* `import_claude_assisted_narrative(ticker, markdown_path, accession_number=None,
  source_report_id=None, source_packet_path=None, report_type="earnings_update")`
  validates the exact `Claude-assisted draft for analyst review` label and
  rejects empty/incomplete drafts, hashes the packet, and inserts one draft
  `research_reports` row (`report_status="draft"`,
  `generator_type="claude_assisted"`, `imported_at`, provenance fields, counts).
  Evidence links are reused from the source report when given, else derived from
  the filing's trusted promoted claims; a completed `report_generation_runs`
  audit row is written. No trusted-claim mutation, no overwrite — always a new
  version
* CLI is **dry-run by default**; `--confirm` is required before any write; it
  prints a readable summary and never prints secrets
* the API `POST /reports/import-claude-draft` shares the same insert core
  (`insert_claude_draft`)

### Review service

`src/research_report_review.py` + `test_research_report_review.py` act only on
`claude_assisted` `draft` reports:

* `approve_research_report` — draft → `reviewed` (sets `reviewed_at`,
  `reviewer_notes`)
* `edit_and_approve_research_report` — preserves the original draft immutably as
  `superseded` and inserts a **new** `reviewed` version (next version number,
  edited markdown, copied provenance + evidence links)
* `reject_research_report` — draft → `rejected` with a required `rejection_reason`
* deterministic reports are never reviewable through this workflow; acting on a
  non-draft is an invalid transition

### Report-review API (admin-only)

* `GET /reports/review-queue` — Claude-assisted drafts only, with markdown and
  evidence-link count (declared before `/reports/{report_id}` so the literal
  path is not captured by the int route)
* `POST /reports/import-claude-draft` — validates the label, inserts a draft
* `POST /reports/{id}/approve` · `/edit-and-approve` · `/reject`
* missing/invalid token → 401, unknown report → 404, invalid transition → 400;
  bodies never expose secrets or stack traces

### Draft / public visibility rules

Public report endpoints (`/reports`, `/reports/latest/{ticker}`,
`/reports/{id}`) exclude `draft`, `rejected`, `superseded`, and `failed` reports
(`_HIDDEN_REPORT_STATUSES`); they show deterministic
(`human_reviewed_deterministic`) and reviewed Claude-assisted reports only, and
`/reports/latest` defaults to the most recent visible report. The admin
**Narrative Review** page is the only surface exposing Claude-assisted drafts.

### Frontend (Bundle B2.2)

`frontend/src/app/reports/review/page.tsx` (sidebar link **Narrative Review**):
admin-token-gated queue cards (ticker, accession, version, imported timestamp,
source report id, claim/evidence counts, packet-hash preview, rendered markdown
preview) with Approve / Edit-and-Approve / Reject / Skip, reviewer-notes and
rejection-reason fields, refresh-after-action, and clean empty/error states. The
report list and viewer pages label each report **Deterministic** vs
**Claude-assisted (reviewed)**. The admin token never leaves session storage.

### Limitations (Bundle B2.2)

Still no automatic Claude API call (generation is manual and local); single
shared admin token; narrative drafts are imported from local files only.

## Institutional UI redesign & report-layout polish (Bundle C1, complete)

A frontend-only redesign plus a deterministic-PDF layout upgrade. **No backend
logic, API contracts, secrets, data, GitHub Actions, or LLM usage changed** —
the only Python touched is the PDF rendering path and an additive `blocks` /
`report_date` key on the deterministic report generator's return value.

### Design system (`frontend/src/components/`)

Reusable components consolidate patterns that were previously duplicated across
pages: `ResearchHeader`, `MetricCard`, `SectionHeader`, `StatusPill` (one
canonical status→color mapping; `StatusBadge` now delegates to it), `DataTable`
(+ `THead`/`TH`/`TR`/`TD`, responsive overflow with `minWidth`), `EmptyState`,
`LoadingSkeleton`, `ColdStartNotice`, `SourceBadge`, `ReportTypeBadge`,
`TickerTabs`, and `ChartPanel`. `Panel`/`StatCard`/`charts`/`ValuationNote`
remain. Design tokens in `globals.css` gain a `warning` color (previously
referenced by Claude-assisted badges but **undefined**, so those badges rendered
colorless — fixed), `edge-strong`/`violet`, a page max-width container, terminal
scrollbars, a skeleton shimmer, and global `focus-visible` outlines for
keyboard accessibility. Shared hooks (`src/lib/hooks.ts`) consolidate the
companies-list and admin-token reads.

### Navigation

The sidebar is grouped into **Markets** (Overview, Peer Comparison, Companies),
**Research** (Evidence Explorer, Reports, Latest Brief), and **Workflow**
(Filings, Extraction Ready, Review Queue, Narrative Review), with explicit
active-state matching (so `/reports` and `/reports/review` never both highlight)
and a responsive layout that stacks the sidebar above content on mobile. The
admin-access panel and session-storage token behavior are unchanged.

### Pages

- `/` Overview — analyst landing screen: system stat cards, peer-leader cards,
  company-coverage table, workflow-health panel, report-coverage panel,
  peer-fundamentals table, recent-filings and extraction-queue panels, all with
  deep links.
- `/peers` — ranked bar chart (metric selector) plus a **sortable** peer table
  (click any column; missing values always sort last), business-model tags, the
  dated valuation badge, and the "not a live market feed" disclosure.
- `/companies/[ticker]` — tabbed deep dive (Overview / Financials / Filings /
  Evidence / Reports) with KPI cards, trend charts, valuation snapshot,
  trusted-claim summary, comparability notes, latest report/brief links, and
  clean empty states.
- `/evidence` — filter bar (ticker / theme / claim-type / confidence / text
  search) and compact cards with a visually prominent source-provenance row
  (accession · document key · chunk id · SEC link · filing date) plus the
  expandable exact source chunk. Accepts a `?ticker=` deep link.
- `/reports`, `/reports/latest/[ticker]`, `/reports/review` — report-type and
  status badges, source-report lineage, version selector, ticker tabs, a PDF
  download shown only when a PDF exists, evidence-link panels, and the
  narrative-review approve/edit/reject cards. Public pages still hide `draft`,
  `rejected`, `superseded`, and `failed` reports.
- `/filings`, `/filings/[accessionNumber]`, `/extraction-ready`,
  `/review-queue`, `/briefs/latest/[ticker]` — consistent headers, tables,
  status visibility, skeletons, and empty states.

### Cold-start & responsive behavior

The API client (`src/lib/api.ts`) tracks in-flight requests and, when one stays
slow past ~3.5s (almost always the Render free-tier dyno waking from sleep),
raises a global non-blocking `ColdStartNotice` banner instead of a silent hang.
Backend errors are still surfaced, never hidden. Tables scroll horizontally with
sensible minimum widths; the sidebar stacks on mobile.

### Deterministic PDF layout

`render_report_pdf` (in `src/research_report_storage.py`) renders the report's
intermediate **block model** natively via a new `_ResearchPDF(FPDF)` subclass
instead of re-parsing HTML: a neutral branded running header (`Earnings
Intelligence OS Research` + ticker/date), section hierarchy with rules, compact
financial tables with a shaded header and zebra rows (labels left, figures
right), evidence quotes, a source appendix, and a numbered footer carrying the
standard disclaimer. Still pure-Python `fpdf2` (no cairo/pango), private Storage,
signed-download URL, and latin-1 transliteration only where the core font
requires it. No Jazz branding or wording is copied; the reference PDF stays in
`/tmp` and is never committed. The legacy HTML `render_pdf` is retained for
back-compat but is no longer on the storage path.

### Verification (Bundle C1)

`npm run lint` and `npm run build` pass clean (all 11 routes compile).
`test_research_report.py` passes against live data (the additive `blocks` key
did not change the markdown/HTML structure). `render_report_pdf` was validated
read-only against the real AVGO block model (valid `%PDF` … `%%EOF`, no DB
writes). The API boots and every public read endpoint returns 200; the
deterministic report `/pdf` route still 307-redirects to a signed URL, while
Claude-assisted reports (no PDF) correctly 404. Next milestone: **Bundle C final
QA** (portfolio screenshots and demo video, deferred).

## v0 institutional terminal redesign — Phase B (Bundle C2, complete)

A frontend-only redesign plus a deterministic-PDF rendering polish. **No backend
logic, API contracts, Supabase schema, secrets, GitHub Actions, or LLM usage
changed** — the only Python touched is the PDF rendering path in
`src/research_report_storage.py`. Phase A (the `/`, `/peers`,
`/companies/[ticker]`, `/evidence` screens and the shared components/tokens)
was already committed as `Port v0 design language into core research screens`
and was not redone.

### OS-driven light/dark theme

`frontend/src/app/globals.css` now follows the operating-system appearance
automatically. `:root` defines a **light-default** token set (white background,
light neutral surfaces, dark primary text, subtle gray borders, restrained
amber primary accent darkened for AA contrast on white) and a
`@media (prefers-color-scheme: dark)` block restores the established v0
near-black terminal palette. The existing token *names* (`--background`,
`--surface`, `--foreground`, `--edge`, `--hairline`, `--accent`, …) are kept so
every shared component adapts with no markup changes; hairlines flip from
white-alpha (dark) to dark-alpha (light). `color-scheme` is set per theme so
native form controls and scrollbars follow suit. There is **no manual theme
switcher** in this phase. Semantic colors are preserved across both themes:
green positive/approved, red negative/rejected/failed, amber/yellow
pending/warning, blue SEC/informational, purple Claude-assisted/AI. The frontend
has zero hard-coded `white`/`black`/palette colors (verified by grep); the only
literal hexes are recharts series/ticker brand hues. `src/components/charts.tsx`
reads the live CSS tokens for grid/axis/tooltip colors and re-reads them on a
`prefers-color-scheme` change, so charts render correctly in both themes.

### Workflow pages

- `/filings` — dense `FilingsTable` (ticker → company link, form, filed, report
  date, accession → detail link, processing-status pill) with ticker/status/
  limit filters; exhibit and claim-extraction status are intentionally **not**
  added here because `GET /filings` does not expose them (they live on
  `GET /extraction-ready`) and the API contract is preserved.
- `/filings/[accessionNumber]` — compact provenance panels: filing metadata
  (ticker, form, dates, accession, SEC link, processing lifecycle, chunk count),
  processing-error surface, and an ingested-documents table with HTML/text
  Storage flags.
- `/extraction-ready` — **converted from oversized cards into a dense action
  table** (Ticker · Accession · Filed · Exhibit · Chunks · Exhibit stage · Claim
  stage · Pending · Trusted · Brief · Action). All protected actions are
  preserved unchanged (Extract Claims, Promote reviewed claims, Generate first
  brief, View latest brief), gated on a saved admin token, with per-row busy
  state and a full-width sub-row for success/error notices and the API's
  redacted extraction error. No batch extraction; no backend behavior change.
- `/review-queue` — grounded pending claims grouped by filing with source
  excerpt, chunk/accession/document-key provenance, theme, confidence, and the
  Approve / Edit-and-Approve / Reject flow plus scoped per-filing promotion
  (admin-token-gated, grounded-only).
- `/briefs/latest/[ticker]` — ticker tabs, brief metadata cards (version,
  trusted/factual/interpretive counts), rendered intelligence-note markdown,
  and the version-generation control. No PDF button (briefs have no PDF route).

### Report pages

- `/reports` — **regrouped by ticker**: each company group shows the latest
  visible report prominently (det/Claude badge, status, type, generated date,
  claim & metric counts, PDF link only when available, view action) with prior
  versions in a collapsible subordinate table. Public hiding of draft / rejected
  / superseded / failed reports is enforced by the unchanged backend.
- `/reports/latest/[ticker]` — ticker tabs, professional header, report-type +
  deterministic/Claude badge, review status, version selector, generated date,
  valuation-snapshot disclosure, source-report lineage, **Download PDF only when
  a PDF exists** (Claude-assisted reports correctly show none), evidence-link
  panel, and admin-only version generation.
- `/reports/review` — admin-token-gated narrative-review queue (draft-only):
  ticker, type, version, imported date, source report id, packet-hash preview,
  claim/evidence counts, rendered markdown preview, reviewer notes, and the
  Approve / Edit-and-Approve / Reject / Skip actions; edit-and-approve preserves
  the original draft immutably.

### Deterministic PDF rendering polish

`src/research_report_storage.py` keeps rendering the report's intermediate
**block model** natively via `_ResearchPDF(FPDF)` (no HTML re-parse) and stays
pure-Python `fpdf2` (built-in fonts only, no external font files, private
Storage, signed URLs, latin-1 transliteration only where the core font
requires). Rendering refinements only (the report-generation logic is
unchanged): the first brand `h1` becomes a restrained accent **masthead
eyebrow** (the running header already carries the brand) so the company name —
the first `h2` — renders as the dominant first-page title; the report-metadata
`kv` block renders in an **accent-tinted panel** with a left accent bar; section
headers gain a small **accent tick** before the hairline rule; and evidence
quotes use an **accent left rule**. Executive-summary section, hierarchical
financial tables with a shaded header + zebra rows, numbered evidence claims,
source appendix, methodology section, page numbers, and the disclaimer footer
are retained. Validated read-only against the real AVGO block model (valid
`%PDF` … `%%EOF`, 52 blocks, no DB writes); `test_research_report.py` still
passes (markdown/HTML/block model unchanged).

### Verification (Bundle C2)

`cd frontend && npm run lint && npm run build` pass clean (all 11 routes
compile). `test_research_report.py` passes against live data. The API boots and
real read endpoints return real data: `/extraction-ready` (15 filings with
exhibit/claim lifecycle), `/reports` (returns only
`human_reviewed_deterministic` + `reviewed` — drafts/rejected/superseded/failed
hidden, no public leakage), and `/reports/latest/AVGO` (a reviewed
Claude-assisted report with no PDF, so no dead PDF link). Protected actions
still require the session-storage admin token. Next milestone: **Bundle C final
QA** (portfolio screenshots and demo video, deferred — screenshots are captured
locally for review only and never committed).

## Deployment (complete — MVP live)

* **Backend (Render):** `https://earnings-intelligence-os-api.onrender.com`
  — deployed from the `render.yaml` blueprint (Python web service, health
  check on `/health`, start command
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`)
* **Frontend (Vercel):** `https://earnings-intelligence-os.vercel.app`
* backend env vars configured in Render: `SUPABASE_URL`,
  `SUPABASE_SECRET_KEY`, `SEC_USER_AGENT`, `GEMINI_API_KEY`, `GEMINI_MODEL`
  (optional, default `gemini-2.5-flash`), `ALLOWED_ORIGINS`, `ADMIN_API_TOKEN`
* production CORS: Render `ALLOWED_ORIGINS` is set to
  `http://localhost:3000,https://earnings-intelligence-os.vercel.app`
* the Supabase server-side key configuration in Render was initially wrong
  and has been corrected; the API now reaches Supabase in production
* production smoke test passed: public GET endpoints (health, companies,
  filings, briefs, review queue) and admin-token-protected POST endpoints
  are working against the live deployment
* frontend env var: `NEXT_PUBLIC_API_BASE_URL` set in Vercel to the Render
  API origin (production-safe `frontend/.env.example` documents it)
* the deployed API never calls Gemini (extraction stays manual); scheduled
  SEC ingestion stays in GitHub Actions

## Tests

Script-style tests run with `python test_*.py` against live Supabase data.
API tests: `test_api_health.py`, `test_api_filings.py`, `test_api_briefs.py`,
`test_api_review_queue.py`, `test_api_companies.py`, `test_api_cors.py`,
`test_api_auth.py` (public reads, 401s, correct-token action, fail-closed
500), `test_api_review_actions.py`,
`test_api_promotion.py` (global + scoped modes), `test_api_brief_generation.py`,
`test_api_extraction_ready.py`, `test_process_pending_exhibits.py`
(worker processed / not-found / failed paths, idempotency, and proof that
grounded chunks and trusted claims survive reruns),
`test_exhibit_selection.py` (synthetic press-release-first ranking, no
network), `test_exhibit_repointing.py` (best-ranked upgrade + exact-match
reuse), `test_api_error_redaction.py` (no provider details in public
payloads), `test_claim_extraction_status.py`,
`test_ready_filing_extraction.py`, `test_promotion_lifecycle.py`
(scoped promotion approves exactly the fully reviewed filing),
`test_api_manual_extraction.py`
(auth, validation, 404/400/429/safe-500 mapping, and the
promotion-driven `approved` lifecycle), `test_api_company_detail.py`,
`test_api_overview.py` (totals consistent with per-company rows),
`test_api_admin_validate.py`, `test_report_packet.py` (deterministic
report-packet exporter: trusted-claims-only, grounding, determinism across
reruns, honest missing-data labelling; writes to a temp dir, never calls an
LLM), `test_claude_narrative_import.py` /
`test_research_report_review.py` / `test_api_report_review.py` (Claude-assisted
narrative import + review: label validation, dry-run safety, versioning,
approve / edit-and-approve / reject, invalid-transition guards, deterministic
protection, auth, drafts-only queue, public draft exclusion, no secret leakage;
temporary draft rows are deleted in `finally` blocks and no Claude/Gemini call
is made), and `test_cleanup_legacy_claims.py`
(dry-run safety only — the destructive mode is never run by tests).
Every extraction test
monkeypatches the Gemini-backed extractor — automated tests never consume
free-tier quota. `test_api_briefs.py` is version-agnostic (analysts
generate new brief versions in production).
Write-endpoint tests supply a temporary admin token via the environment
(never printed),
insert clearly marked temporary rows and delete them in `finally` blocks;
real trusted claims and persisted briefs are never modified.
Frontend checks: `cd frontend && npm run lint && npm run build`.
Known cosmetic warning when importing TestClient:
`StarletteDeprecationWarning: Using httpx with starlette.testclient is
deprecated; install httpx2 instead.` — harmless, left as-is.

## Legacy cleanup script

`cleanup_legacy_claims.py` targets only `proposed_claims` rows with
`source_chunk_id` null **and** `review_status = "pending"` (drafts from the
pre-grounding extractor). Default invocation is a dry run that prints the
matching rows; deletion requires the explicit `--confirm` flag and is never
run by tests, deployment, or GitHub Actions. Deletes repeat the safety
predicates per row id, so a row reviewed in the meantime is left alone.

## Known limitations

* Two ungrounded legacy pending AVGO primary-document claims (ids 11, 12)
  remain in `proposed_claims`. They are excluded from the review queue,
  approval, promotion, and briefs by design. Remove them with
  `python cleanup_legacy_claims.py --confirm` when ready (dry run is safe
  to preview anytime).
* Auth is a single shared admin token — no user accounts, roles, or audit
  trail; suitable for the MVP only.
* 404-vs-400 mapping for workflow errors keys on `ValueError` message
  prefixes (documented as fragile; typed exceptions are the upgrade path).
* Gemini quota detection is string-marker-based ("429", "quota", "rate")
  and could misclassify rare non-quota errors as 429.
* Exhibit selection is filename-heuristic; unusual naming conventions may
  need new narrow patterns (INTC, the last holdout, resolved without one —
  it has 2 extraction-ready filings and a v1 brief).
* The deployed API serves Gemini extraction only on explicit admin action;
  brief content quality still depends on analyst review rigor.

## Live URLs

* Dashboard (Vercel): <https://earnings-intelligence-os.vercel.app>
* API (Render): <https://earnings-intelligence-os-api.onrender.com>

## Status

Level 3 product polish is complete: all five companies (AVGO, NVDA, AMD,
QCOM, INTC) have extraction-ready exhibits, trusted human-reviewed claims,
and at least one persisted brief; the dashboard covers the full workflow
end to end (monitor → exhibits → extraction → review → promotion → briefs)
with cross-company and per-company views.

## Safety rules

* Never expose `.env`, Supabase credentials, or API keys
* Do not commit local downloaded/parsed documents or generated briefs
* Keep the Supabase Storage bucket private
* Do not write AI output directly into trusted `qualitative_claims` —
  promotion only happens after human review
* Require exact grounded excerpts after whitespace normalization
* Keep AI extraction manual until quality is reviewed
* Write endpoints require the admin token; keep `ADMIN_API_TOKEN` private
  and never commit or print it
* Production secrets (Supabase keys, admin token) live only in Render's and
  Vercel's environment settings — never in the repository; keep
  `ALLOWED_ORIGINS` restricted to known frontend origins
