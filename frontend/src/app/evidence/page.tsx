"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  api,
  type EvidenceDetail,
  type EvidenceItem,
} from "@/lib/api";
import { ErrorBox, Loading, Panel, SuccessNote } from "@/components/Panel";
import ResearchHeader from "@/components/ResearchHeader";
import { SourceBadge } from "@/components/Badges";
import { EmptyState, LoadingSkeleton } from "@/components/States";
import { useAdminToken, useCompanies } from "@/lib/hooks";

const CLAIM_TYPES = ["", "factual", "interpretive"];
const CONFIDENCES = ["", "high", "medium", "low"];

const selectClass =
  "w-full rounded border border-edge bg-surface-raised px-2 py-1 text-[12px] text-foreground focus:border-accent focus:outline-none";

function ClassBadge({ value }: { value: string | null }) {
  if (!value) return null;
  const style =
    value === "factual"
      ? "text-info border-info/40"
      : "text-accent border-accent/40";
  return (
    <span
      className={`inline-block rounded border px-1.5 py-px font-mono text-[10px] uppercase tracking-wide leading-4 ${style}`}
    >
      {value}
    </span>
  );
}

function ReviewedBadge({ value }: { value: boolean | string | null }) {
  const reviewed = value === true || value === "true" || value === "Yes";
  if (!reviewed) return null;
  return (
    <span className="inline-block rounded border border-positive/40 px-1.5 py-px font-mono text-[10px] uppercase tracking-wide leading-4 text-positive">
      reviewed
    </span>
  );
}

/**
 * Admin-only correction modal. Shows the claim's identity, status, and
 * immutable source excerpt directly above the editable wording so the
 * analyst can compare the revision against the quote before saving. Only
 * the claim text is sent — the excerpt and provenance cannot be edited.
 */
