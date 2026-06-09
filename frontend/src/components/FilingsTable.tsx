import Link from "next/link";
import type { Filing } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";

export default function FilingsTable({
  filings,
  showReportDate = false,
}: {
  filings: Filing[];
  showReportDate?: boolean;
}) {
  if (filings.length === 0) {
    return (
      <p className="px-1 py-4 text-[13px] text-muted">
        No filings match the current filters.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-edge text-left text-[11px] uppercase tracking-wider text-muted">
            <th className="px-2 py-1.5 font-medium">Ticker</th>
            <th className="px-2 py-1.5 font-medium">Form</th>
            <th className="px-2 py-1.5 font-medium">Filed</th>
            {showReportDate && (
              <th className="px-2 py-1.5 font-medium">Report date</th>
            )}
            <th className="px-2 py-1.5 font-medium">Accession number</th>
            <th className="px-2 py-1.5 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {filings.map((filing) => (
            <tr
              key={filing.id}
              className="border-b border-edge/60 hover:bg-surface-raised"
            >
              <td className="px-2 py-1.5 font-mono font-medium text-accent">
                {filing.ticker}
              </td>
              <td className="px-2 py-1.5 font-mono">{filing.form}</td>
              <td className="px-2 py-1.5 font-mono text-muted">
                {filing.filing_date ?? "—"}
              </td>
              {showReportDate && (
                <td className="px-2 py-1.5 font-mono text-muted">
                  {filing.report_date ?? "—"}
                </td>
              )}
              <td className="px-2 py-1.5 font-mono">
                <Link
                  href={`/filings/${encodeURIComponent(filing.accession_number)}`}
                  className="text-info hover:underline"
                >
                  {filing.accession_number}
                </Link>
              </td>
              <td className="px-2 py-1.5">
                <StatusBadge status={filing.processing_status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
