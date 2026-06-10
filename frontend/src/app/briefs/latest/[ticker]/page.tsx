"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import { api, ApiError, type Brief } from "@/lib/api";
import { ErrorBox, Panel, SuccessNote } from "@/components/Panel";
import ResearchHeader from "@/components/ResearchHeader";
import MetricCard from "@/components/MetricCard";
import TickerTabs from "@/components/TickerTabs";
import { EmptyState, LoadingSkeleton } from "@/components/States";
import { useCompanyTickers } from "@/lib/hooks";

export default function LatestBriefPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker: rawTicker } = use(params);
  const ticker = decodeURIComponent(rawTicker).toUpperCase();
  const tickers = useCompanyTickers();

  const [brief, setBrief] = useState<Brief | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const data = await api.getLatestBrief(ticker);
        if (!cancelled) {
          setBrief(data);
          setNotFound(false);
          setError(null);
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setBrief(null);
          setNotFound(true);
        } else {
          setError(err instanceof Error ? err.message : "Failed to load brief.");
        }
      }
      if (!cancelled) setLoading(false);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [ticker, reloadKey]);

  async function generateNewVersion() {
    if (!brief) return;
    setGenerating(true);
    setError(null);
    setFlash(null);
    try {
      const result = await api.generateBrief(ticker, brief.accession_number);
      setFlash(
        `Brief v${result.version_number} generated and stored ` +
          `(${result.trusted_claim_count} trusted claims).`,
      );
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="space-y-5">
      <ResearchHeader
        eyebrow="Research"
        title={`Latest Brief · ${ticker}`}
        description="Evidence-linked briefing built only from trusted, human-reviewed claims."
      />

      <TickerTabs tickers={tickers} active={ticker} basePath="/briefs/latest" />

      {flash && <SuccessNote message={flash} />}
      {error && <ErrorBox message={error} />}
      {loading && <LoadingSkeleton rows={8} />}

      {notFound && !loading && (
        <EmptyState
          title={`No stored brief exists for ${ticker} yet.`}
          hint={
            <>
              Briefs are generated from promoted trusted claims. Once a filing for{" "}
              {ticker} is approved with trusted claims, generate the first version
              from the{" "}
              <Link href="/extraction-ready" className="text-info hover:underline">
                Extraction Ready page
              </Link>
              .
            </>
          }
        />
      )}

      {brief && !loading && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <MetricCard
              label="Version"
              value={`v${brief.version_number}`}
              hint={`generated ${new Date(brief.generated_at).toLocaleDateString()}`}
            />
            <MetricCard
              label="Trusted claims"
              value={brief.trusted_claim_count}
              hint="human-reviewed only"
              tone="positive"
            />
            <MetricCard label="Factual" value={brief.factual_claim_count} />
            <MetricCard label="Interpretive" value={brief.interpretive_claim_count} />
          </div>

          <Panel
            title={`${brief.ticker} · ${brief.accession_number}`}
            actions={
              <button
                disabled={generating}
                className="rounded border border-accent/50 px-2.5 py-1 text-[12px] font-medium text-accent transition-colors hover:bg-accent/10 disabled:opacity-50"
                onClick={generateNewVersion}
              >
                {generating ? "Generating…" : "Generate new brief version"}
              </button>
            }
          >
            <article className="brief-markdown max-w-3xl text-[13.5px]">
              <ReactMarkdown>{brief.markdown_content}</ReactMarkdown>
            </article>
          </Panel>
        </>
      )}
    </div>
  );
}
