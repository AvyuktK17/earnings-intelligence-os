"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError, type FilingDetail } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import { ErrorBox, Loading, Panel } from "@/components/Panel";

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
      <header className="flex items-baseline gap-3">
        <h1 className="text-lg font-semibold">Filing detail</h1>
        <Link href="/filings" className="text-[12px] text-info hover:underline">
          ← back to filings
        </Link>
      </header>

      {loading && <Loading label="Loading filing…" />}
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
                <StatusBadge status={detail.filing.processing_status} />
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
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-edge text-left text-[11px] uppercase tracking-wider text-muted">
                    <th className="px-2 py-1.5 font-medium">Type</th>
                    <th className="px-2 py-1.5 font-medium">Filename</th>
                    <th className="px-2 py-1.5 font-medium">SEC URL</th>
                    <th className="px-2 py-1.5 font-medium">HTML stored</th>
                    <th className="px-2 py-1.5 font-medium">Text stored</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.documents.map((doc) => (
                    <tr key={doc.id} className="border-b border-edge/60">
                      <td className="px-2 py-1.5 font-mono">
                        {doc.document_type}
                      </td>
                      <td className="px-2 py-1.5 font-mono">{doc.filename}</td>
                      <td className="px-2 py-1.5">
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
                      </td>
                      <td className="px-2 py-1.5 font-mono">
                        <PathFlag present={Boolean(doc.html_storage_path)} />
                      </td>
                      <td className="px-2 py-1.5 font-mono">
                        <PathFlag present={Boolean(doc.text_storage_path)} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        </>
      )}
    </div>
  );
}
