// Back-compat shim: StatusBadge now delegates to the unified StatusPill so the
// status-color mapping lives in exactly one place.
import StatusPill from "@/components/StatusPill";

export default function StatusBadge({ status }: { status: string }) {
  return <StatusPill status={status} label={status} />;
}
