"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, type PeersResponse, type PeerRow } from "@/lib/api";
import { ErrorBox, Panel } from "@/components/Panel";
import ResearchHeader from "@/components/ResearchHeader";
import ChartPanel from "@/components/ChartPanel";
import { DataTable, TR, TD } from "@/components/DataTable";
import { LoadingSkeleton } from "@/components/States";
import { PeerBarChart } from "@/components/charts";
import { ValuationBadge, ValuationDisclaimer } from "@/components/ValuationNote";
import { formatMultiple, formatPercent, formatUSD } from "@/lib/format";

type Col = {
  key: keyof PeerRow;
  label: string;
  format: (v: number) => string;
  // Whether a higher value is "better" / ranks first by default.
  descending: boolean;
  rankable?: boolean;
};

const COLUMNS: Col[] = [
  { key: "revenue", label: "Revenue", format: formatUSD, descending: true },
  { key: "yoy_revenue_growth", label: "YoY", format: formatPercent, descending: true },
  { key: "gross_margin", label: "Gross", format: formatPercent, descending: true },
  { key: "operating_margin", label: "Op.", format: formatPercent, descending: true },
  { key: "free_cash_flow_margin", label: "FCF mgn", format: formatPercent, descending: true },
  { key: "rd_as_pct_of_revenue", label: "R&D%", format: formatPercent, descending: true },
  { key: "ttm_revenue", label: "TTM Rev", format: formatUSD, descending: true, rankable: true },
  { key: "market_cap", label: "Mkt cap", format: formatUSD, descending: true },
  { key: "enterprise_value", label: "EV", format: formatUSD, descending: true },
  { key: "ev_to_ttm_revenue", label: "EV/Rev", format: formatMultiple, descending: false },
  { key: "ev_to_ttm_operating_income", label: "EV/OpInc", format: formatMultiple, descending: false },
  { key: "price_to_ttm_fcf", label: "P/FCF", format: formatMultiple, descending: false },
  { key: "free_cash_flow_yield", label: "FCF yld", format: formatPercent, descending: true },
];

// Metrics offered in the ranked bar chart (a readable subset).
const RANKED_METRICS: Col[] = [
  { key: "ttm_revenue", label: "TTM Revenue", format: formatUSD, descending: true },
  { key: "yoy_revenue_growth", label: "YoY Revenue Growth", format: formatPercent, descending: true },
  { key: "gross_margin", label: "Gross Margin", format: formatPercent, descending: true },
  { key: "operating_margin", label: "Operating Margin", format: formatPercent, descending: true },
  { key: "free_cash_flow_margin", label: "FCF Margin", format: formatPercent, descending: true },
  { key: "rd_as_pct_of_revenue", label: "R&D % of Revenue", format: formatPercent, descending: true },
  { key: "free_cash_flow_yield", label: "FCF Yield", format: formatPercent, descending: true },
  { key: "ev_to_ttm_revenue", label: "EV / TTM Revenue", format: formatMultiple, descending: false },
  { key: "ev_to_ttm_operating_income", label: "EV / TTM Op. Income", format: formatMultiple, descending: false },
  { key: "price_to_ttm_fcf", label: "Price / TTM FCF", format: formatMultiple, descending: false },
];

const MULTIPLE_KEYS = new Set<keyof PeerRow>([
  "ev_to_ttm_revenue",
  "ev_to_ttm_operating_income",
  "price_to_ttm_fcf",
]);

// Columns where the sign carries financial meaning (green positive / red
// negative) — growth and yield read as performance states.
const SIGNED_KEYS = new Set<keyof PeerRow>([
  "yoy_revenue_growth",
  "free_cash_flow_yield",
]);

function cellTone(
  key: keyof PeerRow,
  value: number | null,
): "accent" | "positive" | "negative" | undefined {
  if (MULTIPLE_KEYS.has(key)) return "accent";
  if (SIGNED_KEYS.has(key) && value != null)
    return value > 0 ? "positive" : value < 0 ? "negative" : undefined;
  return undefined;
}

