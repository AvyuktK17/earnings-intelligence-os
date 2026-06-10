"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import {
  api,
  ApiError,
  type CompanyDetail,
  type MetricsResponse,
  type PeerRow,
} from "@/lib/api";
import FilingsTable from "@/components/FilingsTable";
import { ErrorBox, Loading, Panel, StatCard } from "@/components/Panel";
import StatusBadge from "@/components/StatusBadge";
import { TrendLineChart } from "@/components/charts";
import { ValuationBadge, ValuationDisclaimer } from "@/components/ValuationNote";
import {
  formatMultiple,
  formatPercent,
  formatPrice,
  formatUSD,
  mergeSeriesByPeriod,
} from "@/lib/format";

function points(metrics: MetricsResponse | null, name: string) {
  return metrics?.metrics[name] ?? [];
}

function latest(metrics: MetricsResponse | null, name: string): number | null {
  const value = metrics?.latest_period_summary?.[name];
  return value == null ? null : value;
}

export default function CompanyPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker: rawTicker } = use(params);
  const ticker = decodeURIComponent(rawTicker).toUpperCase();

  const [detail, setDetail] = useState<CompanyDetail | null>(null);
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [peer, setPeer] = useState<PeerRow | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await api.getCompany(ticker);
        if (!cancelled) {
          setDetail(data);
          setNotFound(false);
          setError(null);
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true);
        } else {
          setError(
            err instanceof Error ? err.message : "Failed to load company.",
          );
        }
      }
      // Financials are best-effort and never block the pipeline view.
      try {
        const [metricsData, peers] = await Promise.all([
          api.getMetrics(ticker),
          api.getPeers(),
        ]);
        if (!cancelled) {
          setMetrics(metricsData);
          setPeer(peers.peers.find((p) => p.ticker === ticker) ?? null);
        }
      } catch {
        /* leave financials empty; the page degrades cleanly */
      }
      if (!cancelled) setLoading(false);
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [ticker]);

  const revenueData = mergeSeriesByPeriod([
    { name: "Revenue", points: points(metrics, "Revenue") },
  ]);
  const marginData = mergeSeriesByPeriod([
    { name: "Gross Margin", points: points(metrics, "Gross Margin") },
    { name: "Operating Margin", points: points(metrics, "Operating Margin") },
  ]);
  const fcfData = mergeSeriesByPeriod([
    { name: "FCF Margin", points: points(metrics, "Free-Cash-Flow Margin") },
  ]);
  const rdData = mergeSeriesByPeriod([
    { name: "R&D % of Revenue", points: points(metrics, "R&D as % of Revenue") },
  ]);
  const ttmData = mergeSeriesByPeriod([
    { name: "TTM Revenue", points: points(metrics, "TTM Revenue") },
    { name: "TTM Operating Income", points: points(metrics, "TTM Operating Income") },
  ]);

  const hasFinancials = metrics != null && metrics.metric_count > 0;

  const balanceRows: [string, number | null][] = [
    ["Cash & equivalents", latest(metrics, "Cash and Cash Equivalents")],
    ["Total debt", latest(metrics, "Total Debt")],
    ["Net cash (debt)", latest(metrics, "Net Cash (Debt)")],
    ["Operating cash flow", latest(metrics, "Operating Cash Flow")],
    ["Free cash flow", latest(metrics, "Free Cash Flow")],
    ["Capital expenditure", latest(metrics, "Capital Expenditure")],
  ];

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-lg font-semibold">
          {detail ? detail.company.company_name : ticker}
          <span className="ml-2 font-mono text-[14px] text-accent">{ticker}</span>
        </h1>
        <p className="text-[12px] text-muted">
          {detail?.company.business_model ?? "Company research workspace"}
          {detail && (
            <span className="ml-2 font-mono text-faint">
              CIK {detail.company.cik}
            </span>
          )}
        </p>
      </header>

      {error && <ErrorBox message={error} />}
      {loading && !error && <Loading label="Loading company…" />}

      {notFound && (
        <Panel>
          <div className="py-8 text-center">
            <p className="text-[14px] text-muted">
              {ticker} is not on the monitored watchlist.
            </p>
            <p className="mt-1 text-[12px] text-faint">
              The watchlist currently covers the companies listed in the sidebar.
            </p>
          </div>
        </Panel>
      )}

      {detail && (
        <>
          {/* --- Financial KPIs ------------------------------------------- */}
          {hasFinancials && (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
              <StatCard
                label="Revenue"
                value={formatUSD(latest(metrics, "Revenue"))}
                hint={`${metrics?.latest_period ?? ""} · YoY ${formatPercent(
                  latest(metrics, "YoY Revenue Growth"),
                )}`}
              />
              <StatCard
                label="Gross margin"
                value={formatPercent(latest(metrics, "Gross Margin"))}
                hint="latest quarter"
              />
              <StatCard
                label="Operating margin"
                value={formatPercent(latest(metrics, "Operating Margin"))}
                hint="latest quarter"
              />
              <StatCard
                label="Diluted EPS"
                value={formatPrice(latest(metrics, "Diluted EPS"))}
                hint="latest quarter"
              />
              <StatCard
                label="FCF margin"
                value={formatPercent(latest(metrics, "Free-Cash-Flow Margin"))}
                hint="latest quarter"
              />
            </div>
          )}

          {/* --- Trend charts -------------------------------------------- */}
          {hasFinancials ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <Panel title="Revenue — quarterly">
                <TrendLineChart data={revenueData} lines={[{ key: "Revenue", color: "#e8b93e" }]} format={formatUSD} />
              </Panel>
              <Panel title="Gross & operating margin">
                <TrendLineChart
                  data={marginData}
                  lines={[
                    { key: "Gross Margin", color: "#4cc38a" },
                    { key: "Operating Margin", color: "#539bf5" },
                  ]}
                  format={formatPercent}
                />
              </Panel>
              <Panel title="Free-cash-flow margin">
                <TrendLineChart data={fcfData} lines={[{ key: "FCF Margin", color: "#a371f7" }]} format={formatPercent} />
              </Panel>
              <Panel title="R&D intensity (% of revenue)">
                <TrendLineChart data={rdData} lines={[{ key: "R&D % of Revenue", color: "#e5534b" }]} format={formatPercent} />
              </Panel>
              <Panel title="TTM revenue & operating income">
                <TrendLineChart
                  data={ttmData}
                  lines={[
                    { key: "TTM Revenue", color: "#e8b93e" },
                    { key: "TTM Operating Income", color: "#539bf5" },
                  ]}
                  format={formatUSD}
                />
              </Panel>
              <Panel title="Balance sheet & cash flow — latest quarter">
                <table className="w-full text-left text-[13px]">
                  <tbody>
                    {balanceRows.map(([label, value]) => (
                      <tr key={label} className="border-b border-edge/50 last:border-b-0">
                        <td className="py-1.5 pr-3 text-muted">{label}</td>
                        <td className="py-1.5 text-right font-mono">{formatUSD(value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
            </div>
          ) : (
            !loading && (
              <Panel title="Financials">
                <p className="px-1 py-3 text-[13px] text-muted">
                  Historical fundamentals are not yet available for {ticker}.
                </p>
              </Panel>
            )
          )}

          {/* --- Valuation snapshot -------------------------------------- */}
          {peer && (
            <Panel
              title="Valuation snapshot"
              actions={<ValuationBadge date={peer.valuation_snapshot_date} />}
            >
              <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-[13px] lg:grid-cols-4">
                <Field label="Share price" value={formatPrice(peer.share_price)} />
                <Field label="Market cap" value={formatUSD(peer.market_cap)} />
                <Field label="Enterprise value" value={formatUSD(peer.enterprise_value)} />
                <Field label="EV / TTM revenue" value={formatMultiple(peer.ev_to_ttm_revenue)} accent />
                <Field label="EV / TTM op. income" value={formatMultiple(peer.ev_to_ttm_operating_income)} accent />
                <Field label="Price / TTM FCF" value={formatMultiple(peer.price_to_ttm_fcf)} accent />
                <Field label="FCF yield" value={formatPercent(peer.free_cash_flow_yield)} accent />
                <Field label="Debt measure" value={peer.debt_measure ?? "—"} mono={false} />
              </div>
              {peer.valuation_notes && (
                <p className="mt-3 text-[12px] text-muted">{peer.valuation_notes}</p>
              )}
              <div className="mt-3">
                <ValuationDisclaimer />
              </div>
            </Panel>
          )}

          {/* --- Pipeline summary (existing) ----------------------------- */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="Filings tracked"
              value={detail.filings_count}
              hint={`${detail.chunked_filings_count} fully chunked`}
            />
            <StatCard
              label="Extraction ready"
              value={detail.extraction_ready_count}
              hint="earnings exhibits ingested"
            />
            <StatCard
              label="Trusted claims"
              value={detail.trusted_claim_count}
              hint="human-reviewed and promoted"
            />
            <StatCard
              label="Latest brief"
              value={detail.latest_brief ? `v${detail.latest_brief.version_number}` : "—"}
              hint={
                detail.latest_brief
                  ? `${detail.latest_brief.trusted_claim_count} trusted claims`
                  : "no brief stored yet"
              }
            />
          </div>

          <Panel
            title="Latest brief"
            actions={
              detail.latest_brief ? (
                <Link
                  href={`/briefs/latest/${encodeURIComponent(ticker)}`}
                  className="text-[12px] text-info hover:text-accent hover:underline"
                >
                  View latest brief →
                </Link>
              ) : undefined
            }
          >
            {detail.latest_brief ? (
              <div className="flex flex-wrap gap-x-5 gap-y-1 text-[13px]">
                <span className="font-mono text-accent">
                  v{detail.latest_brief.version_number}
                </span>
                <span className="font-mono text-muted">
                  {detail.latest_brief.accession_number}
                </span>
                <span className="text-muted">
                  {detail.latest_brief.trusted_claim_count} trusted ·{" "}
                  {detail.latest_brief.factual_claim_count} factual ·{" "}
                  {detail.latest_brief.interpretive_claim_count} interpretive
                </span>
                <span className="font-mono text-faint">
                  generated{" "}
                  {new Date(detail.latest_brief.generated_at).toLocaleString()}
                </span>
              </div>
            ) : (
              <p className="px-1 py-3 text-[13px] text-muted">
                No brief stored yet. Extract, review, and promote claims from an{" "}
                <Link href="/extraction-ready" className="text-info hover:underline">
                  extraction-ready filing
                </Link>
                , then generate the first version.
              </p>
            )}
          </Panel>

          <Panel title={`Extraction-ready filings · ${detail.extraction_ready_count}`}>
            {detail.extraction_ready.length === 0 ? (
              <p className="px-1 py-3 text-[13px] text-muted">
                No earnings exhibits ingested yet for {ticker}. The exhibit
                worker checks new 8-K filings automatically.
              </p>
            ) : (
              <table className="w-full text-left text-[13px]">
                <thead>
                  <tr className="border-b border-edge text-[11px] uppercase tracking-wider text-muted">
                    <th className="py-1.5 pr-3 font-medium">Accession</th>
                    <th className="py-1.5 pr-3 font-medium">Filed</th>
                    <th className="py-1.5 pr-3 font-medium">Exhibit</th>
                    <th className="py-1.5 pr-3 font-medium text-right">Chunks</th>
                    <th className="py-1.5 font-medium">Extraction</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.extraction_ready.map((row) => (
                    <tr
                      key={row.accession_number}
                      className="border-b border-edge/50 last:border-b-0"
                    >
                      <td className="py-1.5 pr-3 font-mono">
                        <Link
                          href={`/filings/${encodeURIComponent(row.accession_number)}`}
                          className="text-info hover:text-accent hover:underline"
                        >
                          {row.accession_number}
                        </Link>
                      </td>
                      <td className="py-1.5 pr-3 font-mono text-muted">
                        {row.filing_date ?? "—"}
                      </td>
                      <td className="py-1.5 pr-3 font-mono text-[12px]">
                        {row.filename ?? "—"}
                      </td>
                      <td className="py-1.5 pr-3 text-right font-mono">
                        {row.chunk_count}
                      </td>
                      <td className="py-1.5">
                        <StatusBadge status={row.claim_extraction_status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>

          <Panel title="Recent filings">
            <FilingsTable filings={detail.recent_filings} showReportDate />
          </Panel>
        </>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  accent,
  mono = true,
}: {
  label: string;
  value: string;
  accent?: boolean;
  mono?: boolean;
}) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wider text-muted">{label}</div>
      <div
        className={`mt-0.5 ${mono ? "font-mono" : ""} text-[15px] ${
          accent ? "text-accent" : "text-foreground"
        }`}
      >
        {value}
      </div>
    </div>
  );
}
