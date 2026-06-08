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

## Document-specific claim extraction completed

* `proposed_claims` table now has:

  * `document_key TEXT` column (migrated and backfilled)
  * `source_chunk_id` column (already existed; now populated by extractor)
* `src/claim_extractor.py` updated:

  * `extract_and_store_claims` accepts optional `document_key: str | None = None`
  * defaults to `"primary"` when omitted (backwards-compatible)
  * selects `id, chunk_index, chunk_text` from `filing_chunks` (was missing `id`)
  * builds `chunk_id_map` alongside `chunk_map`
  * each inserted row includes `document_key` and `source_chunk_id`
  * idempotent DELETE scoped to `(accession_number, document_key, review_status=pending)`
* AVGO EX-99.1 exhibit test verified:

  * 4 financially material claims stored (Revenue, Net Income, Cash Flow, Q3 Guidance)
  * every row: `document_key` correct, `source_chunk_id` matches filing_chunks PK, excerpt validates against chunk text after whitespace normalization
  * scoped delete confirmed: exhibit pending rows deleted cleanly; 2 primary pending rows untouched

## Safety rules

* Never expose `.env` or API keys
* Do not commit local downloaded or parsed documents
* Keep Supabase Storage bucket private
* Do not write AI output directly into trusted qualitative_claims
* Require exact grounded excerpts after whitespace normalization
* Keep AI extraction manual until quality is reviewed
