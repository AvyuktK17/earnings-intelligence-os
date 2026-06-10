import Link from "next/link";
import type { Filing } from "@/lib/api";
import StatusPill from "@/components/StatusPill";
import { DataTable, TH, THead, TR, TD } from "@/components/DataTable";

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
    <DataTable minWidth={560}>
      <THead>
        <TH>Ticker</TH>
        <TH>Form</TH>
        <TH>Filed</TH>
        {showReportDate && <TH>Report date</TH>}
        <TH>Accession number</TH>
        <TH>Status</TH>
      </THead>
      <tbody>
        {filings.map((filing) => (
          <TR key={filing.id}>
            <TD mono className="font-medium">
              <Link
                href={`/companies/${encodeURIComponent(filing.ticker)}`}
                className="text-accent hover:underline"
              >
                {filing.ticker}
              </Link>
            </TD>
            <TD mono>{filing.form}</TD>
            <TD mono tone="muted">
              {filing.filing_date ?? "—"}
            </TD>
            {showReportDate && (
              <TD mono tone="muted">
                {filing.report_date ?? "—"}
              </TD>
            )}
            <TD mono>
              <Link
                href={`/filings/${encodeURIComponent(filing.accession_number)}`}
                className="text-info hover:underline"
              >
                {filing.accession_number}
              </Link>
            </TD>
            <TD>
              <StatusPill status={filing.processing_status} />
            </TD>
          </TR>
        ))}
      </tbody>
    </DataTable>
  );
}
