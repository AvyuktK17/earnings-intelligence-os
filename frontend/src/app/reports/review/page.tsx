"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import {
  api,
  ApiError,
  getAdminToken,
  subscribeAdminToken,
  type ReportReviewItem,
} from "@/lib/api";
import { ErrorBox, Loading, Panel, SuccessNote } from "@/components/Panel";

function useAdminToken() {
  return useSyncExternalStore(
    subscribeAdminToken,
    () => getAdminToken(),
    () => null,
  );
}

type Mode = "idle" | "edit" | "reject";

function DraftCard({
  draft,
  onDone,
  onError,
}: {
  draft: ReportReviewItem;
  onDone: (message: string) => void;
  onError: (message: string) => void;
}) {
  const [mode, setMode] = useState<Mode>("idle");
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState("");
  const [editedMarkdown, setEditedMarkdown] = useState(draft.markdown_content);
  const [rejectionReason, setRejectionReason] = useState("");
  const [skipped, setSkipped] = useState(false);

  if (skipped) return null;

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    try {
      await action();
      onDone(success);
    } catch (err) {
      onError(
        err instanceof Error ? err.message : "Action failed. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title={`${draft.ticker} · v${draft.version_number} · ${draft.title}`}
    >
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <span className="rounded border border-warning/50 px-1.5 py-px font-mono text-warning">
            Claude-assisted draft
          </span>
          <span className="rounded border border-edge px-1.5 py-px font-mono text-muted">
            {draft.report_type.replace(/_/g, " ")}
          </span>
          {draft.accession_number && (
            <Link
              href={`/filings/${encodeURIComponent(draft.accession_number)}`}
              className="font-mono text-info hover:underline"
            >
              {draft.accession_number}
            </Link>
          )}
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[12px] sm:grid-cols-3">
          <div>
            <span className="text-faint">Imported:</span>{" "}
            <span className="font-mono">
              {draft.imported_at
                ? new Date(draft.imported_at).toLocaleString()
                : "—"}
            </span>
          </div>
          <div>
            <span className="text-faint">Source report:</span>{" "}
            <span className="font-mono">{draft.source_report_id ?? "—"}</span>
          </div>
          <div>
            <span className="text-faint">Trusted claims:</span>{" "}
            <span className="font-mono">{draft.source_claim_count ?? "—"}</span>
          </div>
          <div>
            <span className="text-faint">Evidence links:</span>{" "}
            <span className="font-mono">{draft.evidence_link_count}</span>
          </div>
          <div>
            <span className="text-faint">Valuation:</span>{" "}
            <span className="font-mono">
              {draft.valuation_snapshot_date ?? "—"}
            </span>
          </div>
          <div>
            <span className="text-faint">Packet hash:</span>{" "}
            <span className="font-mono" title={draft.source_packet_hash ?? ""}>
              {draft.source_packet_hash
                ? `${draft.source_packet_hash.slice(0, 12)}…`
                : "—"}
            </span>
          </div>
        </div>

        <details className="rounded border border-edge bg-surface-raised">
          <summary className="cursor-pointer px-3 py-1.5 text-[12px] text-muted">
            Rendered draft preview
          </summary>
          <article className="brief-markdown max-h-[420px] overflow-y-auto px-3 py-2 text-[13px]">
            <ReactMarkdown>{draft.markdown_content}</ReactMarkdown>
          </article>
        </details>

        {mode === "idle" && (
          <div className="space-y-2">
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Reviewer notes (optional)…"
              className="w-full rounded border border-edge bg-surface-raised px-2 py-1 text-[12px]"
              rows={2}
            />
            <div className="flex flex-wrap gap-2">
              <button
                disabled={busy}
                onClick={() =>
                  run(
                    () => api.approveReport(draft.id, notes || undefined),
                    `Approved ${draft.ticker} v${draft.version_number}.`,
                  )
                }
                className="rounded border border-positive/50 px-2.5 py-1 text-[12px] font-medium text-positive hover:bg-positive/10 disabled:opacity-50"
              >
                {busy ? "Working…" : "Approve"}
              </button>
              <button
                disabled={busy}
                onClick={() => setMode("edit")}
                className="rounded border border-accent/50 px-2.5 py-1 text-[12px] font-medium text-accent hover:bg-accent/10 disabled:opacity-50"
              >
                Edit and Approve
              </button>
              <button
                disabled={busy}
                onClick={() => setMode("reject")}
                className="rounded border border-negative/50 px-2.5 py-1 text-[12px] font-medium text-negative hover:bg-negative/10 disabled:opacity-50"
              >
                Reject
              </button>
              <button
                disabled={busy}
                onClick={() => setSkipped(true)}
                className="rounded border border-edge px-2.5 py-1 text-[12px] font-medium text-muted hover:bg-surface-raised disabled:opacity-50"
              >
                Skip
              </button>
            </div>
          </div>
        )}

        {mode === "edit" && (
          <div className="space-y-2">
            <textarea
              value={editedMarkdown}
              onChange={(e) => setEditedMarkdown(e.target.value)}
              className="h-64 w-full rounded border border-edge bg-surface-raised px-2 py-1 font-mono text-[12px]"
            />
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Reviewer notes (optional)…"
              className="w-full rounded border border-edge bg-surface-raised px-2 py-1 text-[12px]"
              rows={2}
            />
            <p className="text-[11px] text-faint">
              The original imported draft is preserved immutably (superseded);
              this creates a new reviewed version.
            </p>
            <div className="flex gap-2">
              <button
                disabled={busy || !editedMarkdown.trim()}
                onClick={() =>
                  run(
                    () =>
                      api.editAndApproveReport(
                        draft.id,
                        editedMarkdown,
                        notes || undefined,
                      ),
                    `Edited and approved ${draft.ticker} as a new reviewed version.`,
                  )
                }
                className="rounded border border-accent/50 px-2.5 py-1 text-[12px] font-medium text-accent hover:bg-accent/10 disabled:opacity-50"
              >
                {busy ? "Working…" : "Save reviewed version"}
              </button>
              <button
                disabled={busy}
                onClick={() => setMode("idle")}
                className="rounded border border-edge px-2.5 py-1 text-[12px] text-muted hover:bg-surface-raised"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {mode === "reject" && (
          <div className="space-y-2">
            <textarea
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              placeholder="Rejection reason (required)…"
              className="w-full rounded border border-negative/40 bg-surface-raised px-2 py-1 text-[12px]"
              rows={2}
            />
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Reviewer notes (optional)…"
              className="w-full rounded border border-edge bg-surface-raised px-2 py-1 text-[12px]"
              rows={2}
            />
            <div className="flex gap-2">
              <button
                disabled={busy || !rejectionReason.trim()}
                onClick={() =>
                  run(
                    () =>
                      api.rejectReport(
                        draft.id,
                        rejectionReason,
                        notes || undefined,
                      ),
                    `Rejected ${draft.ticker} v${draft.version_number}.`,
                  )
                }
                className="rounded border border-negative/50 px-2.5 py-1 text-[12px] font-medium text-negative hover:bg-negative/10 disabled:opacity-50"
              >
                {busy ? "Working…" : "Confirm reject"}
              </button>
              <button
                disabled={busy}
                onClick={() => setMode("idle")}
                className="rounded border border-edge px-2.5 py-1 text-[12px] text-muted hover:bg-surface-raised"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}

export default function NarrativeReviewPage() {
  const adminToken = useAdminToken();
  const [drafts, setDrafts] = useState<ReportReviewItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!adminToken) {
        if (!cancelled) setDrafts(null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const r = await api.getReportReviewQueue();
        if (!cancelled) setDrafts(r.reports);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          setError("Admin token missing or invalid.");
          setDrafts(null);
        } else {
          setError(
            err instanceof Error ? err.message : "Failed to load review queue.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [adminToken, reloadKey]);

  function handleDone(message: string) {
    setFlash(message);
    setError(null);
    setReloadKey((k) => k + 1);
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-lg font-semibold">Narrative Review</h1>
        <p className="text-[12px] text-muted">
          Claude-assisted narrative drafts awaiting analyst review. Drafts are
          private until approved — they never appear on public report pages.
        </p>
      </header>

      {flash && <SuccessNote message={flash} />}
      {error && <ErrorBox message={error} />}

      {!adminToken && (
        <Panel>
          <div className="py-8 text-center">
            <p className="text-[14px] text-muted">Admin token required.</p>
            <p className="mt-1 text-[12px] text-faint">
              Save an admin token in the sidebar to review imported narrative
              drafts.
            </p>
          </div>
        </Panel>
      )}

      {adminToken && loading && <Loading label="Loading review queue…" />}

      {adminToken && drafts && drafts.length === 0 && !loading && (
        <Panel>
          <div className="py-8 text-center">
            <p className="text-[14px] text-muted">No drafts awaiting review.</p>
            <p className="mt-1 text-[12px] text-faint">
              Import a Claude-assisted draft locally with{" "}
              <span className="font-mono">import_claude_narrative.py</span> to
              populate this queue.
            </p>
          </div>
        </Panel>
      )}

      {adminToken &&
        drafts &&
        drafts.map((draft) => (
          <DraftCard
            key={draft.id}
            draft={draft}
            onDone={handleDone}
            onError={setError}
          />
        ))}
    </div>
  );
}
