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

interface TickerGroup {
  ticker: string;
  latest: ReportMeta;
  prior: ReportMeta[];
}

function PdfLink({ report }: { report: ReportMeta }) {
  if (!(report.pdf_available || report.pdf_storage_path)) {
    return <span className="font-mono text-[11px] text-faint">—</span>;
  }
  return (
    <a
      href={api.reportPdfUrl(report.id)}
      target="_blank"
      rel="noopener noreferrer"
      className="font-mono text-[11px] text-info hover:text-accent hover:underline"
    >
      PDF ↗
    </a>
  );
}

function TickerGroupPanel({ group }: { group: TickerGroup }) {
  const { ticker, latest, prior } = group;
  return (
    <Panel
      title={`${ticker} · ${prior.length + 1} version${prior.length ? "s" : ""}`}
      actions={
        <Link
          href={`/reports/latest/${encodeURIComponent(ticker)}`}
          className="text-[12px] text-info hover:text-accent hover:underline"
        >
          open report →
        </Link>
      }
    >
      {/* Latest visible report — the prominent block. */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-hairline-strong bg-surface-raised px-3 py-2.5">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/reports/latest/${encodeURIComponent(ticker)}`}
              className="font-mono text-[13px] font-semibold text-accent hover:underline"
            >
              {ticker}
            </Link>
            <span className="font-mono text-[12px] text-muted">
              v{latest.version_number}
            </span>
            <ReportTypeBadge generatorType={latest.generator_type} />
            <StatusPill status={latest.report_status} />
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 font-mono text-[11px] text-faint">
            <span>{latest.report_type.replace(/_/g, " ")}</span>
            <span>·</span>
            <span>{new Date(latest.generated_at).toLocaleDateString()}</span>
            <span>·</span>
            <span>{latest.source_claim_count} claims</span>
            <span>·</span>
            <span>{latest.source_metric_count} metrics</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <PdfLink report={latest} />
          <Link
            href={`/reports/latest/${encodeURIComponent(ticker)}`}
            className="text-[12px] text-info hover:text-accent hover:underline"
          >
            view →
          </Link>
        </div>
      </div>

      {/* Prior versions — visually subordinate and collapsed by default. */}
      {prior.length > 0 && (
        <details className="mt-2 rounded-md border border-hairline">
          <summary className="cursor-pointer px-3 py-1.5 text-[11px] uppercase tracking-wider text-muted">
            {prior.length} prior version{prior.length > 1 ? "s" : ""}
          </summary>
          <div className="border-t border-hairline px-3 py-2">
            <DataTable minWidth={620}>
              <THead>
                <TH right>Ver</TH>
                <TH>Source</TH>
                <TH>Status</TH>
                <TH right>Claims</TH>
                <TH right>Metrics</TH>
                <TH>PDF</TH>
                <TH>Generated</TH>
              </THead>
              <tbody>
                {prior.map((r) => (
                  <TR key={r.id}>
                    <TD right mono>
                      v{r.version_number}
                    </TD>
                    <TD>
                      <ReportTypeBadge generatorType={r.generator_type} />
                    </TD>
                    <TD>
                      <StatusPill status={r.report_status} />
                    </TD>
                    <TD right mono>
                      {r.source_claim_count}
                    </TD>
                    <TD right mono>
                      {r.source_metric_count}
                    </TD>
                    <TD>
                      <PdfLink report={r} />
                    </TD>
                    <TD mono tone="faint">
                      {new Date(r.generated_at).toLocaleDateString()}
                    </TD>
                  </TR>
                ))}
              </tbody>
            </DataTable>
          </div>
        </details>
      )}
    </Panel>
  );
}

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

  // Group reports by ticker. The API returns visible reports newest-first;
  // within each ticker the highest version is the prominent "latest" and the
  // remainder become subordinate prior versions.
  const groups = useMemo<TickerGroup[]>(() => {
    const byTicker = new Map<string, ReportMeta[]>();
    for (const r of reports ?? []) {
      const list = byTicker.get(r.ticker) ?? [];
      list.push(r);
      byTicker.set(r.ticker, list);
    }
    return [...byTicker.entries()]
      .map(([t, list]) => {
        const sorted = [...list].sort(
          (a, b) => b.version_number - a.version_number,
        );
        const [latest, ...prior] = sorted;
        return { ticker: t, latest, prior };
      })
      .sort((a, b) => a.ticker.localeCompare(b.ticker));
  }, [reports]);

  return (
    <div className="space-y-5">
      <ResearchHeader
        eyebrow="Research"
        title="Research Reports"
        description="Versioned earnings-update reports grouped by company — deterministic notes plus reviewed Claude-assisted narratives. Drafts, rejected, and superseded versions are never listed here."
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
        (groups.length === 0 ? (
          <EmptyState
            title="No reports generated yet."
            hint="Generate the first deterministic report from a company's report page (admin token required)."
          />
        ) : (
          <div className="space-y-4">
            {groups.map((group) => (
              <TickerGroupPanel key={group.ticker} group={group} />
            ))}
          </div>
        ))}
    </div>
  );
}
