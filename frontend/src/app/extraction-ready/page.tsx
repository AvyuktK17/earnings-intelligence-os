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
import { ErrorBox, Panel, SuccessNote } from "@/components/Panel";
import StatusPill from "@/components/StatusPill";
import ResearchHeader from "@/components/ResearchHeader";
import { DataTable, TH, THead, TR, TD } from "@/components/DataTable";
import { EmptyState, LoadingSkeleton } from "@/components/States";

interface Notice {
  kind: "success" | "error";
  text: string;
}

const LIFECYCLE_STAGES = ["not_started", "pending_review", "approved"];
const STAGE_ACTIVE_STYLES: Record<string, string> = {
  not_started: "text-muted font-semibold",
  pending_review: "text-accent font-semibold",
  approved: "text-positive font-semibold",
};

/** Compact claim-extraction lifecycle trail; failures keep the loud pill. */
function LifecycleTrail({ status }: { status: string }) {
  if (status === "failed") return <StatusPill status="failed" />;
  return (
    <span className="flex items-center gap-1 whitespace-nowrap font-mono text-[10.5px]">
      {LIFECYCLE_STAGES.map((stage, i) => (
        <span key={stage} className="flex items-center gap-1">
          {i > 0 && <span className="text-faint">›</span>}
          <span
            className={
              stage === status ? STAGE_ACTIVE_STYLES[stage] : "text-faint"
            }
          >
            {stage.replace(/_/g, " ")}
          </span>
        </span>
      ))}
    </span>
  );
}

const actionBtn =
  "rounded border px-2 py-0.5 text-[11px] font-medium transition-colors disabled:opacity-50";

