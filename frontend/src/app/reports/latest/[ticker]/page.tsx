"use client";

import { use, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  api,
  ApiError,
  type ReportDetail,
  type ReportMeta,
} from "@/lib/api";
import { ErrorBox, Panel, SuccessNote } from "@/components/Panel";
import ResearchHeader from "@/components/ResearchHeader";
import MetricCard from "@/components/MetricCard";
import TickerTabs from "@/components/TickerTabs";
import { ReportTypeBadge } from "@/components/Badges";
import { DataTable, TH, THead, TR, TD } from "@/components/DataTable";
import { EmptyState, LoadingSkeleton } from "@/components/States";
import { useAdminToken, useCompanyTickers } from "@/lib/hooks";

export default function LatestReportPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker: rawTicker } = use(params);
  const ticker = decodeURIComponent(rawTicker).toUpperCase();
  const adminToken = useAdminToken();
  const tickers = useCompanyTickers();

  const [report, setReport] = useState<ReportDetail | null>(null);
  const [versions, setVersions] = useState<ReportMeta[]>([]);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const latest = await api.getLatestReport(ticker);
        if (cancelled) return;
        setReport(latest);
        setNotFound(false);
        setError(null);
        const all = await api.getReports({ ticker });
        if (!cancelled) setVersions(all.reports);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setReport(null);
          setNotFound(true);
          setVersions([]);
        } else {
          setError(err instanceof Error ? err.message : "Failed to load report.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [ticker, reloadKey]);

  async function selectVersion(id: number) {
    if (report && id === report.id) return;
    setError(null);
    try {
      setReport(await api.getReport(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load version.");
    }
  }

  async function generateNewVersion() {
    setGenerating(true);
    setError(null);
    setFlash(null);
    try {
      const result = await api.generateReport({
        ticker,
        accession_number: report?.accession_number ?? null,
      });
      setFlash(
        `Report v${result.version_number} generated (${result.source_claim_count} ` +
          `trusted claims, ${result.evidence_link_count} evidence links).`,
      );
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="space-y-5">
      <ResearchHeader
        eyebrow="Research"
        title={`Research Report · ${ticker}`}
        description="Deterministic earnings update built only from trusted claims, audited metrics, and a dated valuation snapshot — no forecasts, ratings, or DCF."
      />

      <TickerTabs tickers={tickers} active={ticker} basePath="/reports/latest" />

      {flash && <SuccessNote message={flash} />}
      {error && <ErrorBox message={error} />}
      {loading && <LoadingSkeleton rows={8} />}

      {notFound && !loading && (
        <EmptyState
          title={`No report exists for ${ticker} yet.`}
          hint={
            adminToken
              ? "Generate the first version below."
              : "Save an admin token in the sidebar to generate the first version."
          }
          action={
            adminToken && (
              <button
                disabled={generating}
                onClick={generateNewVersion}
                className="rounded border border-accent/50 px-3 py-1.5 text-[12px] font-medium text-accent transition-colors hover:bg-accent/10 disabled:opacity-50"
              >
                {generating ? "Generating…" : "Generate first report"}
              </button>
            )
          }
        />
      )}

      {report && !loading && (
        <>
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <ReportTypeBadge
              generatorType={report.generator_type}
              reportStatus={report.report_status}
            />
            <StatusChip status={report.report_status} />
            {report.source_report_id != null && (
              <span className="rounded border border-edge px-1.5 py-px font-mono text-faint">
                source report #{report.source_report_id}
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <MetricCard
              label="Version"
              value={`v${report.version_number}`}
              hint={`generated ${new Date(report.generated_at).toLocaleDateString()}`}
            />
            <MetricCard
              label="Trusted claims"
              value={report.source_claim_count}
              hint="evidence-linked"
              tone="positive"
            />
            <MetricCard
              label="Metrics"
              value={report.source_metric_count}
              hint="deterministic"
            />
            <MetricCard
              label="Valuation snapshot"
              value={report.valuation_snapshot_date ?? "—"}
              hint="dated, not live"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {versions.length > 1 && (
              <select
                aria-label="Report version"
                value={report.id}
                onChange={(e) => selectVersion(Number(e.target.value))}
                className="rounded border border-edge bg-surface-raised px-2 py-1 text-[12px] text-foreground focus:border-accent focus:outline-none"
              >
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version_number} ·{" "}
                    {new Date(v.generated_at).toLocaleDateString()} ·{" "}
                    {v.generator_type === "claude_assisted" ? "Claude" : "Det."}
                  </option>
                ))}
              </select>
            )}
            {(report.pdf_available || report.pdf_storage_path) && (
              <a
                href={api.reportPdfUrl(report.id)}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded border border-info/50 px-2.5 py-1 text-[12px] font-medium text-info transition-colors hover:bg-info/10"
              >
                Download PDF ↗
              </a>
            )}
            {adminToken && (
              <button
                disabled={generating}
                onClick={generateNewVersion}
                className="rounded border border-accent/50 px-2.5 py-1 text-[12px] font-medium text-accent transition-colors hover:bg-accent/10 disabled:opacity-50"
              >
                {generating ? "Generating…" : "Generate new report version"}
              </button>
            )}
          </div>

          <Panel title={report.title}>
            <article className="brief-markdown max-w-3xl text-[13.5px]">
              <ReactMarkdown>{report.markdown_content}</ReactMarkdown>
            </article>
          </Panel>

          {report.evidence_links.length > 0 && (
            <Panel title={`Evidence links · ${report.evidence_links.length}`}>
              <DataTable minWidth={620}>
                <THead>
                  <TH>Claim</TH>
                  <TH>Section</TH>
                  <TH>Accession</TH>
                  <TH>Document</TH>
                  <TH right>Chunk</TH>
                </THead>
                <tbody>
                  {report.evidence_links.map((link) => (
                    <TR key={link.id}>
                      <TD mono>#{link.qualitative_claim_id}</TD>
                      <TD tone="muted">
                        {(link.section_name ?? "").replace(/_/g, " ")}
                      </TD>
                      <TD mono tone="faint">
                        {link.accession_number ?? "—"}
                      </TD>
                      <TD mono tone="faint" className="text-[11px]">
                        {link.document_key ?? "—"}
                      </TD>
                      <TD right mono tone="faint">
                        {link.source_chunk_id ?? "—"}
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </DataTable>
            </Panel>
          )}
        </>
      )}
    </div>
  );
}

function StatusChip({ status }: { status: string }) {
  return (
    <span className="rounded border border-edge px-1.5 py-px font-mono text-muted">
      {status.replace(/_/g, " ")}
    </span>
  );
}
