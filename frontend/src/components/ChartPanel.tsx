import type { ReactNode } from "react";
import { Panel } from "@/components/Panel";

/**
 * A Panel tuned for charts: consistent title, optional right-aligned control
 * (e.g. a metric selector), a fixed chart area, and an optional caption line
 * for units / ranking notes beneath the chart.
 */
export default function ChartPanel({
  title,
  control,
  caption,
  children,
}: {
  title: string;
  control?: ReactNode;
  caption?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Panel title={title} actions={control}>
      <div className="min-w-0">{children}</div>
      {caption && <p className="mt-1.5 text-[11px] text-faint">{caption}</p>}
    </Panel>
  );
}