function EditClaimModal({
  item,
  onClose,
  onSaved,
}: {
  item: EvidenceItem;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const [text, setText] = useState(item.claim);
  const [excerpt, setExcerpt] = useState(item.supporting_excerpt ?? "");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const textChanged = text.trim() !== item.claim;
  const excerptChanged =
    excerpt.trim() !== (item.supporting_excerpt ?? "").trim();

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.editEvidenceClaim(item.qualitative_claim_id, {
        editedClaimText: textChanged ? text.trim() : undefined,
        editedSupportingExcerpt: excerptChanged ? excerpt.trim() : undefined,
        reviewerNotes: notes.trim() || undefined,
      });
      onSaved(
        `Claim #${item.qualitative_claim_id} corrected. The original wording is preserved in the audit trail.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Correction failed.");
      setBusy(false);
    }
  }

  const fieldClass =
    "w-full rounded border border-edge bg-surface-raised px-2 py-1.5 text-[13px] " +
    "text-foreground placeholder-faint focus:border-accent focus:outline-none";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`Edit claim ${item.qualitative_claim_id}`}
    >
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-md border border-edge bg-surface p-4 shadow-lg">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-hairline pb-2 font-mono text-[11px] text-muted">
          <span className="text-[12px] font-semibold uppercase tracking-wider text-foreground">
            Edit claim
          </span>
          <span>claim #{item.qualitative_claim_id}</span>
          <span className="font-medium text-accent">{item.ticker}</span>
          <span>{item.accession_number ?? "—"}</span>
          <span>chunk {item.source_chunk_id ?? "—"}</span>
          <span className="rounded border border-positive/40 px-1.5 text-positive">
            trusted · human reviewed
          </span>
        </div>

        <div className="mt-3 space-y-3">
          <div>
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-faint">
              Current excerpt
            </div>
            <blockquote className="border-l-2 border-accent/40 pl-2.5 text-[12.5px] italic leading-relaxed text-muted">
              “{item.supporting_excerpt ?? "—"}”
            </blockquote>
          </div>

          <div>
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-faint">
              Current claim text
            </div>
            <p className="text-[12.5px] leading-relaxed text-muted">
              {item.claim}
            </p>
          </div>

          <label className="block">
            <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-faint">
              Corrected claim text — verify every figure against the excerpt
            </span>
            <textarea
              className={`${fieldClass} min-h-24 font-sans`}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-faint">
              Corrected excerpt (optional) — must be an exact quote from the
              source chunk; the API rejects anything that isn&apos;t
            </span>
            <textarea
              className={`${fieldClass} min-h-16 font-sans italic`}
              value={excerpt}
              onChange={(e) => setExcerpt(e.target.value)}
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-faint">
              Reviewer notes (optional — why the correction was needed)
            </span>
            <input
              className={fieldClass}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. growth figure corrected to match the excerpt"
            />
          </label>

          {error && <ErrorBox message={error} />}

          <div className="flex gap-2 pt-1">
            <button
              disabled={
                busy ||
                !text.trim() ||
                !excerpt.trim() ||
                (!textChanged && !excerptChanged)
              }
              className="rounded border border-positive/50 px-2.5 py-1 text-[12px] font-medium text-positive transition-colors hover:bg-positive/10 disabled:opacity-50"
              onClick={save}
            >
              {busy ? "Saving…" : "Save correction"}
            </button>
            <button
              disabled={busy}
              className="rounded border border-edge px-2.5 py-1 text-[12px] font-medium text-muted transition-colors hover:bg-surface-raised disabled:opacity-50"
              onClick={onClose}
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Right pane: the selected claim with excerpt, provenance chain, source chunk. */
function ClaimDetail({
  item,
  canEdit,
  onSaved,
}: {
  item: EvidenceItem;
  canEdit: boolean;
  onSaved: (message: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [detail, setDetail] = useState<EvidenceDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setDetail(null);
      setError(null);
      setLoading(true);
      try {
        const d = await api.getEvidenceDetail(item.qualitative_claim_id);
        if (!cancelled) setDetail(d);
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Failed to load.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [item.qualitative_claim_id]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="font-mono font-semibold text-accent">
          {item.ticker}
        </span>
        <span className="text-muted">{item.theme}</span>
        <ClassBadge value={item.factual_or_interpretive} />
        <span className="font-mono text-faint">conf {item.confidence ?? "—"}</span>
        <ReviewedBadge value={item.human_reviewed} />
        <span className="ml-auto font-mono text-[11px] text-faint">
          claim #{item.qualitative_claim_id}
        </span>
        {canEdit && (
          <button
            className="rounded border border-accent/50 px-2 py-0.5 text-[11px] font-medium text-accent transition-colors hover:bg-accent/10"
            onClick={() => setEditing(true)}
          >
            Edit claim
          </button>
        )}
      </div>

      {editing && (
        <EditClaimModal
          item={item}
          onClose={() => setEditing(false)}
          onSaved={(message) => {
            setEditing(false);
            onSaved(message);
          }}
        />
      )}

      <p className="text-[13.5px] leading-relaxed text-foreground">
        {item.claim}
      </p>

      {item.supporting_excerpt && (
        <div>
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-faint">
            Supporting excerpt
          </div>
          <blockquote className="border-l-2 border-accent/40 pl-2.5 text-[12.5px] italic leading-relaxed text-muted">
            “{item.supporting_excerpt}”
          </blockquote>
        </div>
      )}

      {/* Provenance chain */}
      <div className="rounded border border-hairline bg-surface-raised px-2.5 py-2">
        <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-faint">
          Provenance chain
        </div>
        <SourceBadge
          accession={item.accession_number}
          documentKey={item.document_key}
          chunkId={item.source_chunk_id}
          secUrl={item.sec_url}
          filingDate={item.filing_date}
        />
      </div>

      {/* Source chunk */}
      <div>
        <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-faint">
          Source chunk
        </div>
        {loading && <Loading label="Loading source chunk…" />}
        {error && <ErrorBox message={error} />}
        {detail && (
          <div className="rounded border border-hairline bg-background px-3 py-2.5">
            <div className="mb-1.5 flex flex-wrap gap-x-4 gap-y-0.5 font-mono text-[11px] text-faint">
              {detail.document?.filename && (
                <span>doc: {detail.document.filename}</span>
              )}
              {detail.filing?.form && <span>{detail.filing.form}</span>}
              {detail.filing?.report_date && (
                <span>report {detail.filing.report_date}</span>
              )}
            </div>
            <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap text-[12px] leading-relaxed text-muted">
              {detail.chunk_text ?? "No chunk text available."}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

function EvidenceExplorer() {
  const searchParams = useSearchParams();
  const companies = useCompanies();
  const adminToken = useAdminToken();
  const [items, setItems] = useState<EvidenceItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [ticker, setTicker] = useState(searchParams.get("ticker") ?? "");
  const [theme, setTheme] = useState("");
  const [claimType, setClaimType] = useState("");
  const [confidence, setConfidence] = useState("");
  const [text, setText] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const r = await api.getEvidence({
          ticker: ticker || undefined,
          theme: theme || undefined,
          claim_type: claimType || undefined,
          confidence: confidence || undefined,
          limit: 200,
        });
        if (!cancelled) setItems(r.evidence);
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Failed to load evidence.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [ticker, theme, claimType, confidence, reloadKey]);

  // Theme options derived from whatever is currently loaded.
  const themes = useMemo(() => {
    const set = new Set<string>();
    for (const i of items ?? []) if (i.theme) set.add(i.theme);
    return [...set].sort();
  }, [items]);

  const filtered = useMemo(() => {
    if (!items) return [];
    const q = text.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (i) =>
        i.claim.toLowerCase().includes(q) ||
        (i.theme ?? "").toLowerCase().includes(q) ||
        (i.supporting_excerpt ?? "").toLowerCase().includes(q),
    );
  }, [items, text]);

  // Resolve the effective selection during render: honor the clicked id when it
  // is still in the filtered list, otherwise fall back to the first match. This
  // avoids a selection-syncing effect (and its cascading-render lint warning).
  const effectiveId =
    selectedId != null &&
    filtered.some((i) => i.qualitative_claim_id === selectedId)
      ? selectedId
      : (filtered[0]?.qualitative_claim_id ?? null);
  const selected =
    filtered.find((i) => i.qualitative_claim_id === effectiveId) ?? null;

  return (
    <div className="space-y-5">
      <ResearchHeader
        eyebrow="Research"
        title="Evidence Explorer"
        description="Trusted, human-reviewed claims linked to the exact SEC filing chunk they were grounded in. Pending, rejected, and ungrounded drafts never appear here."
      />

      {flash && <SuccessNote message={flash} />}
      {error && <ErrorBox message={error} />}
      {loading && !error && <LoadingSkeleton rows={6} />}

      {items && !loading && (
        <div className="grid gap-4 lg:grid-cols-[210px_minmax(0,1fr)_minmax(0,460px)]">
          {/* Left: compact filters */}
          <Panel title="Filters">
            <div className="space-y-2.5">
              <Filter label="Ticker">
                <select
                  aria-label="Ticker"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value)}
                  className={selectClass}
                >
                  <option value="">All tickers</option>
                  {companies.map((c) => (
                    <option key={c.ticker} value={c.ticker}>
                      {c.ticker}
                    </option>
                  ))}
                </select>
              </Filter>
              <Filter label="Theme">
                <select
                  aria-label="Theme"
                  value={theme}
                  onChange={(e) => setTheme(e.target.value)}
                  className={selectClass}
                >
                  <option value="">All themes</option>
                  {themes.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </Filter>
              <Filter label="Claim type">
                <select
                  aria-label="Claim type"
                  value={claimType}
                  onChange={(e) => setClaimType(e.target.value)}
                  className={selectClass}
                >
                  {CLAIM_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t || "All types"}
                    </option>
                  ))}
                </select>
              </Filter>
              <Filter label="Confidence">
                <select
                  aria-label="Confidence"
                  value={confidence}
                  onChange={(e) => setConfidence(e.target.value)}
                  className={selectClass}
                >
                  {CONFIDENCES.map((t) => (
                    <option key={t} value={t}>
                      {t || "All confidence"}
                    </option>
                  ))}
                </select>
              </Filter>
              <Filter label="Search">
                <input
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Claim, theme, excerpt…"
                  aria-label="Search"
                  className={selectClass}
                />
              </Filter>
            </div>
          </Panel>

          {/* Center: claim list */}
          <Panel
            title={text ? `Matching “${text}”` : "Trusted claims"}
            actions={
              <span className="font-mono text-[11px] text-faint">
                {filtered.length} claims
              </span>
            }
          >
            {filtered.length === 0 ? (
              <EmptyState
                title="No trusted evidence matches these filters."
                hint="Clear a filter, or extract → review → promote claims to populate the evidence layer."
              />
            ) : (
              <ul className="max-h-[640px] space-y-1.5 overflow-y-auto pr-0.5">
                {filtered.map((item) => {
                  const active = item.qualitative_claim_id === effectiveId;
                  return (
                    <li key={item.qualitative_claim_id}>
                      <button
                        onClick={() =>
                          setSelectedId(item.qualitative_claim_id)
                        }
                        className={`w-full rounded border px-2.5 py-2 text-left transition-colors ${
                          active
                            ? "border-accent/50 bg-accent/5"
                            : "border-hairline hover:border-hairline-strong hover:bg-surface-raised/60"
                        }`}
                      >
                        <div className="mb-1 flex flex-wrap items-center gap-2 text-[10px]">
                          <span className="font-mono font-semibold text-accent">
                            {item.ticker}
                          </span>
                          <span className="text-muted">{item.theme}</span>
                          <span className="ml-auto font-mono text-faint">
                            #{item.qualitative_claim_id}
                          </span>
                        </div>
                        <p
                          className={`line-clamp-2 text-[12.5px] leading-snug ${
                            active ? "text-foreground" : "text-muted"
                          }`}
                        >
                          {item.claim}
                        </p>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </Panel>

          {/* Right: selected claim detail */}
          <Panel title="Selected claim">
            {selected ? (
              <ClaimDetail
                item={selected}
                canEdit={Boolean(adminToken)}
                onSaved={(message) => {
                  setFlash(message);
                  setReloadKey((k) => k + 1);
                }}
              />
            ) : (
              <p className="py-6 text-center text-[12px] text-faint">
                Select a claim to view its excerpt, provenance chain, and source
                chunk.
              </p>
            )}
          </Panel>
        </div>
      )}
    </div>
  );
}

function Filter({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-faint">
        {label}
      </span>
      {children}
    </label>
  );
}

export default function EvidenceExplorerPage() {
  return (
    <Suspense fallback={<LoadingSkeleton rows={5} />}>
      <EvidenceExplorer />
    </Suspense>
  );
}
