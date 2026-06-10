"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  api,
  type FilingsResponse,
  type OverviewResponse,
} from "@/lib/api";
import FilingsTable from "@/components/FilingsTable";
import { ErrorBox, Loading, Panel, StatCard } from "@/components/Panel";

export default function OverviewPage() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [filings, setFilings] = useState<FilingsResponse | null>(null);
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
      if (!cancelled) setLoading(false);
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

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
