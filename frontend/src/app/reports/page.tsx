"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, type Company, type ReportMeta } from "@/lib/api";
import { ErrorBox, Loading, Panel } from "@/components/Panel";

function StatusBadge({ status }: { status: string }) {
  return (
    <span className="inline-block rounded border border-positive/40 px-1.5 py-px font-mono text-[11px] leading-4 text-positive">
      {status.replace(/_/g, " ")}
    </span>
  );
}

function GeneratorBadge({ generator }: { generator: string }) {
  const isClaude = generator === "claude_assisted";
  const label = isClaude ? "Claude-assisted" : "Deterministic";
  const cls = isClaude
    ? "border-warning/50 text-warning"
    : "border-info/50 text-info";
  return (
    <span
      className={`inline-block rounded border px-1.5 py-px font-mono text-[11px] leading-4 ${cls}`}
    >
      {label}
    </span>
  );
}

export default function ReportsIndexPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [reports, setReports] = useState<ReportMeta[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [ticker, setTicker] = useState("");
  const [reportType, setReportType] = useState("");

  useEffect(() => {
    api.getCompanies().then((r) => setCompanies(r.companies)).catch(() => {});
  }, []);

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
      <header>
        <h1 className="text-lg font-semibold">Research Reports</h1>
        <p className="text-[12px] uppercase tracking-wider text-muted">
          Deterministic, human-reviewed earnings-update reports
        </p>
      </header>

      <Panel title="Filters">
        <div className="flex flex-wrap items-center gap-2 text-[12px]">
          <select
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            className="rounded border border-edge bg-surface-raised px-2 py-1 text-foreground"
          >
            <option value="">All tickers</option>
            {companies.map((c) => (
              <option key={c.ticker} value={c.ticker}>
                {c.ticker}
              </option>
            ))}
          </select>
          <select
            value={reportType}
            onChange={(e) => setReportType(e.target.value)}
            className="rounded border border-edge bg-surface-raised px-2 py-1 text-foreground"
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
      {loading && !error && <Loading label="Loading reports…" />}

      {reports && !loading && (
        reports.length === 0 ? (
          <Panel>
            <div className="py-8 text-center">
              <p className="text-[14px] text-muted">No reports generated yet.</p>
              <p className="mt-1 text-[12px] text-faint">
                Generate the first deterministic report from a company&apos;s
                latest-report page (admin token required).
              </p>
            </div>
          </Panel>
        ) : (
          <Panel title={`Stored reports · ${reports.length}`}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-left text-[13px]">
                <thead>
                  <tr className="border-b border-edge text-[11px] uppercase tracking-wider text-muted">
                    <th className="py-1.5 pr-3 font-medium">Ticker</th>
                    <th className="py-1.5 pr-3 font-medium">Type</th>
                    <th className="py-1.5 pr-3 font-medium">Source</th>
                    <th className="py-1.5 pr-3 font-medium">Status</th>
                    <th className="py-1.5 pr-3 font-medium text-right">Ver</th>
                    <th className="py-1.5 pr-3 font-medium text-right">Claims</th>
                    <th className="py-1.5 pr-3 font-medium text-right">Metrics</th>
                    <th className="py-1.5 pr-3 font-medium">PDF</th>
                    <th className="py-1.5 pr-3 font-medium">Generated</th>
                    <th className="py-1.5 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {reports.map((r) => (
                    <tr
                      key={r.id}
                      className="border-b border-edge/50 last:border-b-0 hover:bg-surface-raised"
                    >
                      <td className="py-1.5 pr-3 font-mono font-medium">
                        <Link
                          href={`/reports/latest/${encodeURIComponent(r.ticker)}`}
                          className="text-accent hover:underline"
                        >
                          {r.ticker}
                        </Link>
                      </td>
                      <td className="py-1.5 pr-3 text-muted">
                        {r.report_type.replace(/_/g, " ")}
                      </td>
                      <td className="py-1.5 pr-3">
                        <GeneratorBadge generator={r.generator_type} />
                      </td>
                      <td className="py-1.5 pr-3">
                        <StatusBadge status={r.report_status} />
                      </td>
                      <td className="py-1.5 pr-3 text-right font-mono">v{r.version_number}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">{r.source_claim_count}</td>
                      <td className="py-1.5 pr-3 text-right font-mono">{r.source_metric_count}</td>
                      <td className="py-1.5 pr-3">
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
                      </td>
                      <td className="py-1.5 pr-3 font-mono text-faint">
                        {new Date(r.generated_at).toLocaleDateString()}
                      </td>
                      <td className="py-1.5 text-right">
                        <Link
                          href={`/reports/latest/${encodeURIComponent(r.ticker)}`}
                          className="text-[12px] text-info hover:text-accent hover:underline"
                        >
                          view →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        )
      )}
    </div>
  );
}
