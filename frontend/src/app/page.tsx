"use client";

import { useEffect, useState } from "react";
import {
  api,
  ApiError,
  type Brief,
  type ExtractionReadyResponse,
  type FilingsResponse,
  type ReviewQueueResponse,
} from "@/lib/api";
import FilingsTable from "@/components/FilingsTable";
import { ErrorBox, Loading, Panel, StatCard } from "@/components/Panel";

export default function OverviewPage() {
  const [filings, setFilings] = useState<FilingsResponse | null>(null);
  const [queue, setQueue] = useState<ReviewQueueResponse | null>(null);
  const [extractionReady, setExtractionReady] =
    useState<ExtractionReadyResponse | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [briefMissing, setBriefMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [filingsData, queueData, extractionReadyData] =
          await Promise.all([
            api.getFilings({ limit: 25 }),
            api.getReviewQueue(),
            api.getExtractionReady(),
          ]);
        if (cancelled) return;
        setFilings(filingsData);
        setQueue(queueData);
        setExtractionReady(extractionReadyData);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load data.");
        }
      }

      // The brief may legitimately not exist yet — a 404 is not an error.
      try {
        const briefData = await api.getLatestBrief("AVGO");
        if (!cancelled) setBrief(briefData);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setBriefMissing(true);
        } else {
          setError(err instanceof Error ? err.message : "Failed to load brief.");
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

      {!loading && filings && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="Recent filings"
              value={filings.count}
              hint="latest feed (limit 25)"
            />
            <StatCard
              label="Extraction-ready filings"
              value={extractionReady?.count ?? 0}
              hint="exhibits ingested and chunked"
            />
            <StatCard
              label="Pending grounded claims"
              value={queue?.count ?? 0}
              hint="awaiting analyst review"
            />
            <StatCard
              label="Latest AVGO brief"
              value={brief ? `v${brief.version_number}` : "—"}
              hint={briefMissing ? "no brief stored yet" : "stored version"}
            />
          </div>

          <Panel title="Latest filings">
            <FilingsTable filings={filings.filings} />
          </Panel>
        </>
      )}
    </div>
  );
}
