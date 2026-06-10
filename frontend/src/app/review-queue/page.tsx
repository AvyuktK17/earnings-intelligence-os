"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, type ProposedClaim } from "@/lib/api";
import { ErrorBox, Panel, SuccessNote } from "@/components/Panel";
import ResearchHeader from "@/components/ResearchHeader";
import { EmptyState, LoadingSkeleton } from "@/components/States";

const buttonClass =
  "rounded border px-2.5 py-1 text-[12px] font-medium transition-colors disabled:opacity-50";
const inputClass =
  "w-full rounded border border-edge bg-surface-raised px-2 py-1.5 text-[13px] " +
  "text-foreground placeholder-faint focus:border-accent focus:outline-none";

function ClaimCard({
  claim,
  onDone,
}: {
  claim: ProposedClaim;
  onDone: (message: string) => void;
}) {
  const [mode, setMode] = useState<"idle" | "approve" | "edit" | "reject">(
    "idle",
  );
  const [notes, setNotes] = useState("");
  const [editedText, setEditedText] = useState(claim.claim_text);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setActionError(null);
    try {
      await action();
      onDone(message);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Action failed.");
      setBusy(false);
    }
  }

  return (
    <div className="rounded-md border border-edge bg-surface p-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] text-muted">
        <span className="font-medium text-accent">{claim.ticker}</span>
        <span>{claim.accession_number}</span>
        <span>{claim.document_key}</span>
        <span>
          chunk {claim.source_chunk_index} · id {claim.source_chunk_id}
        </span>
        <span className="rounded border border-edge px-1.5">
          {claim.claim_type}
        </span>
        <span className="rounded border border-edge px-1.5">
          confidence: {claim.confidence}
        </span>
      </div>

      <h3 className="mt-2 text-[13px] font-semibold text-foreground">
        {claim.theme}
      </h3>
      <p className="mt-1 text-[13px] leading-relaxed">{claim.claim_text}</p>
      <blockquote className="mt-2 border-l-2 border-edge pl-3 text-[12px] leading-relaxed text-muted">
        “{claim.supporting_excerpt}”
      </blockquote>

      {actionError && (
        <div className="mt-3">
          <ErrorBox message={actionError} />
        </div>
      )}

      {mode === "idle" && (
        <div className="mt-3 flex gap-2">
          <button
            className={`${buttonClass} border-positive/50 text-positive hover:bg-positive/10`}
            onClick={() => setMode("approve")}
          >
            Approve
          </button>
          <button
            className={`${buttonClass} border-accent/50 text-accent hover:bg-accent/10`}
            onClick={() => setMode("edit")}
          >
            Edit &amp; Approve
          </button>
          <button
            className={`${buttonClass} border-negative/50 text-negative hover:bg-negative/10`}
            onClick={() => setMode("reject")}
          >
            Reject
          </button>
        </div>
      )}

      {mode !== "idle" && (
        <div className="mt-3 space-y-2">
          {mode === "edit" && (
            <textarea
              className={`${inputClass} min-h-20 font-sans`}
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
              placeholder="Edited claim text"
            />
          )}
          <input
            className={inputClass}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Reviewer notes (optional)"
          />
          <div className="flex gap-2">
            {mode === "approve" && (
              <button
                disabled={busy}
                className={`${buttonClass} border-positive/50 text-positive hover:bg-positive/10`}
                onClick={() =>
                  run(
                    () => api.approveClaim(claim.id, notes),
                    `Claim ${claim.id} approved.`,
                  )
                }
              >
                {busy ? "Approving…" : "Confirm approve"}
              </button>
            )}
            {mode === "edit" && (
              <button
                disabled={busy || !editedText.trim()}
                className={`${buttonClass} border-accent/50 text-accent hover:bg-accent/10`}
                onClick={() =>
                  run(
                    () => api.editClaim(claim.id, editedText.trim(), notes),
                    `Claim ${claim.id} approved with edits.`,
                  )
                }
              >
                {busy ? "Saving…" : "Confirm edit & approve"}
              </button>
            )}
            {mode === "reject" && (
              <button
                disabled={busy}
                className={`${buttonClass} border-negative/50 text-negative hover:bg-negative/10`}
                onClick={() =>
                  run(
                    () => api.rejectClaim(claim.id, notes),
                    `Claim ${claim.id} rejected.`,
                  )
                }
              >
                {busy ? "Rejecting…" : "Confirm reject"}
              </button>
            )}
            <button
              disabled={busy}
              className={`${buttonClass} border-edge text-muted hover:bg-surface-raised`}
              onClick={() => {
                setMode("idle");
                setActionError(null);
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ReviewQueuePage() {
  const [claims, setClaims] = useState<ProposedClaim[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [promoting, setPromoting] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await api.getReviewQueue();
        if (!cancelled) {
          setClaims(data.claims);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load queue.",
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

  const refresh = useCallback(() => setReloadKey((k) => k + 1), []);

  function handleDone(message: string) {
    setFlash(message);
    refresh();
  }

  // Group claims by filing so promotion can be scoped to a known filing.
  const filingGroups = useMemo(() => {
    const groups = new Map<string, ProposedClaim[]>();
    for (const claim of claims ?? []) {
      const key = `${claim.ticker}|${claim.accession_number}`;
      const list = groups.get(key) ?? [];
      list.push(claim);
      groups.set(key, list);
    }
    return [...groups.entries()].map(([key, list]) => {
      const [ticker, accessionNumber] = key.split("|");
      return { ticker, accessionNumber, claims: list };
    });
  }, [claims]);

  async function promoteFiling(ticker: string, accessionNumber: string) {
    setPromoting(true);
    setError(null);
    try {
      const result = await api.promoteClaims(ticker, accessionNumber);
      setFlash(
        `Promotion for ${ticker} ${accessionNumber}: ` +
          `${result.promoted_count} promoted, ` +
          `${result.skipped_existing_count} already promoted.`,
      );
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Promotion failed.");
    } finally {
      setPromoting(false);
    }
  }

  return (
    <div className="space-y-5">
      <ResearchHeader
        eyebrow="Workflow"
        title="Review Queue"
        description="Grounded AI-drafted claims awaiting analyst review — nothing enters trusted research without approval."
      />

      {flash && <SuccessNote message={flash} />}
      {error && <ErrorBox message={error} />}
      {loading && <LoadingSkeleton rows={4} withCards={false} />}

      {!loading && claims && claims.length === 0 && (
        <EmptyState
          title="The review queue is empty."
          hint={
            <>
              New grounded claims appear here after a manual extraction run.
              Reviewed claims can be promoted and published via the{" "}
              <Link
                href="/briefs/latest/AVGO"
                className="text-info hover:underline"
              >
                latest brief
              </Link>
              .
            </>
          }
        />
      )}

      {!loading &&
        filingGroups.map((group) => (
          <Panel
            key={`${group.ticker}-${group.accessionNumber}`}
            title={`${group.ticker} · ${group.accessionNumber} · ${group.claims.length} pending`}
            actions={
              <button
                disabled={promoting}
                className={`${buttonClass} border-info/50 text-info hover:bg-info/10`}
                onClick={() =>
                  promoteFiling(group.ticker, group.accessionNumber)
                }
              >
                {promoting
                  ? "Promoting…"
                  : "Promote reviewed claims for this filing"}
              </button>
            }
          >
            <div className="space-y-3">
              {group.claims.map((claim) => (
                <ClaimCard key={claim.id} claim={claim} onDone={handleDone} />
              ))}
            </div>
          </Panel>
        ))}
    </div>
  );
}
