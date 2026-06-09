"use client";

import { useEffect, useState } from "react";
import { api, type FilingsResponse } from "@/lib/api";
import FilingsTable from "@/components/FilingsTable";
import { ErrorBox, Loading, Panel } from "@/components/Panel";

const TICKERS = ["", "QCOM", "AMD", "NVDA", "INTC", "AVGO"];
const STATUSES = ["", "detected", "downloaded", "parsed", "chunked", "failed"];
const LIMITS = [10, 25, 50, 100];

const selectClass =
  "rounded border border-edge bg-surface-raised px-2 py-1 font-mono text-[12px] " +
  "text-foreground focus:border-accent focus:outline-none";

export default function FilingsPage() {
  const [ticker, setTicker] = useState("");
  const [status, setStatus] = useState("");
  const [limit, setLimit] = useState(25);
  const [data, setData] = useState<FilingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);

  const queryKey = `${ticker}|${status}|${limit}`;
  const loading = loadedFor !== queryKey;

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const result = await api.getFilings({
          ticker: ticker || undefined,
          status: status || undefined,
          limit,
        });
        if (!cancelled) {
          setData(result);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load filings.",
          );
        }
      }
      if (!cancelled) setLoadedFor(queryKey);
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [ticker, status, limit, queryKey]);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-lg font-semibold">Filings</h1>
        <p className="text-[12px] text-muted">
          SEC EDGAR filings detected by the monitor
        </p>
      </header>

      <Panel
        title={`Filing feed${data ? ` · ${data.count} shown` : ""}`}
        actions={
          <div className="flex items-center gap-2">
            <label className="text-[11px] uppercase tracking-wider text-muted">
              Ticker
              <select
                className={`ml-1.5 ${selectClass}`}
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
              >
                {TICKERS.map((t) => (
                  <option key={t} value={t}>
                    {t || "all"}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-[11px] uppercase tracking-wider text-muted">
              Status
              <select
                className={`ml-1.5 ${selectClass}`}
                value={status}
                onChange={(e) => setStatus(e.target.value)}
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s || "all"}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-[11px] uppercase tracking-wider text-muted">
              Limit
              <select
                className={`ml-1.5 ${selectClass}`}
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
              >
                {LIMITS.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          </div>
        }
      >
        {error && <ErrorBox message={error} />}
        {loading && !error && <Loading label="Loading filings…" />}
        {!loading && !error && data && (
          <FilingsTable filings={data.filings} showReportDate />
        )}
      </Panel>
    </div>
  );
}
