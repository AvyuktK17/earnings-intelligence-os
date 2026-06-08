# Earnings Intelligence OS — Project Status

## 1. Project Goal

Monitor SEC EDGAR for 10-K, 10-Q, and 8-K filings from five semiconductor
companies (QCOM, AMD, NVDA, INTC, AVGO).  For each filing:

1. Detect and store the filing in Supabase.
2. Download the primary HTML document and any EX-99.1 earnings-release exhibit.
3. Parse HTML to plain text.
4. Upload both files to a private Supabase Storage bucket (`filing-documents`).
5. Chunk the text into ≤ 2,000-character segments stored in `filing_chunks`.
6. Extract AI-generated financial claims via Gemini and store them as
   `proposed_claims` for human review.

GitHub Actions runs the monitor every 6 hours automatically.

---

## 2. What Is Already Working

| Area | Status |
|---|---|
| Supabase tables (see §3) | created |
| GitHub Actions monitor (every 6 h) | working |
| SEC filing detection for all 5 tickers | working |
| Duplicate-safe filing sync | working |
| Download → parse → Storage upload pipeline | working |
| `processing_status` state machine (detected → downloaded → parsed → chunked) | working |
| Failure tracking (`processing_error` column) | working |
| Batch processor (`run_processor.py`, 3 filings per run) | working |
| Primary-document chunking (`chunk_and_store_filing`) | working |
| Chunk backfill worker | working |
| Backfill worker for missing Storage paths | working |
| Gemini API smoke test (`test_gemini_connection.py`) | passing |
| Structured claim extraction from primary chunks (`claim_extractor.py`) | working — whitespace-normalised excerpt validation |
| EX-99.1 exhibit discovery from SEC EDGAR directory index | working |
| Exhibit download, parse, Storage upload, `filing_documents` upsert | working |
| Exhibit chunking with separate `document_key` (`chunk_and_store_document`) | working |

All tasks above have been committed and pushed to `main`.

---

## 3. Database Tables

### `companies`
`id, ticker, cik, name, created_at`

### `pipeline_runs`
`id, ticker, trigger_type, status, started_at, completed_at, error_message`

### `filings`
`id, ticker, accession_number, form, filing_date, report_date, primary_document,`
`sec_url, processing_status, downloaded_at, parsed_at, chunked_at,`
`processing_error, html_storage_path, text_storage_path`

Processing status values: `detected → downloaded → parsed → chunked`

### `filing_documents`
`id, filing_id, ticker, accession_number, document_type, filename,`
`sec_url, html_storage_path, text_storage_path, created_at`

Unique constraint: `(accession_number, filename)`
Currently stores `document_type = "earnings_release"` for EX-99.1 exhibits.

### `filing_chunks`
`id, filing_id, filing_document_id, ticker, accession_number,`
`document_key, chunk_index, chunk_text, character_count, created_at`

Unique constraint: `(accession_number, document_key, chunk_index)`

- Primary-document chunks: `document_key = "primary"`, `filing_document_id = NULL`
- Exhibit chunks: `document_key = "exhibit:{filename}"`, `filing_document_id = <filing_documents.id>`

### `proposed_claims`
`id, filing_id, ticker, accession_number, theme, claim_text,`
`supporting_excerpt, source_chunk_index, claim_type, confidence,`
`review_status, created_at`

`review_status = "pending"` for newly extracted claims.
Never auto-approve or copy to any trusted `qualitative_claims` table.

---

## 4. GitHub Actions Workflow

