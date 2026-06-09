"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type ExtractionReadyResponse } from "@/lib/api";
import { ErrorBox, Loading, Panel } from "@/components/Panel";
import StatusBadge from "@/components/StatusBadge";

export default function ExtractionReadyPage() {
  const [data, setData] = useState<ExtractionReadyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const result = await api.getExtractionReady();
        if (!cancelled) setData(result);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load extraction-ready filings.",
          );
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
        <h1 className="text-lg font-semibold">Extraction Ready</h1>
        <p className="text-[12px] text-muted">
          These earnings-release exhibits have been ingested and chunked. They
          are ready for manual AI claim extraction.
        </p>
      </header>

      <Panel title={`Extraction queue${data ? ` · ${data.count} ready` : ""}`}>
        {error && <ErrorBox message={error} />}
        {loading && !error && <Loading label="Loading extraction queue…" />}
        {!loading && !error && data && data.filings.length === 0 && (
          <p className="px-1 py-6 text-[13px] text-muted">
            No extraction-ready filings yet. The exhibit worker marks 8-K
            filings here once their earnings release is ingested and chunked.
          </p>
        )}
        {!loading && !error && data && data.filings.length > 0 && (
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-edge text-[11px] uppercase tracking-wider text-muted">
                <th className="py-1.5 pr-3 font-medium">Ticker</th>
                <th className="py-1.5 pr-3 font-medium">Accession</th>
                <th className="py-1.5 pr-3 font-medium">Filed</th>
                <th className="py-1.5 pr-3 font-medium">Exhibit</th>
                <th className="py-1.5 pr-3 font-medium">Document key</th>
                <th className="py-1.5 pr-3 font-medium text-right">Chunks</th>
                <th className="py-1.5 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.filings.map((filing) => (
                <tr
                  key={filing.filing_id}
                  className="border-b border-edge/50 last:border-b-0"
                >
                  <td className="py-1.5 pr-3 font-mono font-medium">
                    {filing.ticker}
                  </td>
                  <td className="py-1.5 pr-3 font-mono">
                    <Link
                      href={`/filings/${encodeURIComponent(filing.accession_number)}`}
                      className="text-info hover:text-accent hover:underline"
                    >
                      {filing.accession_number}
                    </Link>
                  </td>
                  <td className="py-1.5 pr-3 font-mono text-muted">
                    {filing.filing_date ?? "—"}
                  </td>
                  <td className="py-1.5 pr-3 font-mono text-[12px]">
                    {filing.filename ?? "—"}
                  </td>
                  <td className="py-1.5 pr-3 font-mono text-[12px] text-muted">
                    {filing.document_key ?? "—"}
                  </td>
                  <td className="py-1.5 pr-3 text-right font-mono">
                    {filing.chunk_count}
                  </td>
                  <td className="py-1.5">
                    <StatusBadge status={filing.exhibit_processing_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
