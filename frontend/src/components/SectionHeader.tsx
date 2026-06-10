import type { ReactNode } from "react";

/**
 * A labelled section divider used inside or above content blocks. Pairs an
 * uppercase section label with an optional count chip and right-aligned actions.
 */
export default function SectionHeader({
  label,
  count,
  actions,
  className = "",
}: {
  label: ReactNode;
  count?: number | string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-wrap items-center justify-between gap-2 ${className}`}
    >
      <div className="flex items-center gap-2">
        <h2 className="text-[12px] font-semibold uppercase tracking-wider text-muted">
          {label}
        </h2>
        {count != null && (
          <span className="rounded border border-edge px-1.5 font-mono text-[11px] leading-4 text-faint">
            {count}
          </span>
        )}
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-2">{actions}</div>
      )}
    </div>
  );
}
