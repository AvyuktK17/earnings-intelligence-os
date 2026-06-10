"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError, type FilingDetail } from "@/lib/api";
import StatusPill from "@/components/StatusPill";
import { ErrorBox, Panel } from "@/components/Panel";
import ResearchHeader from "@/components/ResearchHeader";
import { DataTable, TH, THead, TR, TD } from "@/components/DataTable";
import { LoadingSkeleton } from "@/components/States";

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wider text-muted">
        {label}
      </dt>
      <dd className="mt-0.5 font-mono text-[13px]">{children}</dd>
    </div>
  );
}

function PathFlag({ present }: { present: boolean }) {
  return present ? (
    <span className="text-positive">yes</span>
  ) : (
    <span className="text-faint">no</span>
  );
}

export default function FilingDetailPage({
  params,
}: {
  params: Promise<{ accessionNumber: string }>;
}) {
  const { accessionNumber } = use(params);
  const accession = decodeURIComponent(accessionNumber);

  const [detail, setDetail] = useState<FilingDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    api
      .getFiling(accession)
      .then((result) => {
        if (!cancelled) setDetail(result);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) setNotFound(true);
        else
          setError(
            err instanceof Error ? err.message : "Failed to load filing.",
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [accession]);

  return (
    <div className="space-y-5">
      <ResearchHeader
        eyebrow="Workflow"
        title="Filing detail"
        description={accession}
        actions={
          <Link
            href="/filings"
            className="text-[12px] text-info hover:underline"
          >
            ← back to filings
          </Link>
        }
      />

      {loading && <LoadingSkeleton rows={6} />}
      {error && <ErrorBox message={error} />}
      {notFound && (
        <ErrorBox message={`No filing found for ${accession}.`} />
      )}

      {detail && (
        <>
          <Panel title="Filing">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 lg:grid-cols-4">
              <Field label="Ticker">
                <span className="text-accent">{detail.filing.ticker}</span>
              </Field>
              <Field label="Form">{detail.filing.form}</Field>
              <Field label="Filing date">
                {detail.filing.filing_date ?? "—"}
              </Field>
              <Field label="Report date">
                {detail.filing.report_date ?? "—"}
              </Field>
              <Field label="Accession number">
                {detail.filing.accession_number}
              </Field>
              <Field label="Status">
                <StatusPill status={detail.filing.processing_status} />
              </Field>
              <Field label="Chunk count">{detail.chunk_count}</Field>
              <Field label="SEC URL">
                {detail.filing.sec_url ? (
                  <a
                    href={detail.filing.sec_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-info hover:underline"
                  >
                    open on EDGAR ↗
                  </a>
                ) : (
                  "—"
                )}
              </Field>
              <Field label="Downloaded at">
                {detail.filing.downloaded_at ?? "—"}
              </Field>
              <Field label="Parsed at">{detail.filing.parsed_at ?? "—"}</Field>
              <Field label="Chunked at">
                {detail.filing.chunked_at ?? "—"}
              </Field>
            </dl>
            {detail.filing.processing_error && (
              <div className="mt-4">
                <ErrorBox
                  message={`Processing error: ${detail.filing.processing_error}`}
                />
              </div>
            )}
          </Panel>

          <Panel title={`Documents · ${detail.documents.length}`}>
            {detail.documents.length === 0 ? (
              <p className="px-1 py-2 text-[13px] text-muted">
                No exhibit documents recorded for this filing.
              </p>
            ) : (
              <DataTable minWidth={560}>
                <THead>
                  <TH>Type</TH>
                  <TH>Filename</TH>
                  <TH>SEC URL</TH>
                  <TH>HTML stored</TH>
                  <TH>Text stored</TH>
                </THead>
                <tbody>
                  {detail.documents.map((doc) => (
                    <TR key={doc.id}>
                      <TD mono>{doc.document_type}</TD>
                      <TD mono>{doc.filename}</TD>
                      <TD>
                        {doc.sec_url ? (
                          <a
                            href={doc.sec_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-info hover:underline"
                          >
                            open ↗
                          </a>
                        ) : (
                          "—"
                        )}
                      </TD>
                      <TD mono>
                        <PathFlag present={Boolean(doc.html_storage_path)} />
                      </TD>
                      <TD mono>
                        <PathFlag present={Boolean(doc.text_storage_path)} />
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </DataTable>
            )}
          </Panel>
        </>
      )}
    </div>
  );
}
