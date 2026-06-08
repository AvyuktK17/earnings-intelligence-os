# Earnings Intelligence OS — Project Status

## Project goal

Build an Earnings Intelligence OS for semiconductor companies:

* monitor SEC EDGAR automatically;
* detect new filings;
* download and parse filings;
* store documents permanently in Supabase Storage;
* split documents into AI-ready chunks;
* extract evidence-linked draft claims;
* require human review before claims enter trusted research outputs.

## Companies monitored

* QCOM
* AMD
* NVDA
* INTC
* AVGO

## Working infrastructure

* Supabase tables:

  * companies
  * financial_metrics
  * qualitative_claims
  * pipeline_runs
  * filings
  * filing_documents
  * filing_chunks
  * proposed_claims
* Private Supabase Storage bucket:

  * filing-documents
* GitHub Actions workflow:

  * manual `workflow_dispatch`
  * scheduled cron: `17 */6 * * *`
  * concurrency group: `sec-filing-monitor`
  * runs every 6 hours
* Workflow steps:

  1. Run filing monitor
  2. Process detected filings
  3. Backfill missing Storage paths
  4. Backfill missing chunks
  5. List detected filings

## Working pipeline lifecycle

* detected
* downloaded
* parsed
* chunked

A filing only receives `chunked` status after:

* HTML download;
* text parsing;
* HTML and text Storage upload;
* Storage-path persistence;
* chunk creation.

## Completed AI groundwork

* Gemini API key stored locally and in GitHub Secrets
* `google-genai` SDK installed
* Gemini smoke test passed
* `proposed_claims` table created
* first AVGO 8-K claim extraction test passed
* excerpt validation normalizes whitespace but still requires literal substring evidence
* weak first output revealed that earnings-related information was in EX-99.1 rather than the thin 8-K cover page

## Exhibit support completed

* `src/filing_exhibits.py`

  * derives SEC filing index URL
  * discovers filing-directory documents
  * selects likely earnings-release exhibit
* `src/process_filing_exhibit.py`

  * downloads EX-99.1
  * parses text
  * uploads HTML and text to private Storage
  * records metadata in filing_documents
* AVGO exhibit ingested:

  * accession: `0001730168-26-000051`
  * filename: `avgo-05032026x8kxex99.htm`
  * parsed text: approximately 24 KB

## Multi-document chunking completed

* filing_chunks now contains:

  * `filing_document_id`
  * `document_key`
* unique constraint:

  * `(accession_number, document_key, chunk_index)`
* primary chunks use:

  * `document_key = "primary"`
  * `filing_document_id = None`
* exhibit chunks use:

  * `document_key = "exhibit:{filename}"`
  * the matching filing_document_id
* `src/filing_chunker.py` now contains:

  * `chunk_and_store_filing(accession_number)`
  * `chunk_and_store_document(document_id)`
* AVGO EX-99.1 test passed:

  * 17 exhibit chunks
  * average size: 1,421 characters
  * 2 primary chunks preserved
  * no duplicate chunks after rerun

## Database update made immediately before handoff

* proposed_claims now has:

  * `document_key TEXT` column (added via `ALTER TABLE proposed_claims ADD COLUMN document_key TEXT`)
  * existing rows backfilled: `UPDATE proposed_claims SET document_key = 'primary' WHERE document_key IS NULL`
* keep `source_chunk_index` for readability
* use `document_key` to scope deletes and inserts per document

## Exact next task

Update claim extraction so it can analyze a specific document, especially the AVGO EX-99.1 exhibit, rather than all chunks for an accession number.

Expected design:

1. Modify `src/claim_extractor.py`
2. Add a function such as:
   `extract_and_store_document_claims(document_id: int, max_claims: int = 5) -> dict`
3. Query chunks using the selected `filing_document_id`
4. Send only those exhibit chunks to Gemini
5. Validate each evidence excerpt against the cited chunk
6. Save:

   * source_chunk_index
   * filing_id
   * ticker
   * accession_number
   * document_key
   * theme
   * claim_text
   * supporting_excerpt
   * claim_type
   * confidence
   * review_status = "pending"
7. Keep normalized-whitespace literal-substring validation
8. Delete only prior pending claims for the same `(accession_number, document_key)` before reinsertion
9. Preserve non-pending rows
10. Test using AVGO document:

* accession: `0001730168-26-000051`
* filename: `avgo-05032026x8kxex99.htm`
* document_key: `exhibit:avgo-05032026x8kxex99.htm`

11. Expect financially material claims such as AI semiconductor revenue, guidance, or revenue trends, not only dividend dates.
12. Do not auto-approve claims.
13. Do not add AI extraction to GitHub Actions yet.

## What was done in the session immediately before this handoff

* `src/claim_extractor.py` updated:

  * `extract_and_store_claims` now accepts optional `document_key: str | None = None`
  * defaults to `"primary"` when omitted (backwards compatible with existing primary-doc test)
  * filters `filing_chunks` by `.eq("document_key", document_key)`
  * raises `ValueError` if no chunks match (catches missing data early)
  * scopes idempotent DELETE to `(accession_number, document_key)` so exhibit and primary claims never collide
  * each inserted `proposed_claims` row includes `document_key`
  * return dict includes `document_key`
* `test_claim_extractor_exhibit.py` created:

  * verifies 17 exhibit chunks present
  * requests 5 claims from exhibit document_key
  * asserts ≥ 3 stored
  * validates each row's document_key, source_chunk_index, supporting_excerpt, claim_type, confidence
  * checks idempotency on second run
  * confirms primary pending rows are untouched after exhibit extraction

* **Blocked on Supabase migration**: `proposed_claims.document_key TEXT` column must be added before the test can pass. SQL to run in Supabase SQL editor:

  ```sql
  ALTER TABLE proposed_claims ADD COLUMN document_key TEXT;
  UPDATE proposed_claims SET document_key = 'primary' WHERE document_key IS NULL;
  ```

## Safety rules

* Never expose `.env` or API keys
* Do not commit local downloaded or parsed documents
* Keep Supabase Storage bucket private
* Do not write AI output directly into trusted qualitative_claims
* Require exact grounded excerpts after whitespace normalization
* Keep AI extraction manual until quality is reviewed
