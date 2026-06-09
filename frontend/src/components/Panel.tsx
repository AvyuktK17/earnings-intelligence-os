import type { ReactNode } from "react";

export function Panel({
  title,
  children,
  actions,
}: {
  title?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="rounded-md border border-edge bg-surface">
      {(title || actions) && (
        <header className="flex items-center justify-between border-b border-edge px-4 py-2.5">
          {title && (
            <h2 className="text-[12px] font-semibold uppercase tracking-wider text-muted">
              {title}
            </h2>
          )}
          {actions}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 px-1 py-6 text-[13px] text-muted">
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-edge border-t-accent" />
      {label}
    </div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded border border-negative/40 bg-negative/10 px-3 py-2 text-[13px] text-negative">
      {message}
    </div>
  );
}

export function SuccessNote({ message }: { message: string }) {
  return (
    <div className="rounded border border-positive/40 bg-positive/10 px-3 py-2 text-[13px] text-positive">
      {message}
    </div>
  );
}

export function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <div className="rounded-md border border-edge bg-surface px-4 py-3">
      <div className="text-[11px] uppercase tracking-wider text-muted">
        {label}
      </div>
      <div className="mt-1 font-mono text-2xl text-foreground">{value}</div>
      {hint && <div className="mt-0.5 text-[11px] text-faint">{hint}</div>}
    </div>
  );
}
