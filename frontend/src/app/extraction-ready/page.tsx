"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  api,
  ApiError,
  getAdminToken,
  type ExtractionReadyFiling,
  type ExtractionReadyResponse,
} from "@/lib/api";
import { ErrorBox, Loading, Panel, SuccessNote } from "@/components/Panel";
import StatusBadge from "@/components/StatusBadge";

interface Notice {
  kind: "success" | "error";
  text: string;
}

function FilingCard({
  filing,
  busy,
  notice,
  onExtract,
}: {
  filing: ExtractionReadyFiling;
  busy: boolean;
  notice: Notice | null;
  onExtract: (accessionNumber: string) => void;
}) {
  return (
    <div className="rounded-md border border-edge bg-surface p-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-mono text-[13px] font-semibold text-accent">
          {filing.ticker}
        </span>
        <Link
          href={`/filings/${encodeURIComponent(filing.accession_number)}`}
          className="font-mono text-[12px] text-info hover:text-accent hover:underline"
        >
          {filing.accession_number}
        </Link>
        <span className="font-mono text-[12px] text-muted">
          filed {filing.filing_date ?? "—"}
        </span>
        <span className="ml-auto flex items-center gap-1.5">
          <StatusBadge status={filing.exhibit_processing_status} />
          <StatusBadge status={filing.claim_extraction_status} />
        </span>
      </div>

      <div className="mt-2 font-mono text-[12px] text-muted">
        {filing.filename ?? "—"} · {filing.document_key ?? "—"} ·{" "}
        {filing.chunk_count} chunks
      </div>

      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-muted">
        <span>
          drafts pending review:{" "}
          <span className="font-mono text-foreground">
            {filing.pending_grounded_claim_count}
          </span>
        </span>
        <span>
          trusted promoted:{" "}
          <span className="font-mono text-foreground">
            {filing.trusted_promoted_claim_count}
          </span>
        </span>
        <span>
          latest brief:{" "}
          <span className="font-mono text-foreground">
            {filing.latest_brief_version != null
              ? `v${filing.latest_brief_version}`
              : "—"}
          </span>
        </span>
      </div>

      {/* The API redacts provider errors to a safe generic sentence. */}
      {filing.claim_extraction_status === "failed" &&
        filing.claim_extraction_error && (
          <div className="mt-3">
            <ErrorBox message={filing.claim_extraction_error} />
          </div>
        )}

      {notice && (
        <div className="mt-3">
          {notice.kind === "success" ? (
            <div className="space-y-1">
              <SuccessNote message={notice.text} />
              <Link
                href="/review-queue"
                className="inline-block text-[12px] text-info hover:text-accent hover:underline"
              >
                Review drafted claims →
              </Link>
            </div>
          ) : (
            <ErrorBox message={notice.text} />
          )}
        </div>
      )}

      <div className="mt-3">
        <button
          className="rounded border border-accent/50 px-2.5 py-1 text-[12px] font-medium text-accent transition-colors hover:bg-accent/10 disabled:opacity-50"
          disabled={busy}
          onClick={() => onExtract(filing.accession_number)}
        >
          {busy ? "Extracting…" : "Extract Claims"}
        </button>
      </div>
    </div>
  );
}

export default function ExtractionReadyPage() {
  const [data, setData] = useState<ExtractionReadyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const [busyAccession, setBusyAccession] = useState<string | null>(null);
  const [notices, setNotices] = useState<Record<string, Notice>>({});

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const result = await api.getExtractionReady();
        if (!cancelled) {
          setData(result);
          setError(null);
        }
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
  }, [reloadKey]);

  function setNotice(accessionNumber: string, notice: Notice) {
    setNotices((current) => ({ ...current, [accessionNumber]: notice }));
  }

  async function handleExtract(accessionNumber: string) {
    if (!getAdminToken()) {
      setNotice(accessionNumber, {
        kind: "error",
        text: "Save your admin token in the Admin Access panel first — extraction is a protected action.",
      });
      return;
    }

    setBusyAccession(accessionNumber);
    try {
      const result = await api.extractClaims(accessionNumber);
      setNotice(accessionNumber, {
        kind: "success",
        text:
          `Drafted ${result.proposed_claim_count} grounded claims` +
          (result.skipped_invalid_count > 0
            ? ` (${result.skipped_invalid_count} invalid skipped).`
            : "."),
      });
      setReloadKey((k) => k + 1);
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setNotice(accessionNumber, {
          kind: "error",
          text: "Gemini free-tier quota or rate limit reached. No drafts were deleted — try again after the quota window resets.",
        });
      } else if (err instanceof ApiError) {
        setNotice(accessionNumber, { kind: "error", text: err.message });
      } else {
        setNotice(accessionNumber, {
          kind: "error",
          text: "Extraction failed unexpectedly. Please try again.",
        });
      }
    } finally {
      setBusyAccession(null);
    }
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-lg font-semibold">Extraction Ready</h1>
        <p className="text-[12px] text-muted">
          These earnings-release exhibits have been ingested and chunked. They
          are ready for manual AI claim extraction.
        </p>
      </header>

      {error && <ErrorBox message={error} />}
      {loading && !error && <Loading label="Loading extraction queue…" />}

      {!loading && !error && data && data.filings.length === 0 && (
        <Panel>
          <p className="px-1 py-6 text-[13px] text-muted">
            No extraction-ready filings yet. The exhibit worker marks 8-K
            filings here once their earnings release is ingested and chunked.
          </p>
        </Panel>
      )}

      {!loading && !error && data && data.filings.length > 0 && (
        <div className="space-y-3">
          {data.filings.map((filing) => (
            <FilingCard
              key={filing.filing_id}
              filing={filing}
              busy={busyAccession === filing.accession_number}
              notice={notices[filing.accession_number] ?? null}
              onExtract={handleExtract}
            />
          ))}
        </div>
      )}
    </div>
  );
}
