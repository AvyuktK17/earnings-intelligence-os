"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  api,
  type FilingsResponse,
  type OverviewResponse,
  type PeerRow,
  type PeersResponse,
  type ReportMeta,
  type ExtractionReadyResponse,
} from "@/lib/api";
import FilingsTable from "@/components/FilingsTable";
import { ErrorBox, Panel } from "@/components/Panel";
import ResearchHeader from "@/components/ResearchHeader";
import MetricCard from "@/components/MetricCard";
import { DataTable, TH, THead, TR, TD } from "@/components/DataTable";
import { EmptyState, LoadingSkeleton } from "@/components/States";
import StatusPill from "@/components/StatusPill";
import { ValuationBadge } from "@/components/ValuationNote";
import { formatMultiple, formatPercent, formatUSD } from "@/lib/format";

/** Green for positive financial states, red for negative — neutral otherwise. */
function signTone(value: number | null): "positive" | "negative" | undefined {
  if (value == null) return undefined;
  if (value > 0) return "positive";
  if (value < 0) return "negative";
  return undefined;
}

function leader(peers: PeerRow[], key: keyof PeerRow): PeerRow | null {
  const ranked = peers
    .filter((p) => p[key] != null)
    .sort((a, b) => (b[key] as number) - (a[key] as number));
  return ranked[0] ?? null;
}

