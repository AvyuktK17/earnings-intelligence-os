"use client";

import { useEffect, useMemo, useState } from "react";
import {
  api,
  type Company,
  type EvidenceDetail,
  type EvidenceItem,
} from "@/lib/api";
import { ErrorBox, Loading, Panel } from "@/components/Panel";

const CLAIM_TYPES = ["", "factual", "interpretive"];
const CONFIDENCES = ["", "high", "medium", "low"];

function ClassBadge({ value }: { value: string | null }) {
  if (!value) return null;
  const style =
    value === "factual"
      ? "text-info border-info/40"
      : "text-accent border-accent/40";
  return (
    <span className={`inline-block rounded border px-1.5 py-px font-mono text-[11px] leading-4 ${style}`}>
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
          <blockquote className="mt-2 border-l-2 border-edge pl-2.5 text-[12.5px] text-muted">
            {item.supporting_excerpt.length > 220 && !open
              ? `${item.supporting_excerpt.slice(0, 220)}…`
              : item.supporting_excerpt}
          </blockquote>
        )}
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] text-faint">
          <span>{item.accession_number ?? "—"}</span>
          <span>{item.document_key ?? "—"}</span>
          <span>chunk {item.source_chunk_id ?? "—"}</span>
          {item.filing_date && <span>filed {item.filing_date}</span>}
          {item.sec_url && (
            <a
              href={item.sec_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-info hover:text-accent hover:underline"
            >
              SEC source ↗
            </a>
          )}
          <button
            onClick={toggle}
            className="text-info hover:text-accent hover:underline"
          >
            {open ? "Hide source text" : "Show full source text"}
          </button>
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

export default function EvidenceExplorerPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [items, setItems] = useState<EvidenceItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [ticker, setTicker] = useState("");
  const [claimType, setClaimType] = useState("");
  const [confidence, setConfidence] = useState("");
  const [text, setText] = useState("");

  useEffect(() => {
    api.getCompanies().then((r) => setCompanies(r.companies)).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const r = await api.getEvidence({
          ticker: ticker || undefined,
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
  }, [ticker, claimType, confidence]);

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
      <header>
        <h1 className="text-lg font-semibold">Evidence Explorer</h1>
        <p className="text-[12px] uppercase tracking-wider text-muted">
          Trusted, human-reviewed claims linked to SEC filing evidence
        </p>
      </header>

      <Panel title="Filters">
        <div className="flex flex-wrap items-center gap-2 text-[12px]">
          <select
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            className="rounded border border-edge bg-surface-raised px-2 py-1 text-foreground"
          >
            <option value="">All tickers</option>
            {companies.map((c) => (
              <option key={c.ticker} value={c.ticker}>
                {c.ticker}
              </option>
            ))}
          </select>
          <select
            value={claimType}
            onChange={(e) => setClaimType(e.target.value)}
            className="rounded border border-edge bg-surface-raised px-2 py-1 text-foreground"
          >
            {CLAIM_TYPES.map((t) => (
              <option key={t} value={t}>
                {t || "All types"}
              </option>
            ))}
          </select>
          <select
            value={confidence}
            onChange={(e) => setConfidence(e.target.value)}
            className="rounded border border-edge bg-surface-raised px-2 py-1 text-foreground"
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
            placeholder="Search claim text or theme…"
            className="min-w-[220px] flex-1 rounded border border-edge bg-surface-raised px-2 py-1 text-foreground placeholder:text-faint"
          />
        </div>
      </Panel>

      {error && <ErrorBox message={error} />}
      {loading && !error && <Loading label="Loading evidence…" />}

      {items && !loading && (
        <>
          <p className="text-[12px] text-faint">
            {filtered.length} trusted claim{filtered.length === 1 ? "" : "s"}
            {text && ` matching “${text}”`}
          </p>
          {filtered.length === 0 ? (
            <Panel>
              <div className="py-8 text-center text-[13px] text-muted">
                No trusted evidence matches these filters.
              </div>
            </Panel>
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
