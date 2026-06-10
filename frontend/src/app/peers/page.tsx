"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, type PeersResponse, type PeerRow } from "@/lib/api";
import { ErrorBox, Loading, Panel } from "@/components/Panel";
import { PeerBarChart } from "@/components/charts";
import { ValuationBadge, ValuationDisclaimer } from "@/components/ValuationNote";
import { formatMultiple, formatPercent, formatUSD } from "@/lib/format";

// Metrics the ranked bar chart can sort/compare on, with their formatter and
// whether a higher value ranks first.
const RANKED_METRICS: {
  key: keyof PeerRow;
  label: string;
  format: (v: number) => string;
  descending: boolean;
}[] = [
  { key: "ttm_revenue", label: "TTM Revenue", format: formatUSD, descending: true },
  { key: "yoy_revenue_growth", label: "YoY Revenue Growth", format: (v) => formatPercent(v), descending: true },
  { key: "gross_margin", label: "Gross Margin", format: (v) => formatPercent(v), descending: true },
  { key: "operating_margin", label: "Operating Margin", format: (v) => formatPercent(v), descending: true },
  { key: "free_cash_flow_margin", label: "FCF Margin", format: (v) => formatPercent(v), descending: true },
  { key: "rd_as_pct_of_revenue", label: "R&D % of Revenue", format: (v) => formatPercent(v), descending: true },
  { key: "free_cash_flow_yield", label: "FCF Yield", format: (v) => formatPercent(v), descending: true },
  { key: "ev_to_ttm_revenue", label: "EV / TTM Revenue", format: formatMultiple, descending: false },
  { key: "ev_to_ttm_operating_income", label: "EV / TTM Op. Income", format: formatMultiple, descending: false },
  { key: "price_to_ttm_fcf", label: "Price / TTM FCF", format: formatMultiple, descending: false },
];

function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return (
    <th className={`py-1.5 pr-3 font-medium ${right ? "text-right" : ""}`}>
      {children}
    </th>
  );
}

export default function PeersPage() {
  const [data, setData] = useState<PeersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [metricKey, setMetricKey] = useState<string>("ttm_revenue");

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
      .map((row) => ({ ticker: row.ticker, value: row[selected.key] as number | null }))
      .sort((a, b) => {
        if (a.value == null) return 1;
        if (b.value == null) return -1;
        return selected.descending ? b.value - a.value : a.value - b.value;
      });
  }, [data, selected]);

  const snapshotDate = data?.valuation_snapshot_dates?.[0] ?? null;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">Peer Comparison</h1>
          <p className="text-[12px] uppercase tracking-wider text-muted">
            Latest-period semiconductor fundamentals & valuation
          </p>
        </div>
        <ValuationBadge date={snapshotDate} />
      </header>

      {error && <ErrorBox message={error} />}
      {loading && !error && <Loading label="Loading peer comparison…" />}

      {data && (
        <>
          <Panel
            title="Ranked comparison"
            actions={
              <select
                value={metricKey}
                onChange={(e) => setMetricKey(e.target.value)}
                className="rounded border border-edge bg-surface-raised px-2 py-1 text-[12px] text-foreground"
              >
                {RANKED_METRICS.map((m) => (
                  <option key={String(m.key)} value={String(m.key)}>
                    {m.label}
                  </option>
                ))}
              </select>
            }
          >
            <PeerBarChart data={chartData} format={selected.format} />
            <p className="mt-1 text-[11px] text-faint">
              {selected.label} ·{" "}
              {selected.descending ? "higher ranks first" : "lower ranks first"}.
              Multiples derive from the dated valuation snapshot below.
            </p>
          </Panel>

          <Panel title="Peer table — latest reported quarter">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1100px] text-left text-[12.5px]">
                <thead>
                  <tr className="border-b border-edge text-[11px] uppercase tracking-wider text-muted">
                    <Th>Ticker</Th>
                    <Th>Model</Th>
                    <Th right>Revenue</Th>
                    <Th right>YoY</Th>
                    <Th right>Gross</Th>
                    <Th right>Op.</Th>
                    <Th right>FCF mgn</Th>
                    <Th right>R&amp;D%</Th>
                    <Th right>TTM Rev</Th>
                    <Th right>Mkt cap</Th>
                    <Th right>EV</Th>
                    <Th right>EV/Rev</Th>
                    <Th right>EV/OpInc</Th>
                    <Th right>P/FCF</Th>
                    <Th right>FCF yld</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.peers.map((row) => (
                    <tr
                      key={row.ticker}
                      className="border-b border-edge/50 last:border-b-0 hover:bg-surface-raised"
                    >
                      <td className="py-1.5 pr-3 font-mono font-medium">
                        <Link
                          href={`/companies/${encodeURIComponent(row.ticker)}`}
                          className="text-accent hover:underline"
                        >
                          {row.ticker}
                        </Link>
                      </td>
                      <td className="py-1.5 pr-3 text-[11px] text-muted">
                        {row.business_model ?? "—"}
                      </td>
                      <td className="py-1.5 pr-3 text-right font-mono">{formatUSD(row.revenue)}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">{formatPercent(row.yoy_revenue_growth)}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">{formatPercent(row.gross_margin)}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">{formatPercent(row.operating_margin)}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">{formatPercent(row.free_cash_flow_margin)}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">{formatPercent(row.rd_as_pct_of_revenue)}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">{formatUSD(row.ttm_revenue)}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">{formatUSD(row.market_cap)}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">{formatUSD(row.enterprise_value)}</td>
                      <td className="py-1.5 pr-3 text-right font-mono text-accent">{formatMultiple(row.ev_to_ttm_revenue)}</td>
                      <td className="py-1.5 pr-3 text-right font-mono text-accent">{formatMultiple(row.ev_to_ttm_operating_income)}</td>
                      <td className="py-1.5 pr-3 text-right font-mono text-accent">{formatMultiple(row.price_to_ttm_fcf)}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">{formatPercent(row.free_cash_flow_yield)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1">
              <ValuationBadge date={snapshotDate} />
              <ValuationDisclaimer text={data.valuation_disclaimer} />
            </div>
          </Panel>

          <Panel title="Comparability notes">
            <ul className="space-y-2 text-[12.5px]">
              {data.comparability_notes.map((note) => (
                <li key={note.ticker} className="flex gap-2">
                  <span className="font-mono font-medium text-accent">
                    {note.ticker}
                  </span>
                  <span className="text-muted">
                    <span className="text-foreground">{note.business_model ?? "—"}</span>
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
              Margins, growth, and TTM figures are computed deterministically
              from audited SEC-sourced fundamentals; debt measures differ across
              issuers as noted, so leverage-sensitive multiples are not strictly
              like-for-like.
            </p>
          </Panel>
        </>
      )}
    </div>
  );
}
