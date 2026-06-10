"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  api,
  type EvidenceDetail,
  type EvidenceItem,
} from "@/lib/api";
import { ErrorBox, Loading, Panel } from "@/components/Panel";
import ResearchHeader from "@/components/ResearchHeader";
import SectionHeader from "@/components/SectionHeader";
import { SourceBadge } from "@/components/Badges";
import { EmptyState, LoadingSkeleton } from "@/components/States";
import { useCompanies } from "@/lib/hooks";

const CLAIM_TYPES = ["", "factual", "interpretive"];
const CONFIDENCES = ["", "high", "medium", "low"];

const selectClass =
  "rounded border border-edge bg-surface-raised px-2 py-1 text-[12px] text-foreground focus:border-accent focus:outline-none";

function ClassBadge({ value }: { value: string | null }) {
  if (!value) return null;
  const style =
    value === "factual"
      ? "text-info border-info/40"
      : "text-accent border-accent/40";
  return (
    <span
      className={`inline-block rounded border px-1.5 py-px font-mono text-[11px] leading-4 ${style}`}
    >
      {value}
    </span>
  );
}

function ReviewedBadge({ value }: { value: boolean | string | null }) {
  const reviewed = value === true || value === "true" || value === "Yes";
  if (!reviewed) return null;
  return (
    <span className="inline-block rounded border border-positive/40 px-1.5 py-px font-mono text-[11px] leading-4 text-positive">
      reviewed
    </span>
  );
}

function EvidenceCard({ item }: { item: EvidenceItem }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<EvidenceDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && !detail) {
      setLoadingDetail(true);
      setDetailError(null);
      try {
        setDetail(await api.getEvidenceDetail(item.qualitative_claim_id));
      } catch (err) {
        setDetailError(err instanceof Error ? err.message : "Failed to load.");
      } finally {
        setLoadingDetail(false);
      }
    }
  }

  return (
    <div className="rounded-md border border-edge bg-surface">
      <div className="flex flex-wrap items-center gap-2 border-b border-edge px-3 py-2 text-[12px]">
        <span className="font-mono font-semibold text-accent">{item.ticker}</span>
        <span className="text-muted">{item.theme}</span>
        <ClassBadge value={item.factual_or_interpretive} />
        <span className="font-mono text-faint">conf {item.confidence ?? "—"}</span>
        <ReviewedBadge value={item.human_reviewed} />
        <span className="ml-auto font-mono text-[11px] text-faint">
          claim #{item.qualitative_claim_id}
        </span>
      </div>
      <div className="px-3 py-2.5">
        <p className="text-[13.5px] text-foreground">{item.claim}</p>
        {item.supporting_excerpt && (
          <blockquote className="mt-2 border-l-2 border-accent/40 pl-2.5 text-[12.5px] italic text-muted">
            {item.supporting_excerpt.length > 240 && !open
              ? `${item.supporting_excerpt.slice(0, 240)}…`
              : item.supporting_excerpt}
          </blockquote>
        )}

        {/* Provenance is made visually prominent on its own row. */}
        <div className="mt-2.5 rounded border border-edge/70 bg-surface-raised px-2.5 py-1.5">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-faint">
            Source provenance
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <SourceBadge
              accession={item.accession_number}
              documentKey={item.document_key}
              chunkId={item.source_chunk_id}
              secUrl={item.sec_url}
              filingDate={item.filing_date}
            />
            <button
              onClick={toggle}
              className="ml-auto whitespace-nowrap rounded border border-edge px-1.5 py-px text-[11px] text-info transition-colors hover:bg-info/10"
              aria-expanded={open}
            >
              {open ? "Hide source text" : "Show source chunk"}
            </button>
          </div>
        </div>

        {open && (
          <div className="mt-3 rounded border border-edge bg-background px-3 py-2.5">
            {loadingDetail && <Loading label="Loading source chunk…" />}
            {detailError && <ErrorBox message={detailError} />}
            {detail && (
              <>
                <div className="mb-1.5 flex flex-wrap gap-x-4 gap-y-0.5 font-mono text-[11px] text-faint">
                  {detail.document?.filename && (
                    <span>doc: {detail.document.filename}</span>
                  )}
                  {detail.filing?.form && <span>{detail.filing.form}</span>}
                  {detail.filing?.report_date && (
                    <span>report {detail.filing.report_date}</span>
                  )}
                </div>
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap text-[12px] leading-relaxed text-muted">
                  {detail.chunk_text ?? "No chunk text available."}
                </pre>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function EvidenceExplorer() {
  const searchParams = useSearchParams();
  const companies = useCompanies();
  const [items, setItems] = useState<EvidenceItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
  }, [ticker, theme, claimType, confidence]);

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

  return (
    <div className="space-y-5">
      <ResearchHeader
        eyebrow="Research"
        title="Evidence Explorer"
        description="Trusted, human-reviewed claims linked to the exact SEC filing chunk they were grounded in. Pending, rejected, and ungrounded drafts never appear here."
      />

      <Panel title="Filters">
        <div className="flex flex-wrap items-center gap-2">
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
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Search claim text, theme, or excerpt…"
            aria-label="Search"
            className="min-w-[220px] flex-1 rounded border border-edge bg-surface-raised px-2 py-1 text-[12px] text-foreground placeholder:text-faint focus:border-accent focus:outline-none"
          />
        </div>
      </Panel>

      {error && <ErrorBox message={error} />}
      {loading && !error && <LoadingSkeleton rows={5} withCards={false} />}

      {items && !loading && (
        <>
          <SectionHeader
            label={text ? `Matching “${text}”` : "Trusted evidence"}
            count={filtered.length}
          />
          {filtered.length === 0 ? (
            <EmptyState
              title="No trusted evidence matches these filters."
              hint="Clear a filter, or extract → review → promote claims to populate the evidence layer."
            />
          ) : (
            <div className="space-y-3">
              {filtered.map((item) => (
                <EvidenceCard key={item.qualitative_claim_id} item={item} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function EvidenceExplorerPage() {
  return (
    <Suspense fallback={<LoadingSkeleton rows={5} />}>
      <EvidenceExplorer />
    </Suspense>
  );
}
