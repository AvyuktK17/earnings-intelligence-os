import type { ReactNode } from "react";

/**
 * Small provenance and classification badges. SourceBadge makes filing
 * provenance (accession / document-key / chunk id / SEC link) visually
 * prominent; ReportTypeBadge labels deterministic vs Claude-assisted reports
 * and their reviewed/draft state.
 */

function Chip({
  children,
  className = "border-edge text-faint",
  title,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded border px-1.5 py-px font-mono text-[11px] leading-4 ${className}`}
    >
      {children}
    </span>
  );
}

export function SourceBadge({
  accession,
  documentKey,
  chunkId,
  secUrl,
  filingDate,
}: {
  accession?: string | null;
  documentKey?: string | null;
  chunkId?: number | string | null;
  secUrl?: string | null;
  filingDate?: string | null;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {accession && (
        <Chip className="border-edge-strong text-muted" title="Accession number">
          {accession}
        </Chip>
      )}
      {documentKey && (
        <Chip className="border-edge text-faint" title="Document key">
          {documentKey}
        </Chip>
      )}
      {chunkId != null && (
        <Chip className="border-edge text-faint" title="Source chunk id">
          chunk {chunkId}
        </Chip>
      )}
      {filingDate && (
        <Chip className="border-edge text-faint" title="Filing date">
          filed {filingDate}
        </Chip>
      )}
      {secUrl && (
        <a
          href={secUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 whitespace-nowrap rounded border border-info/40 px-1.5 py-px font-mono text-[11px] leading-4 text-info transition-colors hover:bg-info/10"
        >
          SEC source ↗
        </a>
      )}
    </div>
  );
}

export function ReportTypeBadge({
  generatorType,
  reportStatus,
}: {
  generatorType: string;
  reportStatus?: string;
}) {
  const isClaude = generatorType === "claude_assisted";
  const label = isClaude ? "Claude-assisted" : "Deterministic";
  const cls = isClaude
    ? "border-warning/50 text-warning"
    : "border-info/50 text-info";

  // Optional state suffix so the lifecycle reads in one chip on viewer pages.
  let suffix: string | null = null;
  if (reportStatus === "reviewed") suffix = "reviewed";
  else if (reportStatus === "draft") suffix = "draft";
  else if (reportStatus === "human_reviewed_deterministic") suffix = "published";

  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded border px-1.5 py-px font-mono text-[11px] leading-4 ${cls}`}
    >
      {label}
      {suffix && <span className="text-faint">· {suffix}</span>}
    </span>
  );
}
