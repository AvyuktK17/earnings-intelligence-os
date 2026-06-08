# Earnings Intelligence OS — Backend

A Python backend that monitors SEC EDGAR for recent filings from a watchlist of companies and stores them in Supabase.

## What it does

1. Connects to a Supabase database.
2. Checks SEC EDGAR for recent 10-K, 10-Q, and 8-K filings for each watched company.
3. Inserts filings that have not been seen before.
4. Skips filings that already exist (deduplicates by accession number).
5. Records every pipeline run with its status and timestamps.
6. Provides a command to list all detected filings stored in the database.

## Setup

**1. Clone the repo and enter the backend folder**

```bash
cd backend
```

**2. Create a virtual environment and install dependencies**

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**3. Create your local environment file**

```bash
cp .env.example .env
```

Open `.env` and fill in your credentials:

- `SUPABASE_URL` — your Supabase project URL
- `SUPABASE_SECRET_KEY` — your Supabase service-role key
- `SEC_USER_AGENT` — required by SEC EDGAR, e.g. `Your Name your@email.com`

> **Warning: never commit `.env` to Git.** It is listed in `.gitignore` to prevent accidental exposure.

## Running the monitor

```bash
python run_monitor.py
```

Checks all companies in the `companies` table, inserts any new filings, and prints a summary.

## Listing stored filings

```bash
python list_filings.py
```

Prints the 25 most recently filed rows from the `filings` table, plus the total count.

## Main files

| File | Purpose |
|------|---------|
| `run_monitor.py` | Entry point — run a filing check for all companies |
| `list_filings.py` | Read-only view of filings stored in Supabase |
| `src/database.py` | Supabase client factory |
| `src/sec_client.py` | SEC EDGAR submissions fetcher |
| `src/filing_sync.py` | Insert new filings, skip duplicates |
| `src/run_filing_check.py` | Orchestrate one company: pipeline run + sync |
| `src/run_all_filing_checks.py` | Loop over all companies in the database |
| `src/pipeline_runs.py` | Start, complete, and fail pipeline run records |
