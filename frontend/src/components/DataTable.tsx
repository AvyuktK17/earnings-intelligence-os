import type { ReactNode } from "react";

/**
 * Consistent dense table primitives for the terminal. Tables share one set of
 * header / row / cell styles so spacing, borders, and alignment never drift,
 * and `DataTable` provides responsive horizontal overflow with an optional
 * minimum width for wide financial tables.
 */

export function DataTable({
  children,
  minWidth,
  className = "",
}: {
  children: ReactNode;
  /** Minimum width in px before horizontal scrolling kicks in. */
  minWidth?: number;
  className?: string;
}) {
  return (
    <div className="-mx-1 overflow-x-auto px-1">
      <table
        className={`w-full text-left text-[13px] ${className}`}
        style={minWidth ? { minWidth } : undefined}
      >
        {children}
      </table>
    </div>
  );
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead>
      <tr className="border-b border-edge text-[11px] uppercase tracking-wider text-muted">
        {children}
      </tr>
    </thead>
  );
}

export function TH({
  children,
  right,
  className = "",
}: {
  children?: ReactNode;
  right?: boolean;
  className?: string;
}) {
  return (
    <th
      scope="col"
      className={`py-1.5 pr-3 font-medium ${right ? "text-right" : ""} ${className}`}
    >
      {children}
    </th>
  );
}

export function TR({
  children,
  hover = true,
}: {
  children: ReactNode;
  hover?: boolean;
}) {
  return (
    <tr
      className={`border-b border-edge/50 last:border-b-0 ${
        hover ? "hover:bg-surface-raised" : ""
      }`}
    >
      {children}
    </tr>
  );
}

export function TD({
  children,
  right,
  mono,
  tone,
  className = "",
}: {
  children?: ReactNode;
  right?: boolean;
  mono?: boolean;
  tone?: "muted" | "faint" | "accent" | "info";
  className?: string;
}) {
  const toneClass =
    tone === "muted"
      ? "text-muted"
      : tone === "faint"
        ? "text-faint"
        : tone === "accent"
          ? "text-accent"
          : tone === "info"
            ? "text-info"
            : "";
  return (
    <td
      className={`py-1.5 pr-3 ${right ? "text-right tabular-nums" : ""} ${
        mono ? "font-mono" : ""
      } ${toneClass} ${className}`}
    >
      {children}
    </td>
  );
}