export default function OverviewPage() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [filings, setFilings] = useState<FilingsResponse | null>(null);
  const [peers, setPeers] = useState<PeersResponse | null>(null);
  const [reports, setReports] = useState<ReportMeta[] | null>(null);
  const [ready, setReady] = useState<ExtractionReadyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [overviewData, filingsData] = await Promise.all([
          api.getOverview(),
          api.getFilings({ limit: 8 }),
        ]);
        if (cancelled) return;
        setOverview(overviewData);
        setFilings(filingsData);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load data.");
        }
      }
      // Additive panels never block the core overview.
      const [peersRes, reportsRes, readyRes] = await Promise.allSettled([
        api.getPeers(),
        api.getReports(),
        api.getExtractionReady(),
      ]);
      if (!cancelled) {
        if (peersRes.status === "fulfilled") setPeers(peersRes.value);
        if (reportsRes.status === "fulfilled")
          setReports(reportsRes.value.reports);
        if (readyRes.status === "fulfilled") setReady(readyRes.value);
        setLoading(false);
      }
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

  // Report coverage grouped by ticker (latest version per company).
  const reportCoverage = useMemo(() => {
    if (!reports) return [];
    const byTicker = new Map<string, { count: number; latest: number }>();
    for (const r of reports) {
      const cur = byTicker.get(r.ticker) ?? { count: 0, latest: 0 };
      cur.count += 1;
      cur.latest = Math.max(cur.latest, r.version_number);
      byTicker.set(r.ticker, cur);
    }
    return [...byTicker.entries()]
      .map(([ticker, v]) => ({ ticker, ...v }))
      .sort((a, b) => a.ticker.localeCompare(b.ticker));
  }, [reports]);

  const pendingExtractions = useMemo(
    () =>
      (ready?.filings ?? []).filter(
        (f) => f.claim_extraction_status === "not_started",
      ),
    [ready],
  );

  const snapshotDate = peers?.valuation_snapshot_dates?.[0] ?? null;

  return (
    <div className="space-y-5">
      <ResearchHeader
        eyebrow="Markets"
        title="Research Terminal Overview"
        description="Cross-company state of the semiconductor coverage pipeline — from SEC ingestion through human-reviewed claims, briefs, and research reports."
        actions={<ValuationBadge date={snapshotDate} />}
      />

      <p className="-mt-2 text-[12px] text-faint">
        First time here?{" "}
        <Link href="/about" className="text-accent hover:underline">
          How this works — the evidence-grounded pipeline →
        </Link>
      </p>

      {error && <ErrorBox message={error} />}
      {loading && !error && <LoadingSkeleton rows={6} />}

      {!loading && overview && (
        <>
          {/* --- Peer fundamentals (lead) --------------------------------- */}
          {peers && (
            <Panel
              title="Peer fundamentals — latest reported quarter"
              actions={
                <Link
                  href="/peers"
                  className="text-[12px] text-info hover:text-accent hover:underline"
                >
                  Full comparison →
                </Link>
              }
            >
              <DataTable minWidth={680} className="tnum">
                <THead>
                  <TH>Ticker</TH>
                  <TH>Company</TH>
                  <TH right>Revenue</TH>
                  <TH right>YoY</TH>
                  <TH right>Gross</TH>
                  <TH right>Op.</TH>
                  <TH right>EV/Rev</TH>
                  <TH right>FCF yld</TH>
                </THead>
                <tbody>
                  {peers.peers.map((row) => (
                    <TR key={row.ticker}>
                      <TD mono className="font-medium">
                        <Link
                          href={`/companies/${encodeURIComponent(row.ticker)}`}
                          className="text-accent hover:underline"
                        >
                          {row.ticker}
                        </Link>
                      </TD>
                      <TD tone="muted">{row.company_name}</TD>
                      <TD right mono>
                        {formatUSD(row.revenue)}
                      </TD>
                      <TD right mono tone={signTone(row.yoy_revenue_growth)}>
                        {formatPercent(row.yoy_revenue_growth)}
                      </TD>
                      <TD right mono>
                        {formatPercent(row.gross_margin)}
                      </TD>
                      <TD right mono>
                        {formatPercent(row.operating_margin)}
                      </TD>
                      <TD right mono tone="accent">
                        {formatMultiple(row.ev_to_ttm_revenue)}
                      </TD>
                      <TD right mono tone={signTone(row.free_cash_flow_yield)}>
                        {formatPercent(row.free_cash_flow_yield)}
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </DataTable>
            </Panel>
          )}

          {/* --- Peer leaders --------------------------------------------- */}
          {peers && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <MetricCard
                label="Top revenue growth"
                value={topGrowth?.ticker ?? "—"}
                hint={
                  topGrowth
                    ? `${formatPercent(topGrowth.yoy_revenue_growth)} YoY`
                    : undefined
                }
                tone="positive"
              />
              <MetricCard
                label="Highest gross margin"
                value={topGross?.ticker ?? "—"}
                hint={
                  topGross ? `${formatPercent(topGross.gross_margin)} gross` : undefined
                }
                tone="accent"
              />
              <MetricCard
                label="Strongest FCF margin"
                value={topFcf?.ticker ?? "—"}
                hint={
                  topFcf
                    ? `${formatPercent(topFcf.free_cash_flow_margin)} FCF margin`
                    : undefined
                }
                tone="info"
              />
            </div>
          )}

          {/* --- Coverage + workflow health ------------------------------- */}
          <div className="grid gap-4 lg:grid-cols-3">
            <Panel
              title="Company coverage"
              actions={
                <Link
                  href="/peers"
                  className="text-[12px] text-info hover:text-accent hover:underline"
                >
                  Peer comparison →
                </Link>
              }
            >
              <div className="lg:col-span-2">
                <DataTable minWidth={520}>
                  <THead>
                    <TH>Ticker</TH>
                    <TH>Company</TH>
                    <TH right>Ready</TH>
                    <TH right>Trusted</TH>
                    <TH>Brief</TH>
                    <TH>Latest filing</TH>
                  </THead>
                  <tbody>
                    {overview.companies.map((row) => (
                      <TR key={row.ticker}>
                        <TD mono className="font-medium">
                          <Link
                            href={`/companies/${encodeURIComponent(row.ticker)}`}
                            className="text-accent hover:underline"
                          >
                            {row.ticker}
                          </Link>
                        </TD>
                        <TD tone="muted">{row.company_name}</TD>
                        <TD right mono>
                          {row.extraction_ready_count}
                        </TD>
                        <TD right mono>
                          {row.trusted_claim_count}
                        </TD>
                        <TD mono>
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
                        </TD>
                        <TD mono tone="muted">
                          {row.latest_filing_date ?? "—"}
                        </TD>
                      </TR>
                    ))}
                  </tbody>
                </DataTable>
              </div>
            </Panel>

            <div className="space-y-4">
              <Panel title="Workflow health">
                <dl className="space-y-2 text-[13px]">
                  <HealthRow
                    label="Exhibits awaiting extraction"
                    value={pendingExtractions.length}
                    href="/extraction-ready"
                  />
                  <HealthRow
                    label="Grounded drafts in review"
                    value={overview.pending_grounded_claim_count}
                    href="/review-queue"
                    tone={
                      overview.pending_grounded_claim_count > 0
                        ? "accent"
                        : undefined
                    }
                  />
                  <HealthRow
                    label="Trusted promoted claims"
                    value={overview.trusted_claim_count}
                    href="/evidence"
                  />
                  <HealthRow
                    label="Stored briefs"
                    value={overview.stored_brief_count}
                  />
                </dl>
              </Panel>

              <Panel
                title="Report coverage"
                actions={
                  <Link
                    href="/reports"
                    className="text-[12px] text-info hover:text-accent hover:underline"
                  >
                    All reports →
                  </Link>
                }
              >
                {reportCoverage.length === 0 ? (
                  <p className="py-2 text-[12px] text-muted">
                    No research reports generated yet.
                  </p>
                ) : (
                  <DataTable>
                    <THead>
                      <TH>Ticker</TH>
                      <TH right>Versions</TH>
                      <TH right>Latest</TH>
                    </THead>
                    <tbody>
                      {reportCoverage.map((r) => (
                        <TR key={r.ticker}>
                          <TD mono className="font-medium">
                            <Link
                              href={`/reports/latest/${encodeURIComponent(r.ticker)}`}
                              className="text-accent hover:underline"
                            >
                              {r.ticker}
                            </Link>
                          </TD>
                          <TD right mono>
                            {r.count}
                          </TD>
                          <TD right mono tone="info">
                            v{r.latest}
                          </TD>
                        </TR>
                      ))}
                    </tbody>
                  </DataTable>
                )}
              </Panel>
            </div>
          </div>

          {/* --- Pipeline status (subordinate to research content) -------- */}
          <Panel title="Pipeline status">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
              <MetricCard
                label="Companies"
                value={overview.companies_count}
                hint="monitored watchlist"
              />
              <MetricCard
                label="Filings"
                value={overview.total_filings_count}
                hint="all forms, all time"
              />
              <MetricCard
                label="Extraction ready"
                value={overview.extraction_ready_count}
                hint="exhibits ingested"
                tone="info"
              />
              <MetricCard
                label="Pending review"
                value={overview.pending_grounded_claim_count}
                hint="grounded drafts"
                tone={
                  overview.pending_grounded_claim_count > 0 ? "accent" : "default"
                }
              />
              <MetricCard
                label="Trusted claims"
                value={overview.trusted_claim_count}
                hint="reviewed + promoted"
                tone="positive"
              />
              <MetricCard
                label="Stored briefs"
                value={overview.stored_brief_count}
                hint="versioned"
              />
            </div>
          </Panel>

          {/* --- Operational panels --------------------------------------- */}
          <div className="grid gap-4 lg:grid-cols-2">
            <Panel
              title="Recent filings"
              actions={
                <Link
                  href="/filings"
                  className="text-[12px] text-info hover:text-accent hover:underline"
                >
                  All filings →
                </Link>
              }
            >
              {filings ? (
                <FilingsTable filings={filings.filings} />
              ) : (
                <p className="py-3 text-[12px] text-muted">
                  Filing feed unavailable.
                </p>
              )}
            </Panel>

            <Panel
              title="Extraction queue"
              actions={
                <Link
                  href="/extraction-ready"
                  className="text-[12px] text-info hover:text-accent hover:underline"
                >
                  Open queue →
                </Link>
              }
            >
              {ready && ready.filings.length > 0 ? (
                <DataTable minWidth={420}>
                  <THead>
                    <TH>Ticker</TH>
                    <TH>Accession</TH>
                    <TH right>Chunks</TH>
                    <TH>Stage</TH>
                  </THead>
                  <tbody>
                    {ready.filings.slice(0, 8).map((f) => (
                      <TR key={f.filing_id}>
                        <TD mono className="font-medium text-accent">
                          {f.ticker}
                        </TD>
                        <TD mono>
                          <Link
                            href={`/filings/${encodeURIComponent(f.accession_number)}`}
                            className="text-info hover:underline"
                          >
                            {f.accession_number}
                          </Link>
                        </TD>
                        <TD right mono>
                          {f.chunk_count}
                        </TD>
                        <TD>
                          <StatusPill status={f.claim_extraction_status} />
                        </TD>
                      </TR>
                    ))}
                  </tbody>
                </DataTable>
              ) : (
                <EmptyState
                  title="No extraction-ready exhibits."
                  hint="The exhibit worker marks new 8-K earnings releases here automatically."
                />
              )}
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}

function HealthRow({
  label,
  value,
  href,
  tone,
}: {
  label: string;
  value: number;
  href?: string;
  tone?: "accent";
}) {
  const valueEl = (
    <span
      className={`font-mono tabular-nums ${tone === "accent" ? "text-accent" : "text-foreground"}`}
    >
      {value}
    </span>
  );
  return (
    <div className="flex items-center justify-between gap-2 border-b border-edge/40 pb-2 last:border-b-0 last:pb-0">
      <dt className="text-muted">
        {href ? (
          <Link href={href} className="hover:text-foreground hover:underline">
            {label}
          </Link>
        ) : (
          label
        )}
      </dt>
      <dd>{valueEl}</dd>
    </div>
  );
}
