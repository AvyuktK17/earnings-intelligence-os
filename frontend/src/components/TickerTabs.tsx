import Link from "next/link";

/**
 * Horizontal ticker selector used by the per-company report and brief pages.
 * `basePath` is suffixed with the encoded ticker, so one component serves
 * /reports/latest/<t> and /briefs/latest/<t>.
 */
export default function TickerTabs({
  tickers,
  active,
  basePath,
}: {
  tickers: string[] | null;
  active: string;
  basePath: string;
}) {
  if (tickers === null) {
    return (
      <div className="flex gap-1.5" aria-busy="true">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="skeleton h-6 w-12" />
        ))}
      </div>
    );
  }
  return (
    <div className="flex flex-wrap gap-1.5" role="tablist">
      {tickers.map((t) => {
        const isActive = t === active;
        return (
          <Link
            key={t}
            href={`${basePath}/${encodeURIComponent(t)}`}
            role="tab"
            aria-selected={isActive}
            className={`rounded border px-2.5 py-1 font-mono text-[12px] transition-colors ${
              isActive
                ? "border-accent/60 bg-accent/10 font-semibold text-accent"
                : "border-edge text-muted hover:border-accent/40 hover:text-foreground"
            }`}
          >
            {t}
          </Link>
        );
      })}
    </div>
  );
}
