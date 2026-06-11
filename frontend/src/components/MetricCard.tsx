import type { ReactNode } from "react";

type Tone = "default" | "positive" | "negative" | "accent" | "info";

const TONE_VALUE: Record<Tone, string> = {
  default: "text-foreground",
  positive: "text-positive",
  negative: "text-negative",
  accent: "text-accent",
  info: "text-info",
};

/**
 * Compact KPI cell with a consistent label / value / hint hierarchy and
 * monospaced figures so columns of metrics align across a grid.
 */
export default function MetricCard({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: Tone;
}) {
  return (
    <div className="rounded-md border border-hairline bg-surface px-3.5 py-2.5">
      <div className="truncate text-[10px] font-medium uppercase tracking-wider text-muted">
        {label}
      </div>
      <div
        className={`mt-1 font-mono text-xl leading-none tabular-nums ${TONE_VALUE[tone]}`}
      >
        {value}
      </div>
      {hint && (
        <div className="mt-1 truncate text-[10.5px] leading-snug text-faint">
          {hint}
        </div>
      )}
    </div>
  );
}
