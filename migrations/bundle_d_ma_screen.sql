-- Bundle D — M&A Target Screener: schema migration
-- Run in the Supabase SQL editor. Idempotent (IF NOT EXISTS throughout).

-- 0. Ensure companies(ticker) has a UNIQUE constraint so that the foreign
--    keys in steps 2–4 can reference it. The constraint may already exist on
--    an older database; DO NOTHING in that case.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'companies'::regclass
      AND contype = 'u'
      AND conname = 'companies_ticker_unique'
  ) THEN
    ALTER TABLE companies ADD CONSTRAINT companies_ticker_unique UNIQUE (ticker);
  END IF;
END;
$$;

-- 1. Coverage tier on companies: 'acquirer' (the watchlist 5) vs 'target'
--    (screener universe). Existing rows default to 'acquirer'.
ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS coverage_tier text NOT NULL DEFAULT 'acquirer'
  CHECK (coverage_tier IN ('acquirer', 'target'));

-- 2. Manually reviewed acquirer×target pairs. Only reviewed pairs are scored.
CREATE TABLE IF NOT EXISTS ma_screen_pairs (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  acquirer_ticker text NOT NULL REFERENCES companies(ticker),
  target_ticker   text NOT NULL REFERENCES companies(ticker),
  fit_note        text,
  regulatory_note text,
  manually_reviewed boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (acquirer_ticker, target_ticker),
  CHECK (acquirer_ticker <> target_ticker)
);

-- 3. Versioned run bookkeeping (mirrors report_generation_runs).
CREATE TABLE IF NOT EXISTS ma_screen_runs (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_status text NOT NULL DEFAULT 'running'
    CHECK (run_status IN ('running', 'completed', 'failed')),
  valuation_snapshot_date date,
  universe_size integer,
  pair_count integer,
  error_message text,
  started_at  timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

-- 4. One score row per reviewed pair per run. Append-only; prior runs kept.
CREATE TABLE IF NOT EXISTS ma_screen_scores (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id bigint NOT NULL REFERENCES ma_screen_runs(id),
  pair_id bigint NOT NULL REFERENCES ma_screen_pairs(id),
  acquirer_ticker text NOT NULL,
  target_ticker   text NOT NULL,
  -- components: null = insufficient inputs (never fabricated)
  affordability numeric,
  relative_size numeric,
  financial_quality numeric,
  valuation_reasonableness numeric,
  composite numeric,
  coverage numeric NOT NULL,           -- fraction of components present (0–1)
  weights jsonb NOT NULL,              -- weights actually applied (renormalized)
  null_reasons jsonb,                  -- {component: reason} for missing inputs
  inputs jsonb,                        -- raw input values used, with source dates
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (run_id, pair_id)
);

CREATE INDEX IF NOT EXISTS idx_ma_screen_scores_run ON ma_screen_scores(run_id);
