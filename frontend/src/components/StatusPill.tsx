/**
 * Unified status pill with a single status-color mapping shared across the
 * terminal (filing lifecycle, extraction lifecycle, report lifecycle). Any
 * unknown status falls back to a neutral edge tone rather than disappearing.
 */

export type Tone =
  | "neutral"
  | "info"
  | "accent"
  | "positive"
  | "negative"
  | "warning";

const TONE_CLASS: Record<Tone, string> = {
  neutral: "text-muted border-edge",
  info: "text-info border-info/40",
  accent: "text-accent border-accent/40",
  positive: "text-positive border-positive/40",
  negative: "text-negative border-negative/40",
  warning: "text-warning border-warning/40",
};

// One canonical mapping from a backend status string to a tone.
const STATUS_TONE: Record<string, Tone> = {
  // filing processing lifecycle
  detected: "info",
  downloaded: "neutral",
  parsed: "accent",
  chunked: "positive",
  // exhibit / extraction lifecycle
  not_checked: "neutral",
  not_found: "neutral",
  processed: "positive",
  not_started: "neutral",
  pending: "accent",
  pending_review: "accent",
  reviewed: "positive",
  approved: "positive",
  // report lifecycle
  draft: "warning",
  superseded: "neutral",
  rejected: "negative",
  human_reviewed_deterministic: "positive",
  // shared
  failed: "negative",
};

export function statusTone(status: string): Tone {
  return STATUS_TONE[status] ?? "neutral";
}

export default function StatusPill({
  status,
  tone,
  label,
}: {
  status: string;
  /** Override the auto-derived tone when needed. */
  tone?: Tone;
  /** Override the displayed text (defaults to the status, underscores spaced). */
  label?: string;
}) {
  const resolved = tone ?? statusTone(status);
  return (
    <span
      className={`inline-block whitespace-nowrap rounded border px-1.5 py-px font-mono text-[11px] leading-4 ${TONE_CLASS[resolved]}`}
    >
      {label ?? status.replace(/_/g, " ")}
    </span>
  );
}