export default function PeersPage() {
  const [data, setData] = useState<PeersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [metricKey, setMetricKey] = useState<keyof PeerRow>("ttm_revenue");
  const [sortKey, setSortKey] = useState<keyof PeerRow>("ttm_revenue");
  const [sortDesc, setSortDesc] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await api.getPeers();
        if (!cancelled) setData(result);
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Failed to load peers.");
      }
      if (!cancelled) setLoading(false);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = RANKED_METRICS.find((m) => m.key === metricKey)!;

  const chartData = useMemo(() => {
    if (!data) return [];
    return data.peers
      .map((row) => ({ ticker: row.ticker, value: row[metricKey] as number | null }))
      .sort((a, b) => {
        if (a.value == null) return 1;
        if (b.value == null) return -1;
        return selected.descending ? b.value - a.value : a.value - b.value;
      });
  }, [data, metricKey, selected]);

  const sortedPeers = useMemo(() => {
    if (!data) return [];
    return [...data.peers].sort((a, b) => {
      const av = a[sortKey] as number | string | null;
      const bv = b[sortKey] as number | string | null;
      // Missing values always sort last regardless of direction.
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "string" || typeof bv === "string") {
        return sortDesc
          ? String(bv).localeCompare(String(av))
          : String(av).localeCompare(String(bv));
      }
      return sortDesc ? bv - av : av - bv;
    });
  }, [data, sortKey, sortDesc]);

  function toggleSort(col: Col) {
    if (col.key === sortKey) {
      setSortDesc((d) => !d);
    } else {
      setSortKey(col.key);
      setSortDesc(col.descending);
    }
  }

  const snapshotDate = data?.valuation_snapshot_dates?.[0] ?? null;

  return (
    <div className="space-y-5">
      <ResearchHeader
        eyebrow="Markets"
        title="Peer Comparison"
        description="Latest-period semiconductor fundamentals and dated valuation multiples, computed deterministically from audited SEC-sourced data."
        actions={<ValuationBadge date={snapshotDate} />}
      />

      {error && <ErrorBox message={error} />}
      {loading && !error && <LoadingSkeleton rows={6} />}

      {data && !loading && (
        <>
          <ChartPanel
            title="Ranked comparison"
            control={
              <select
                aria-label="Ranking metric"
                value={String(metricKey)}
                onChange={(e) => setMetricKey(e.target.value as keyof PeerRow)}
                className="rounded border border-edge bg-surface-raised px-2 py-1 text-[12px] text-foreground focus:border-accent focus:outline-none"
              >
                {RANKED_METRICS.map((m) => (
                  <option key={String(m.key)} value={String(m.key)}>
                    {m.label}
                  </option>
                ))}
              </select>
            }
            caption={
              <>
                {selected.label} ·{" "}
                {selected.descending ? "higher ranks first" : "lower ranks first"}.
                Multiples derive from the dated valuation snapshot below; missing
                inputs are omitted rather than estimated.
              </>
            }
          >
            <PeerBarChart data={chartData} format={selected.format} />
          </ChartPanel>

          <Panel title="Peer table — latest reported quarter">
            <DataTable minWidth={1080} className="tnum text-[12.5px]">
              <thead>
                <tr className="border-b border-edge text-[11px] uppercase tracking-wider text-muted">
                  <th scope="col" className="py-1.5 pr-3 font-medium">
                    Ticker
                  </th>
                  <th scope="col" className="py-1.5 pr-3 font-medium">
                    Model
                  </th>
                  {COLUMNS.map((col) => {
                    const isSorted = col.key === sortKey;
                    return (
                      <th
                        key={String(col.key)}
                        scope="col"
                        className="py-1.5 pr-3 text-right font-medium"
                      >
                        <button
                          onClick={() => toggleSort(col)}
                          className={`inline-flex items-center gap-0.5 transition-colors hover:text-foreground ${
                            isSorted ? "text-accent" : ""
                          }`}
                          aria-label={`Sort by ${col.label}`}
                        >
                          {col.label}
                          <span className="w-2 text-[9px]">
                            {isSorted ? (sortDesc ? "▼" : "▲") : ""}
                          </span>
                        </button>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {sortedPeers.map((row) => (
                  <TR key={row.ticker}>
                    <TD mono className="font-medium">
                      <Link
                        href={`/companies/${encodeURIComponent(row.ticker)}`}
                        className="text-accent hover:underline"
                      >
                        {row.ticker}
                      </Link>
                    </TD>
                    <TD>
                      {row.business_model ? (
                        <span className="inline-block rounded border border-edge px-1.5 py-px text-[10.5px] text-muted">
                          {row.business_model}
                        </span>
                      ) : (
                        <span className="text-faint">—</span>
                      )}
                    </TD>
                    {COLUMNS.map((col) => (
                      <TD
                        key={String(col.key)}
                        right
                        mono
                        tone={cellTone(col.key, row[col.key] as number | null)}
                      >
                        {col.format(row[col.key] as number)}
                      </TD>
                    ))}
                  </TR>
                ))}
              </tbody>
            </DataTable>
            <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1">
              <ValuationBadge date={snapshotDate} />
              <ValuationDisclaimer text={data.valuation_disclaimer} />
            </div>
          </Panel>

          <Panel title="Comparability notes">
            <details className="group">
              <summary className="cursor-pointer list-none text-[12px] text-info hover:text-accent">
                <span className="group-open:hidden">
                  Show comparability notes ({data.comparability_notes.length}) →
                </span>
                <span className="hidden group-open:inline">
                  Hide comparability notes ↓
                </span>
              </summary>
              <div className="mt-3">
            <ul className="space-y-2 text-[12.5px]">
              {data.comparability_notes.map((note) => (
                <li key={note.ticker} className="flex flex-wrap gap-2">
                  <span className="font-mono font-medium text-accent">
                    {note.ticker}
                  </span>
                  <span className="text-muted">
                    <span className="text-foreground">
                      {note.business_model ?? "—"}
                    </span>
                    {note.debt_measure && (
                      <span className="ml-2 font-mono text-faint">
                        debt: {note.debt_measure}
                      </span>
                    )}
                    {note.notes && <span className="ml-2">{note.notes}</span>}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-[11px] text-faint">
              Margins, growth, and TTM figures are computed deterministically from
              audited SEC-sourced fundamentals; debt measures differ across
              issuers as noted, so leverage-sensitive multiples are not strictly
              like-for-like. This is not a live market feed.
            </p>
              </div>
            </details>
          </Panel>
        </>
      )}
    </div>
  );
}
