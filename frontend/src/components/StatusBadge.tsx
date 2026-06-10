const STATUS_STYLES: Record<string, string> = {
  detected: "text-info border-info/40",
  downloaded: "text-foreground border-edge",
  parsed: "text-accent border-accent/40",
  chunked: "text-positive border-positive/40",
  processed: "text-positive border-positive/40",
  failed: "text-negative border-negative/40",
  not_started: "text-muted border-edge",
  pending_review: "text-accent border-accent/40",
  approved: "text-positive border-positive/40",
};

export default function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? "text-muted border-edge";
  return (
    <span
      className={`inline-block rounded border px-1.5 py-px font-mono text-[11px] leading-4 ${style}`}
    >
      {status}
    </span>
  );
}
