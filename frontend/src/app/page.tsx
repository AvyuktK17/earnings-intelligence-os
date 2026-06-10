"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  api,
  type FilingsResponse,
  type OverviewResponse,
  type PeerRow,
  type PeersResponse,
} from "@/lib/api";
import FilingsTable from "@/components/FilingsTable";
import { ErrorBox, Loading, Panel, StatCard } from "@/components/Panel";
import { ValuationBadge } from "@/components/ValuationNote";
import { formatMultiple, formatPercent, formatUSD } from "@/lib/format";

function leader(
  peers: PeerRow[],
  key: keyof PeerRow,
): PeerRow | null {
  const ranked = peers
    .filter((p) => p[key] != null)
    .sort((a, b) => (b[key] as number) - (a[key] as number));
  return ranked[0] ?? null;
}

export default function OverviewPage() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [filings, setFilings] = useState<FilingsResponse | null>(null);
  const [peers, setPeers] = useState<PeersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [overviewData, filingsData] = await Promise.all([
          api.getOverview(),
          api.getFilings({ limit: 10 }),
        ]);
        if (cancelled) return;
        setOverview(overviewData);
        setFilings(filingsData);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load data.");
        }
      }
      // Peer fundamentals are additive; never block the pipeline overview.
      try {
        const peersData = await api.getPeers();
        if (!cancelled) setPeers(peersData);
      } catch {
        /* leave the peer panels out if the endpoint is unavailable */
      }
      if (!cancelled) setLoading(false);
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const topGrowth = useMemo(
    () => (peers ? leader(peers.peers, "yoy_revenue_growth") : null),
    [peers],
  );
  const topGross = useMemo(
    () => (peers ? leader(peers.peers, "gross_margin") : null),
    [peers],
  );
  const topFcf = useMemo(
    () => (peers ? leader(peers.peers, "free_cash_flow_margin") : null),
    [peers],
  );

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-lg font-semibold">Earnings Intelligence OS</h1>
        <p className="text-[12px] uppercase tracking-wider text-muted">
          Semiconductor Research Terminal
        </p>
      </header>

      {error && <ErrorBox message={error} />}
      {loading && !error && <Loading label="Loading overview…" />}

      {!loading && overview && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
            <StatCard
              label="Companies"
              value={overview.companies_count}
              hint="monitored watchlist"
            />
            <StatCard
              label="Filings tracked"
              value={overview.total_filings_count}
              hint="all forms, all time"
            />
            <StatCard
              label="Extraction ready"
              value={overview.extraction_ready_count}
              hint="earnings exhibits ingested"
            />
            <StatCard
              label="Pending review"
              value={overview.pending_grounded_claim_count}
              hint="grounded drafts awaiting analysts"
            />
            <StatCard
              label="Trusted claims"
              value={overview.trusted_claim_count}
              hint="human-reviewed and promoted"
            />
            <StatCard
              label="Stored briefs"
              value={overview.stored_brief_count}
              hint="versioned, evidence-linked"
            />
          </div>

          {peers && (
            <>
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                <StatCard
                  label="Top revenue growth"
                  value={topGrowth ? topGrowth.ticker : "—"}
                  hint={
                    topGrowth
                      ? `${formatPercent(topGrowth.yoy_revenue_growth)} YoY`
                      : undefined
                  }
                />
                <StatCard
                  label="Highest gross margin"
                  value={topGross ? topGross.ticker : "—"}
                  hint={
                    topGross
                      ? `${formatPercent(topGross.gross_margin)} gross`
                      : undefined
                  }
                />
                <StatCard
                  label="Strongest FCF margin"
                  value={topFcf ? topFcf.ticker : "—"}
                  hint={
                    topFcf
                      ? `${formatPercent(topFcf.free_cash_flow_margin)} FCF margin`
                      : undefined
                  }
                />
              </div>

              <Panel
                title="Peer fundamentals"
                actions={
                  <div className="flex items-center gap-3">
                    <ValuationBadge
                      date={peers.valuation_snapshot_dates?.[0] ?? null}
                    />
                    <Link
                      href="/peers"
                      className="text-[12px] text-info hover:text-accent hover:underline"
                    >
                      Full peer comparison →
                    </Link>
                  </div>
                }
              >
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[680px] text-left text-[13px]">
                    <thead>
                      <tr className="border-b border-edge text-[11px] uppercase tracking-wider text-muted">
                        <th className="py-1.5 pr-3 font-medium">Ticker</th>
                        <th className="py-1.5 pr-3 font-medium text-right">Revenue</th>
                        <th className="py-1.5 pr-3 font-medium text-right">YoY</th>
                        <th className="py-1.5 pr-3 font-medium text-right">Gross</th>
                        <th className="py-1.5 pr-3 font-medium text-right">Op.</th>
                        <th className="py-1.5 pr-3 font-medium text-right">EV/Rev</th>
                        <th className="py-1.5 font-medium text-right">FCF yld</th>
                      </tr>
                    </thead>
                    <tbody>
                      {peers.peers.map((row) => (
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
                          <td className="py-1.5 pr-3 text-right font-mono">{formatUSD(row.revenue)}</td>
                          <td className="py-1.5 pr-3 text-right font-mono">{formatPercent(row.yoy_revenue_growth)}</td>
                          <td className="py-1.5 pr-3 text-right font-mono">{formatPercent(row.gross_margin)}</td>
                          <td className="py-1.5 pr-3 text-right font-mono">{formatPercent(row.operating_margin)}</td>
                          <td className="py-1.5 pr-3 text-right font-mono text-accent">{formatMultiple(row.ev_to_ttm_revenue)}</td>
                          <td className="py-1.5 text-right font-mono">{formatPercent(row.free_cash_flow_yield)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
            </>
          )}

          <Panel title="Company status">
            <table className="w-full text-left text-[13px]">
              <thead>
                <tr className="border-b border-edge text-[11px] uppercase tracking-wider text-muted">
                  <th className="py-1.5 pr-3 font-medium">Ticker</th>
                  <th className="py-1.5 pr-3 font-medium">Company</th>
                  <th className="py-1.5 pr-3 font-medium text-right">
                    Extraction ready
                  </th>
                  <th className="py-1.5 pr-3 font-medium text-right">
                    Trusted claims
                  </th>
                  <th className="py-1.5 pr-3 font-medium">Latest brief</th>
                  <th className="py-1.5 pr-3 font-medium">Latest filing</th>
                  <th className="py-1.5 font-medium" />
                </tr>
              </thead>
              <tbody>
                {overview.companies.map((row) => (
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
                    <td className="py-1.5 pr-3">{row.company_name}</td>
                    <td className="py-1.5 pr-3 text-right font-mono">
                      {row.extraction_ready_count}
                    </td>
                    <td className="py-1.5 pr-3 text-right font-mono">
                      {row.trusted_claim_count}
                    </td>
                    <td className="py-1.5 pr-3 font-mono">
                      {row.latest_brief_version != null ? (
                        <Link
                          href={`/briefs/latest/${encodeURIComponent(row.ticker)}`}
                          className="text-info hover:text-accent hover:underline"
                        >
                          v{row.latest_brief_version}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-1.5 pr-3 font-mono text-muted">
                      {row.latest_filing_date ?? "—"}
                    </td>
                    <td className="py-1.5 text-right">
                      <Link
                        href={`/companies/${encodeURIComponent(row.ticker)}`}
                        className="text-[12px] text-info hover:text-accent hover:underline"
                      >
                        company page →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          {filings && (
            <Panel title="Latest filings">
              <FilingsTable filings={filings.filings} />
            </Panel>
          )}
        </>
      )}
    </div>
  );
}
