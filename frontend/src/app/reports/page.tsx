"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, type ReportMeta } from "@/lib/api";
import { ErrorBox, Panel } from "@/components/Panel";
import ResearchHeader from "@/components/ResearchHeader";
import StatusPill from "@/components/StatusPill";
import { ReportTypeBadge } from "@/components/Badges";
import { DataTable, TH, THead, TR, TD } from "@/components/DataTable";
import { EmptyState, LoadingSkeleton } from "@/components/States";
import { useCompanies } from "@/lib/hooks";

const selectClass =
  "rounded border border-edge bg-surface-raised px-2 py-1 text-[12px] text-foreground focus:border-accent focus:outline-none";

export default function ReportsIndexPage() {
  const companies = useCompanies();
  const [reports, setReports] = useState<ReportMeta[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [ticker, setTicker] = useState("");
  const [reportType, setReportType] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const r = await api.getReports({
          ticker: ticker || undefined,
          report_type: reportType || undefined,
        });
        if (!cancelled) setReports(r.reports);
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Failed to load reports.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [ticker, reportType]);

  const reportTypes = useMemo(
    () => Array.from(new Set((reports ?? []).map((r) => r.report_type))),
    [reports],
  );

  return (
    <div className="space-y-5">
      <ResearchHeader
        eyebrow="Research"
        title="Research Reports"
        description="Versioned earnings-update reports — deterministic notes plus reviewed Claude-assisted narratives. Drafts, rejected, and superseded versions are never listed here."
      />

      <Panel title="Filters">
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Ticker"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            className={selectClass}
          >
            <option value="">All tickers</option>
            {companies.map((c) => (
              <option key={c.ticker} value={c.ticker}>
                {c.ticker}
              </option>
            ))}
          </select>
          <select
            aria-label="Report type"
            value={reportType}
            onChange={(e) => setReportType(e.target.value)}
            className={selectClass}
          >
            <option value="">All types</option>
            {reportTypes.map((t) => (
              <option key={t} value={t}>
                {t.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
      </Panel>

      {error && <ErrorBox message={error} />}
      {loading && !error && <LoadingSkeleton rows={6} withCards={false} />}

      {reports &&
        !loading &&
        (reports.length === 0 ? (
          <EmptyState
            title="No reports generated yet."
            hint="Generate the first deterministic report from a company's report page (admin token required)."
          />
        ) : (
          <Panel title={`Stored reports · ${reports.length}`}>
            <DataTable minWidth={880}>
              <THead>
                <TH>Ticker</TH>
                <TH>Type</TH>
                <TH>Source</TH>
                <TH>Status</TH>
                <TH right>Ver</TH>
                <TH right>Claims</TH>
                <TH right>Metrics</TH>
                <TH>PDF</TH>
                <TH>Generated</TH>
                <TH />
              </THead>
              <tbody>
                {reports.map((r) => (
                  <TR key={r.id}>
                    <TD mono className="font-medium">
                      <Link
                        href={`/reports/latest/${encodeURIComponent(r.ticker)}`}
                        className="text-accent hover:underline"
                      >
                        {r.ticker}
                      </Link>
                    </TD>
                    <TD tone="muted">{r.report_type.replace(/_/g, " ")}</TD>
                    <TD>
                      <ReportTypeBadge generatorType={r.generator_type} />
                    </TD>
                    <TD>
                      <StatusPill status={r.report_status} />
                    </TD>
                    <TD right mono>
                      v{r.version_number}
                    </TD>
                    <TD right mono>
                      {r.source_claim_count}
                    </TD>
                    <TD right mono>
                      {r.source_metric_count}
                    </TD>
                    <TD>
                      {r.pdf_available || r.pdf_storage_path ? (
                        <a
                          href={api.reportPdfUrl(r.id)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-mono text-[11px] text-info hover:text-accent hover:underline"
                        >
                          PDF ↗
                        </a>
                      ) : (
                        <span className="font-mono text-[11px] text-faint">—</span>
                      )}
                    </TD>
                    <TD mono tone="faint">
                      {new Date(r.generated_at).toLocaleDateString()}
                    </TD>
                    <TD right>
                      <Link
                        href={`/reports/latest/${encodeURIComponent(r.ticker)}`}
                        className="text-[12px] text-info hover:text-accent hover:underline"
                      >
                        view →
                      </Link>
                    </TD>
                  </TR>
                ))}
              </tbody>
            </DataTable>
          </Panel>
        ))}
    </div>
  );
}
