"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError, type CompanyDetail } from "@/lib/api";
import FilingsTable from "@/components/FilingsTable";
import { ErrorBox, Loading, Panel, StatCard } from "@/components/Panel";
import StatusBadge from "@/components/StatusBadge";

export default function CompanyPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker: rawTicker } = use(params);
  const ticker = decodeURIComponent(rawTicker).toUpperCase();

  const [detail, setDetail] = useState<CompanyDetail | null>(null);
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
      if (!cancelled) setLoading(false);
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [ticker]);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-lg font-semibold">
          {detail ? detail.company.company_name : ticker}
          <span className="ml-2 font-mono text-[14px] text-accent">
            {ticker}
          </span>
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
              The watchlist currently covers the companies listed in the
              sidebar.
            </p>
          </div>
        </Panel>
      )}

      {detail && (
        <>
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
              value={
                detail.latest_brief
                  ? `v${detail.latest_brief.version_number}`
                  : "—"
              }
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
                  {new Date(
                    detail.latest_brief.generated_at,
                  ).toLocaleString()}
                </span>
              </div>
            ) : (
              <p className="px-1 py-3 text-[13px] text-muted">
                No brief stored yet. Extract, review, and promote claims from
                an{" "}
                <Link
                  href="/extraction-ready"
                  className="text-info hover:underline"
                >
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
                    <th className="py-1.5 pr-3 font-medium text-right">
                      Chunks
                    </th>
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
