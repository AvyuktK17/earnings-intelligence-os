"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import {
  api,
  ApiError,
  type ComparabilityNote,
  type CompanyDetail,
  type EvidenceItem,
  type MetricsResponse,
  type PeerRow,
  type ReportDetail,
} from "@/lib/api";
import FilingsTable from "@/components/FilingsTable";
import { ErrorBox, Panel } from "@/components/Panel";
import ResearchHeader from "@/components/ResearchHeader";
import MetricCard from "@/components/MetricCard";
import StatusPill from "@/components/StatusPill";
import { ReportTypeBadge, SourceBadge } from "@/components/Badges";
import { DataTable, TH, THead, TR, TD } from "@/components/DataTable";
import { EmptyState, LoadingSkeleton } from "@/components/States";
import { TrendLineChart } from "@/components/charts";
import { ValuationBadge, ValuationDisclaimer } from "@/components/ValuationNote";
import {
  formatMultiple,
  formatPercent,
  formatPrice,
  formatUSD,
  mergeSeriesByPeriod,
} from "@/lib/format";

const TABS = ["Overview", "Financials", "Filings", "Evidence", "Reports"] as const;
type Tab = (typeof TABS)[number];

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
  const [note, setNote] = useState<ComparabilityNote | null>(null);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("Overview");

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
        if (err instanceof ApiError && err.status === 404) setNotFound(true);
        else
          setError(err instanceof Error ? err.message : "Failed to load company.");
      }
      // Best-effort additive data; never blocks the pipeline view.
      const [metricsRes, peersRes, evidenceRes, reportRes] =
        await Promise.allSettled([
          api.getMetrics(ticker),
          api.getPeers(),
          api.getEvidence({ ticker, limit: 50 }),
          api.getLatestReport(ticker),
        ]);
      if (!cancelled) {
        if (metricsRes.status === "fulfilled") setMetrics(metricsRes.value);
        if (peersRes.status === "fulfilled") {
          setPeer(peersRes.value.peers.find((p) => p.ticker === ticker) ?? null);
          setNote(
            peersRes.value.comparability_notes.find((n) => n.ticker === ticker) ??
              null,
          );
        }
        if (evidenceRes.status === "fulfilled")
          setEvidence(evidenceRes.value.evidence);
        if (reportRes.status === "fulfilled") setReport(reportRes.value);
        setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [ticker]);

  const hasFinancials = metrics != null && metrics.metric_count > 0;

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
      <ResearchHeader
        eyebrow="Company"
        title={
          <span>
            {detail ? detail.company.company_name : ticker}
            <span className="ml-2 font-mono text-[15px] text-accent">{ticker}</span>
          </span>
        }
        description={
          detail ? (
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span>{detail.company.business_model ?? "—"}</span>
              <span className="font-mono text-faint">CIK {detail.company.cik}</span>
              {detail.recent_filings[0]?.filing_date && (
                <span className="font-mono text-faint">
                  latest filing {detail.recent_filings[0].filing_date}
                </span>
              )}
            </span>
          ) : (
            "Company research workspace"
          )
        }
        actions={peer && <ValuationBadge date={peer.valuation_snapshot_date} />}
      />

      {error && <ErrorBox message={error} />}
      {loading && !error && <LoadingSkeleton rows={6} />}

      {notFound && !loading && (
        <EmptyState
          title={`${ticker} is not on the monitored watchlist.`}
          hint="The watchlist currently covers the companies listed in the sidebar."
        />
      )}

      {detail && !loading && (
        <>
          {/* --- Pipeline KPIs (always visible) --------------------------- */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <MetricCard
              label="Filings tracked"
              value={detail.filings_count}
              hint={`${detail.chunked_filings_count} fully chunked`}
            />
            <MetricCard
              label="Extraction ready"
              value={detail.extraction_ready_count}
              hint="exhibits ingested"
              tone="info"
            />
            <MetricCard
              label="Trusted claims"
              value={detail.trusted_claim_count}
              hint="reviewed + promoted"
              tone="positive"
            />
            <MetricCard
              label="Latest brief"
              value={detail.latest_brief ? `v${detail.latest_brief.version_number}` : "—"}
              hint={
                detail.latest_brief
                  ? `${detail.latest_brief.trusted_claim_count} trusted claims`
                  : "no brief stored"
              }
            />
          </div>

          {/* --- Tabs ----------------------------------------------------- */}
          <div
            role="tablist"
            className="flex flex-wrap gap-1 border-b border-edge"
          >
            {TABS.map((t) => (
              <button
                key={t}
                role="tab"
                aria-selected={tab === t}
                onClick={() => setTab(t)}
                className={`-mb-px rounded-t border-b-2 px-3 py-1.5 text-[12.5px] transition-colors ${
                  tab === t
                    ? "border-accent font-medium text-accent"
                    : "border-transparent text-muted hover:text-foreground"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* --- Overview tab --------------------------------------------- */}
          {tab === "Overview" && (
            <div className="space-y-5">
              {hasFinancials && (
                <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
                  <MetricCard
                    label="Revenue"
                    value={formatUSD(latest(metrics, "Revenue"))}
                    hint={`${metrics?.latest_period ?? ""} · YoY ${formatPercent(
                      latest(metrics, "YoY Revenue Growth"),
                    )}`}
                  />
                  <MetricCard
                    label="Gross margin"
                    value={formatPercent(latest(metrics, "Gross Margin"))}
                    hint="latest quarter"
                  />
                  <MetricCard
                    label="Operating margin"
                    value={formatPercent(latest(metrics, "Operating Margin"))}
                    hint="latest quarter"
                  />
                  <MetricCard
                    label="Diluted EPS"
                    value={formatPrice(latest(metrics, "Diluted EPS"))}
                    hint="latest quarter"
                  />
                  <MetricCard
                    label="FCF margin"
                    value={formatPercent(latest(metrics, "Free-Cash-Flow Margin"))}
                    hint="latest quarter"
                  />
                </div>
              )}

              {hasFinancials && (
                <Panel
                  title="Revenue trajectory — quarterly"
                  actions={
                    <button
                      onClick={() => setTab("Financials")}
                      className="text-[12px] text-info hover:text-accent hover:underline"
                    >
                      All charts →
                    </button>
                  }
                >
                  <TrendLineChart
                    data={revenueData}
                    lines={[{ key: "Revenue", color: "#e8b93e" }]}
                    format={formatUSD}
                    height={200}
                  />
                </Panel>
              )}

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

              <div className="grid gap-4 lg:grid-cols-3">
                <Panel
                  title={`Latest trusted evidence · ${evidence.length}`}
                  actions={
                    <Link
                      href={`/evidence?ticker=${encodeURIComponent(ticker)}`}
                      className="text-[12px] text-info hover:text-accent hover:underline"
                    >
                      Evidence Explorer →
                    </Link>
                  }
                >
                  <div className="lg:col-span-2">
                    {evidence.length > 0 ? (
                      <ul className="space-y-2.5">
                        {evidence.slice(0, 3).map((item) => (
                          <li
                            key={item.qualitative_claim_id}
                            className="border-b border-hairline/60 pb-2.5 last:border-b-0 last:pb-0"
                          >
                            <div className="mb-1 flex flex-wrap items-center gap-2 text-[11px]">
                              <span className="text-muted">{item.theme}</span>
                              <span className="font-mono text-faint">
                                conf {item.confidence ?? "—"}
                              </span>
                            </div>
                            <p className="text-[13px] leading-relaxed">
                              {item.claim}
                            </p>
                            <div className="mt-1.5">
                              <SourceBadge
                                accession={item.accession_number}
                                chunkId={item.source_chunk_id}
                                secUrl={item.sec_url}
                                filingDate={item.filing_date}
                              />
                            </div>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="py-2 text-[12px] text-muted">
                        No trusted, promoted claims for {ticker} yet.
                      </p>
                    )}
                  </div>
                </Panel>

                <Panel title="Latest filing">
                  {detail.recent_filings[0] ? (
                    <dl className="space-y-2 text-[12.5px]">
                      <FilingField
                        label="Form"
                        value={detail.recent_filings[0].form}
                      />
                      <FilingField
                        label="Filed"
                        value={detail.recent_filings[0].filing_date ?? "—"}
                      />
                      <FilingField
                        label="Status"
                        value={detail.recent_filings[0].processing_status}
                      />
                      <div className="pt-1">
                        <Link
                          href={`/filings/${encodeURIComponent(
                            detail.recent_filings[0].accession_number,
                          )}`}
                          className="font-mono text-[12px] text-info hover:text-accent hover:underline"
                        >
                          {detail.recent_filings[0].accession_number} →
                        </Link>
                      </div>
                    </dl>
                  ) : (
                    <p className="py-2 text-[12px] text-muted">
                      No filings tracked yet.
                    </p>
                  )}
                </Panel>
              </div>

              {note && (
                <Panel title="Comparability notes">
                  <p className="text-[12.5px] text-muted">
                    <span className="text-foreground">
                      {note.business_model ?? "—"}
                    </span>
                    {note.debt_measure && (
                      <span className="ml-2 font-mono text-faint">
                        debt: {note.debt_measure}
                      </span>
                    )}
                    {note.notes && <span className="ml-2">{note.notes}</span>}
                  </p>
                </Panel>
              )}
            </div>
          )}

          {/* --- Financials tab ------------------------------------------- */}
          {tab === "Financials" &&
            (hasFinancials ? (
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
                        <tr
                          key={label}
                          className="border-b border-edge/50 last:border-b-0"
                        >
                          <td className="py-1.5 pr-3 text-muted">{label}</td>
                          <td className="py-1.5 text-right font-mono tabular-nums">
                            {formatUSD(value)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Panel>
              </div>
            ) : (
              <EmptyState
                title={`Historical fundamentals are not yet available for ${ticker}.`}
                hint="The quantitative layer is populated from audited SEC-sourced metrics."
              />
            ))}

          {/* --- Filings tab ---------------------------------------------- */}
          {tab === "Filings" && (
            <div className="space-y-5">
              <Panel title={`Extraction-ready filings · ${detail.extraction_ready_count}`}>
                {detail.extraction_ready.length === 0 ? (
                  <p className="py-3 text-[13px] text-muted">
                    No earnings exhibits ingested yet for {ticker}.
                  </p>
                ) : (
                  <DataTable minWidth={560}>
                    <THead>
                      <TH>Accession</TH>
                      <TH>Filed</TH>
                      <TH>Exhibit</TH>
                      <TH right>Chunks</TH>
                      <TH>Extraction</TH>
                    </THead>
                    <tbody>
                      {detail.extraction_ready.map((row) => (
                        <TR key={row.accession_number}>
                          <TD mono>
                            <Link
                              href={`/filings/${encodeURIComponent(row.accession_number)}`}
                              className="text-info hover:text-accent hover:underline"
                            >
                              {row.accession_number}
                            </Link>
                          </TD>
                          <TD mono tone="muted">
                            {row.filing_date ?? "—"}
                          </TD>
                          <TD mono className="text-[12px]">
                            {row.filename ?? "—"}
                          </TD>
                          <TD right mono>
                            {row.chunk_count}
                          </TD>
                          <TD>
                            <StatusPill status={row.claim_extraction_status} />
                          </TD>
                        </TR>
                      ))}
                    </tbody>
                  </DataTable>
                )}
              </Panel>

              <Panel title="Recent filings">
                <FilingsTable filings={detail.recent_filings} showReportDate />
              </Panel>
            </div>
          )}

          {/* --- Evidence tab --------------------------------------------- */}
          {tab === "Evidence" && (
            <Panel
              title={`Trusted evidence · ${evidence.length}`}
              actions={
                <Link
                  href={`/evidence?ticker=${encodeURIComponent(ticker)}`}
                  className="text-[12px] text-info hover:text-accent hover:underline"
                >
                  Evidence Explorer →
                </Link>
              }
            >
              {evidence.length === 0 ? (
                <p className="py-3 text-[13px] text-muted">
                  No trusted, promoted claims for {ticker} yet.
                </p>
              ) : (
                <ul className="space-y-2.5">
                  {evidence.slice(0, 12).map((item) => (
                    <li
                      key={item.qualitative_claim_id}
                      className="rounded border border-edge bg-surface-raised px-3 py-2"
                    >
                      <div className="mb-1 flex flex-wrap items-center gap-2 text-[11px]">
                        <span className="text-muted">{item.theme}</span>
                        <span className="font-mono text-faint">
                          conf {item.confidence ?? "—"}
                        </span>
                      </div>
                      <p className="text-[13px]">{item.claim}</p>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          )}

          {/* --- Reports tab ---------------------------------------------- */}
          {tab === "Reports" && (
            <div className="space-y-5">
              <Panel title="Latest research report">
                {report ? (
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[13px]">
                    <ReportTypeBadge
                      generatorType={report.generator_type}
                      reportStatus={report.report_status}
                    />
                    <span className="font-mono text-accent">
                      v{report.version_number}
                    </span>
                    <span className="text-muted">{report.title}</span>
                    <Link
                      href={`/reports/latest/${encodeURIComponent(ticker)}`}
                      className="text-info hover:text-accent hover:underline"
                    >
                      Open report →
                    </Link>
                  </div>
                ) : (
                  <p className="py-2 text-[13px] text-muted">
                    No research report for {ticker} yet.{" "}
                    <Link
                      href={`/reports/latest/${encodeURIComponent(ticker)}`}
                      className="text-info hover:underline"
                    >
                      Generate one →
                    </Link>
                  </p>
                )}
              </Panel>

              <Panel title="Latest brief">
                {detail.latest_brief ? (
                  <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[13px]">
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
                    <Link
                      href={`/briefs/latest/${encodeURIComponent(ticker)}`}
                      className="text-info hover:text-accent hover:underline"
                    >
                      View brief →
                    </Link>
                  </div>
                ) : (
                  <p className="py-2 text-[13px] text-muted">
                    No brief stored yet. Extract, review, and promote claims from an{" "}
                    <Link href="/extraction-ready" className="text-info hover:underline">
                      extraction-ready filing
                    </Link>
                    .
                  </p>
                )}
              </Panel>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function FilingField({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b border-hairline/60 pb-2 last:border-b-0 last:pb-0">
      <dt className="text-muted">{label}</dt>
      <dd className="font-mono tabular-nums text-foreground">{value}</dd>
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
        className={`mt-0.5 ${mono ? "font-mono tabular-nums" : ""} text-[15px] ${
          accent ? "text-accent" : "text-foreground"
        }`}
      >
        {value}
      </div>
    </div>
  );
}
