import type { ReactNode } from "react";

/**
 * Standard page masthead for the research terminal: an eyebrow label, the page
 * title, an optional one-line description, and an optional right-aligned slot
 * for badges or actions. Keeps every page's header rhythm identical.
 */
export default function ResearchHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-3 border-b border-edge pb-3">
      <div className="min-w-0">
        {eyebrow && (
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-faint">
            {eyebrow}
          </div>
        )}
        <h1 className="mt-0.5 text-lg font-semibold leading-tight text-foreground">
          {title}
        </h1>
        {description && (
          <p className="mt-1 max-w-2xl text-[12px] leading-snug text-muted">
            {description}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
      )}
    </header>
  );
}
