/**
 * Honest labeling for the manually reviewed valuation data. The dashboard must
 * never imply that valuation figures are a live market feed.
 */

export function ValuationBadge({ date }: { date: string | null | undefined }) {
  if (!date) return null;
  return (
    <span className="inline-block rounded border border-accent/40 px-1.5 py-px font-mono text-[11px] leading-4 text-accent">
      Valuation snapshot as of {date}
    </span>
  );
}

export function ValuationDisclaimer({ text }: { text?: string }) {
  return (
    <p className="text-[11px] text-faint">
      {text ??
        "Valuation data is a manually reviewed point-in-time snapshot, not a live market feed."}
    </p>
  );
}
