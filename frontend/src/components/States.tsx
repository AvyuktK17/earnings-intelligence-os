"use client";

import type { ReactNode } from "react";
import { useSyncExternalStore } from "react";
import { getApiIsSlow, subscribeApiSlow } from "@/lib/api";

/**
 * Shared loading / empty / cold-start states. These keep every page honest:
 * loading shows structure, empty explains why and what to do next, and the
 * cold-start notice explains the Render free-tier wake-up delay instead of
 * leaving the analyst staring at a spinner.
 */

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: ReactNode;
  hint?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-md border border-dashed border-edge bg-surface px-4 py-10 text-center">
      <p className="text-[14px] text-muted">{title}</p>
      {hint && (
        <p className="mx-auto mt-1.5 max-w-md text-[12px] leading-snug text-faint">
          {hint}
        </p>
      )}
      {action && <div className="mt-3 flex justify-center">{action}</div>}
    </div>
  );
}

export function SkeletonLine({ className = "" }: { className?: string }) {
  return <div className={`skeleton h-3 ${className}`} />;
}

/** Generic content skeleton: a few cards plus stacked rows. */
export function LoadingSkeleton({
  rows = 5,
  withCards = true,
}: {
  rows?: number;
  withCards?: boolean;
}) {
  return (
    <div className="space-y-4" aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading…</span>
      {withCards && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-md border border-edge bg-surface p-3.5">
              <SkeletonLine className="w-1/2" />
              <div className="skeleton mt-2 h-5 w-3/4" />
            </div>
          ))}
        </div>
      )}
      <div className="rounded-md border border-edge bg-surface p-4">
        <SkeletonLine className="mb-3 w-1/4" />
        <div className="space-y-2">
          {Array.from({ length: rows }).map((_, i) => (
            <SkeletonLine key={i} className={i % 3 === 0 ? "w-5/6" : "w-full"} />
          ))}
        </div>
      </div>
    </div>
  );
}

function useApiIsSlow() {
  return useSyncExternalStore(subscribeApiSlow, getApiIsSlow, () => false);
}

/**
 * Global, non-blocking banner shown while any request is unusually slow —
 * almost always the Render dyno waking from sleep on the first call of a
 * session. Rendered once in the root layout.
 */
export function ColdStartNotice() {
  const slow = useApiIsSlow();
  if (!slow) return null;
  return (
    <div
      role="status"
      className="flex items-center gap-2 border-b border-warning/30 bg-warning/10 px-4 py-1.5 text-[12px] text-warning"
    >
      <span className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-warning" />
      Waking the research API (Render free tier sleeps when idle). This first
      request can take up to a minute — later requests are fast.
    </div>
  );
}
