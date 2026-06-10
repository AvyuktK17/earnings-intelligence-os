"use client";

import { use, useEffect, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import {
  api,
  ApiError,
  getAdminToken,
  subscribeAdminToken,
  type ReportDetail,
  type ReportMeta,
} from "@/lib/api";
import {
  ErrorBox,
  Loading,
  Panel,
  StatCard,
  SuccessNote,
} from "@/components/Panel";

const FALLBACK_TICKERS = ["AMD", "AVGO", "INTC", "NVDA", "QCOM"];

function useAdminToken() {
  return useSyncExternalStore(
    subscribeAdminToken,
    () => getAdminToken(),
    () => null,
  );
}

function CompanyTabs({ tickers, active }: { tickers: string[] | null; active: string }) {
  if (tickers === null)
    return <div className="font-mono text-[11px] text-faint">loading companies…</div>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {tickers.map((t) => (
        <Link
          key={t}
          href={`/reports/latest/${encodeURIComponent(t)}`}
          className={`rounded border px-2.5 py-1 font-mono text-[12px] transition-colors ${
            t === active
              ? "border-accent/60 bg-accent/10 font-semibold text-accent"
              : "border-edge text-muted hover:border-accent/40 hover:text-foreground"
          }`}
        >
          {t}
        </Link>
      ))}
    </div>
  );
}

export default function LatestReportPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker: rawTicker } = use(params);
  const ticker = decodeURIComponent(rawTicker).toUpperCase();
  const adminToken = useAdminToken();

  const [report, setReport] = useState<ReportDetail | null>(null);
  const [versions, setVersions] = useState<ReportMeta[]>([]);
  const [tickers, setTickers] = useState<string[] | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    api
      .getCompanies()
      .then((r) => setTickers(r.companies.map((c) => c.ticker)))
      .catch(() => setTickers(FALLBACK_TICKERS));
  }, []);

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
      <header>
        <h1 className="text-lg font-semibold">Research Report · {ticker}</h1>
        <p className="text-[12px] text-muted">
          Deterministic earnings update built only from trusted claims, audited
          metrics, and a dated valuation snapshot
        </p>
      </header>

      <CompanyTabs tickers={tickers} active={ticker} />

      {flash && <SuccessNote message={flash} />}
      {error && <ErrorBox message={error} />}
      {loading && <Loading label="Loading report…" />}

      {notFound && (
        <Panel>
          <div className="py-8 text-center">
            <p className="text-[14px] text-muted">
              No report exists for {ticker} yet.
            </p>
            <p className="mt-1 text-[12px] text-faint">
              {adminToken
                ? "Generate the first version below."
                : "Save an admin token in the sidebar to generate the first version."}
            </p>
            {adminToken && (
              <button
                disabled={generating}
                onClick={generateNewVersion}
                className="mt-3 rounded border border-accent/50 px-3 py-1.5 text-[12px] font-medium text-accent transition-colors hover:bg-accent/10 disabled:opacity-50"
              >
                {generating ? "Generating…" : "Generate first report"}
              </button>
            )}
          </div>
        </Panel>
      )}

      {report && (
        <>
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span
              className={`rounded border px-1.5 py-px font-mono ${
                report.generator_type === "claude_assisted"
                  ? "border-warning/50 text-warning"
                  : "border-info/50 text-info"
              }`}
            >
              {report.generator_type === "claude_assisted"
                ? "Claude-assisted (reviewed)"
                : "Deterministic"}
            </span>
            <span className="rounded border border-edge px-1.5 py-px font-mono text-muted">
              {report.report_status.replace(/_/g, " ")}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="Version"
              value={`v${report.version_number}`}
              hint={`generated ${new Date(report.generated_at).toLocaleString()}`}
            />
            <StatCard
              label="Trusted claims"
              value={report.source_claim_count}
              hint="evidence-linked"
            />
            <StatCard label="Metrics" value={report.source_metric_count} hint="deterministic" />
            <StatCard
              label="Valuation snapshot"
              value={report.valuation_snapshot_date ?? "—"}
              hint="dated, not live"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {versions.length > 1 && (
              <select
                value={report.id}
                onChange={(e) => selectVersion(Number(e.target.value))}
                className="rounded border border-edge bg-surface-raised px-2 py-1 text-[12px] text-foreground"
              >
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version_number} · {new Date(v.generated_at).toLocaleDateString()}
                  </option>
                ))}
              </select>
            )}
            <a
              href={api.reportPdfUrl(report.id)}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded border border-info/50 px-2.5 py-1 text-[12px] font-medium text-info transition-colors hover:bg-info/10"
            >
              Download PDF ↗
            </a>
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
              <table className="w-full text-left text-[12.5px]">
                <thead>
                  <tr className="border-b border-edge text-[11px] uppercase tracking-wider text-muted">
                    <th className="py-1.5 pr-3 font-medium">Claim</th>
                    <th className="py-1.5 pr-3 font-medium">Section</th>
                    <th className="py-1.5 pr-3 font-medium">Accession</th>
                    <th className="py-1.5 pr-3 font-medium">Document</th>
                    <th className="py-1.5 font-medium text-right">Chunk</th>
                  </tr>
                </thead>
                <tbody>
                  {report.evidence_links.map((link) => (
                    <tr
                      key={link.id}
                      className="border-b border-edge/50 last:border-b-0"
                    >
                      <td className="py-1.5 pr-3 font-mono">
                        #{link.qualitative_claim_id}
                      </td>
                      <td className="py-1.5 pr-3 text-muted">
                        {(link.section_name ?? "").replace(/_/g, " ")}
                      </td>
                      <td className="py-1.5 pr-3 font-mono text-faint">
                        {link.accession_number ?? "—"}
                      </td>
                      <td className="py-1.5 pr-3 font-mono text-[11px] text-faint">
                        {link.document_key ?? "—"}
                      </td>
                      <td className="py-1.5 text-right font-mono text-faint">
                        {link.source_chunk_id ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
          )}
        </>
      )}
    </div>
  );
}