**File:** `.github/workflows/run-monitor.yml`  
**Schedule:** `"17 */6 * * *"` (every 6 hours)  
**Concurrency group:** `sec-filing-monitor`, `cancel-in-progress: false`  
**Secrets used:** `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `SEC_USER_AGENT`  
**Note:** `GEMINI_API_KEY` is not yet wired into the workflow.

**Steps (in order):**
1. Run filing monitor (`run_monitor.py`)
2. Process detected filings (`run_processor.py`, batch size 3)
3. Backfill missing Storage paths (`run_backfill.py`)
4. Backfill missing chunks (`run_chunk_backfill.py`)
5. List detected filings (`list_filings.py`)

---

## 5. Source Files (`src/`)

| File | Purpose |
|---|---|
| `database.py` | `get_supabase_client()` — loads env vars, returns Supabase client |
| `sec_client.py` | `get_recent_filings(cik)` — fetches submissions JSON from SEC EDGAR |
| `filing_sync.py` | `sync_recent_filings(ticker, cik)` — inserts new filings with `status="detected"` |
| `pipeline_runs.py` | `start/complete/fail_pipeline_run()` — pipeline run tracking |
| `run_filing_check.py` | `run_filing_check(ticker, cik)` — orchestrates one company check |
| `run_all_filing_checks.py` | `run_all_filing_checks()` — loops over all companies in DB |
| `filing_downloader.py` | `download_filing(sec_url, output_path)` — downloads from SEC with User-Agent |
| `filing_parser.py` | `extract_filing_text(html_path, output_path)` — BeautifulSoup HTML → plain text |
| `filing_status.py` | `mark_filing_downloaded/parsed/chunked/failed`, `record_filing_storage_paths` |
| `storage.py` | `upload_file(local, storage_path)`, `download_file(storage_path, local)` — private bucket |
| `process_filing.py` | `process_filing(filing)` — full download→parse→upload→chunk pipeline for primary doc |
| `process_detected_filings.py` | `process_detected_filings(limit)` — batch-processes `status="detected"` filings |
| `backfill_missing_storage.py` | backfill Storage paths for parsed rows with null paths |
| `backfill_missing_chunks.py` | backfill chunks for parsed rows missing them |
| `filing_chunker.py` | `chunk_text()`, `chunk_and_store_filing(accession_number)`, `chunk_and_store_document(document_id)` |
| `filing_exhibits.py` | `get_filing_exhibits(sec_url)`, `select_earnings_release_exhibit(exhibits)` |
| `process_filing_exhibit.py` | `process_earnings_release_exhibit(accession_number)` — full exhibit ingestion pipeline |
| `llm_client.py` | `get_gemini_client()`, `test_gemini_connection()` — Gemini API setup |
| `claim_extractor.py` | `extract_and_store_claims(accession_number, max_claims)` — Gemini structured claim extraction |

**Storage bucket:** `filing-documents` (private)  
**Storage path conventions:**
- Primary HTML: `html/{ticker}/{accession_number}.html`
- Primary text: `parsed/{ticker}/{accession_number}.txt`
- Exhibit HTML: `html/{ticker}/{accession_number}/exhibits/{filename}`
- Exhibit text: `parsed/{ticker}/{accession_number}/exhibits/{filename}.txt`

**Local file conventions (Git-ignored):**
- `data/raw_filings/{ticker}_{safe_accession}.html`
- `data/parsed_filings/{ticker}_{safe_accession}.txt`
- `data/raw_filings/{ticker}_{safe_accession}_{safe_filename}` (exhibit HTML)
- `data/parsed_filings/{ticker}_{safe_accession}_{safe_filename}.txt` (exhibit text)
- `data/chunking_inputs/` (chunker downloads)

Tickers are lowercase in local paths and Storage paths; hyphens are kept in
accession numbers inside Storage paths but replaced with underscores locally.

---

## 6. Recently Completed Task

**Exhibit chunking** — completed in the previous session:

- `src/filing_chunker.py` updated:
  - `chunk_and_store_filing` now sets `document_key="primary"` and
    `filing_document_id=None` on each row, and scopes its delete to
    `document_key="primary"` only (exhibit chunks are never touched).
  - New `chunk_and_store_document(document_id)` chunks an exhibit from
    `filing_documents` using `document_key="exhibit:{filename}"`.
- `test_chunk_filing_exhibit.py` created and passing.
- AVGO EX-99.1 exhibit (`avgo-05032026x8kxex99.htm`) produces 17 chunks,
  avg 1,421 chars. Primary chunks (2) coexist without collision.

---

## 7. Next Task — Extend Claim Extraction to Exhibit Chunks

The current `extract_and_store_claims(accession_number)` queries ALL chunks
for an accession number regardless of `document_key`.  It needs to be able to
target a specific document (primary or exhibit) so that claims from the richer
EX-99.1 exhibit can be extracted separately.

**Suggested prompt for the next session:**

> We want to extract Gemini claims from the AVGO EX-99.1 earnings-release
> exhibit (accession `0001730168-26-000051`, filing_documents id 1) using its
> exhibit chunks (`document_key = "exhibit:avgo-05032026x8kxex99.htm"`).
>
> The current `extract_and_store_claims(accession_number)` fetches all chunks
> for an accession number without filtering by `document_key`, so it mixes
> primary and exhibit text.
>
> Next task: extend `src/claim_extractor.py` so that
> `extract_and_store_claims` accepts an optional `document_key` parameter.
> When supplied, filter `filing_chunks` to only that `document_key`.  When
> omitted, keep the current behaviour (all chunks, `document_key = "primary"`
> for backwards compatibility).  Update `proposed_claims` rows to include
> the `document_key` so the source is traceable.  Then create
> `test_claim_extractor_exhibit.py` that calls the function with
> `document_key = "exhibit:avgo-05032026x8kxex99.htm"` and verifies at least
> 3 valid claims are stored.

---

## 8. Known Caveats

- **Older rows were backfilled** — some `filings` rows went through the
  backfill workers rather than the normal pipeline; their `chunked_at` may
  differ from `parsed_at`.
- **Status ordering** — `parsed` always precedes `chunked`.  The old bug where
  `mark_filing_parsed` was called before Storage uploads is fixed; safe
  ordering is: download → mark downloaded → parse → upload HTML → upload text
  → record paths → mark parsed → chunk → mark chunked.
- **8-K earnings content lives in EX-99.1** — the primary 8-K HTML is usually
  just a cover page (~33 KB).  The substantive financial data is in the
  attached exhibit.  `filing_exhibits.py` discovers it via the SEC EDGAR
  directory `index.json`.
- **Gemini excerpt validation normalises whitespace** — `_normalize_ws()`
  collapses repeated spaces/newlines and treats `\xa0` as a space before
  checking substring membership.  The original Gemini excerpt text is still
  stored as-is (normalised before storage).
- **Gemini 503 spikes** — `gemini-2.5-flash` occasionally returns 503
  UNAVAILABLE during demand spikes.  Retry after a short wait; do not
  permanently switch models.
- **`.env` must never be committed** — `SUPABASE_URL`, `SUPABASE_SECRET_KEY`,
  `SEC_USER_AGENT`, `GEMINI_API_KEY` are local only.  In GitHub Actions they
  come from repository secrets.
- **Storage bucket is private** — never call `make_public()` or generate
  public URLs for the `filing-documents` bucket.
- **Downloaded and parsed files are Git-ignored** — `data/raw_filings/`,
  `data/parsed_filings/`, `data/chunking_inputs/` are in `.gitignore`.