function FilingRow({
  filing,
  busy,
  notice,
  onExtract,
  onPromote,
  onGenerateBrief,
}: {
  filing: ExtractionReadyFiling;
  busy: boolean;
  notice: Notice | null;
  onExtract: (accessionNumber: string) => void;
  onPromote: (ticker: string, accessionNumber: string) => void;
  onGenerateBrief: (ticker: string, accessionNumber: string) => void;
}) {
  // Terminal lifecycle step: every grounded draft is reviewed (nothing
  // pending), so the Review Queue no longer lists this filing — promotion
  // must be reachable here or it stays pending_review forever.
  const needsTerminalPromotion =
    filing.claim_extraction_status === "pending_review" &&
    filing.pending_grounded_claim_count === 0;

  // Approved filing with trusted claims but no stored brief: generate v1 here.
  const needsFirstBrief =
    filing.claim_extraction_status === "approved" &&
    filing.trusted_promoted_claim_count > 0 &&
    filing.latest_brief_version == null;

  const hasBrief =
    filing.claim_extraction_status === "approved" &&
    filing.latest_brief_version != null;

  // A failed extraction shows the API's safe, redacted error; any notice from
  // an action renders in a full-width sub-row so the dense table stays aligned.
  const subRow =
    notice ||
    (filing.claim_extraction_status === "failed" &&
      filing.claim_extraction_error);

  return (
    <>
      <TR hover={!subRow}>
        <TD mono className="font-medium">
          <Link
            href={`/companies/${encodeURIComponent(filing.ticker)}`}
            className="text-accent hover:underline"
          >
            {filing.ticker}
          </Link>
        </TD>
        <TD mono>
          <Link
            href={`/filings/${encodeURIComponent(filing.accession_number)}`}
            className="text-info hover:underline"
          >
            {filing.accession_number}
          </Link>
        </TD>
        <TD mono tone="muted">
          {filing.filing_date ?? "—"}
        </TD>
        <TD mono tone="muted" className="max-w-[160px] truncate">
          {filing.filename ?? "—"}
        </TD>
        <TD right mono>
          {filing.chunk_count}
        </TD>
        <TD>
          <StatusPill status={filing.exhibit_processing_status} />
        </TD>
        <TD>
          <LifecycleTrail status={filing.claim_extraction_status} />
        </TD>
        <TD right mono tone={filing.pending_grounded_claim_count > 0 ? "accent" : "faint"}>
          {filing.pending_grounded_claim_count}
        </TD>
        <TD right mono tone={filing.trusted_promoted_claim_count > 0 ? "positive" : "faint"}>
          {filing.trusted_promoted_claim_count}
        </TD>
        <TD mono>
          {hasBrief ? (
            <Link
              href={`/briefs/latest/${encodeURIComponent(filing.ticker)}`}
              className="text-info hover:underline"
            >
              v{filing.latest_brief_version}
            </Link>
          ) : (
            <span className="text-faint">—</span>
          )}
        </TD>
        <TD>
          <div className="flex flex-wrap items-center gap-1.5">
            <button
              className={`${actionBtn} border-accent/50 text-accent hover:bg-accent/10`}
              disabled={busy}
              onClick={() => onExtract(filing.accession_number)}
            >
              {busy ? "…" : "Extract"}
            </button>
            {needsTerminalPromotion && (
              <button
                className={`${actionBtn} border-positive/50 text-positive hover:bg-positive/10`}
                disabled={busy}
                onClick={() => onPromote(filing.ticker, filing.accession_number)}
              >
                Promote
              </button>
            )}
            {needsFirstBrief && (
              <button
                className={`${actionBtn} border-info/50 text-info hover:bg-info/10`}
                disabled={busy}
                onClick={() =>
                  onGenerateBrief(filing.ticker, filing.accession_number)
                }
              >
                Brief
              </button>
            )}
          </div>
        </TD>
      </TR>
      {subRow && (
        <tr className="border-b border-hairline/60">
          <td colSpan={11} className="pb-3">
            {notice ? (
              notice.kind === "success" ? (
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
              )
            ) : (
              filing.claim_extraction_error && (
                <ErrorBox message={filing.claim_extraction_error} />
              )
            )}
          </td>
        </tr>
      )}
    </>
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

  async function handleGenerateBrief(ticker: string, accessionNumber: string) {
    if (!getAdminToken()) {
      setNotice(accessionNumber, {
        kind: "error",
        text: "Save your admin token in the Admin Access panel first — brief generation is a protected action.",
      });
      return;
    }

    setBusyAccession(accessionNumber);
    try {
      const result = await api.generateBrief(ticker, accessionNumber);
      setNotice(accessionNumber, {
        kind: "success",
        text: `Brief v${result.version_number} generated and stored (${result.trusted_claim_count} trusted claims).`,
      });
      setReloadKey((k) => k + 1);
    } catch (err) {
      setNotice(accessionNumber, {
        kind: "error",
        text:
          err instanceof ApiError
            ? err.message
            : "Brief generation failed unexpectedly. Please try again.",
      });
    } finally {
      setBusyAccession(null);
    }
  }

  async function handlePromote(ticker: string, accessionNumber: string) {
    if (!getAdminToken()) {
      setNotice(accessionNumber, {
        kind: "error",
        text: "Save your admin token in the Admin Access panel first — promotion is a protected action.",
      });
      return;
    }

    setBusyAccession(accessionNumber);
    try {
      const result = await api.promoteClaims(ticker, accessionNumber);
      const approved = result.approved_filings?.includes(accessionNumber);
      setNotice(accessionNumber, {
        kind: "success",
        text:
          `Promoted ${result.promoted_count} reviewed claims ` +
          `(${result.skipped_existing_count} already promoted).` +
          (approved ? " Filing is now approved." : ""),
      });
      setReloadKey((k) => k + 1);
    } catch (err) {
      setNotice(accessionNumber, {
        kind: "error",
        text:
          err instanceof ApiError
            ? err.message
            : "Promotion failed unexpectedly. Please try again.",
      });
    } finally {
      setBusyAccession(null);
    }
  }

  return (
    <div className="space-y-5">
      <ResearchHeader
        eyebrow="Workflow"
        title="Extraction Ready"
        description="Earnings-release exhibits that have been ingested and chunked — ready for admin-triggered grounded claim extraction."
      />

      {error && <ErrorBox message={error} />}
      {loading && !error && <LoadingSkeleton rows={5} withCards={false} />}

      {!loading && !error && data && data.filings.length === 0 && (
        <EmptyState
          title="No extraction-ready filings yet."
          hint="The exhibit worker marks 8-K filings here once their earnings release is ingested and chunked."
        />
      )}

      {!loading && !error && data && data.filings.length > 0 && (
        <Panel title={`Extraction queue · ${data.filings.length}`}>
          <DataTable minWidth={1100}>
            <THead>
              <TH>Ticker</TH>
              <TH>Accession</TH>
              <TH>Filed</TH>
              <TH>Exhibit</TH>
              <TH right>Chunks</TH>
              <TH>Exhibit stage</TH>
              <TH>Claim stage</TH>
              <TH right>Pending</TH>
              <TH right>Trusted</TH>
              <TH>Brief</TH>
              <TH>Action</TH>
            </THead>
            <tbody>
              {data.filings.map((filing) => (
                <FilingRow
                  key={filing.filing_id}
                  filing={filing}
                  busy={busyAccession === filing.accession_number}
                  notice={notices[filing.accession_number] ?? null}
                  onExtract={handleExtract}
                  onPromote={handlePromote}
                  onGenerateBrief={handleGenerateBrief}
                />
              ))}
            </tbody>
          </DataTable>
        </Panel>
      )}
    </div>
  );
}
