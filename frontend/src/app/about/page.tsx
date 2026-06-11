import type { Metadata } from "next";
import Link from "next/link";
import ResearchHeader from "@/components/ResearchHeader";
import { Panel } from "@/components/Panel";

export const metadata: Metadata = {
  title: "About & Methodology — Earnings Intelligence OS",
  description:
    "What this research terminal is, how the evidence-grounded pipeline works, and how AI was used to build it.",
};

/** One stage in the trust pipeline diagram. */
function Stage({
  step,
  title,
  detail,
  automated,
}: {
  step: string;
  title: string;
  detail: string;
  automated: boolean;
}) {
  return (
    <li className="relative border-l-2 border-edge pl-4 pb-5 last:pb-0">
      <span className="absolute -left-[7px] top-0.5 h-3 w-3 rounded-full border-2 border-accent bg-surface" />
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-faint">
          {step}
        </span>
        <span className="text-[13px] font-semibold text-foreground">
          {title}
        </span>
        <span
          className={`rounded border px-1.5 font-mono text-[10px] leading-4 ${
            automated
              ? "border-edge text-faint"
              : "border-accent/50 text-accent"
          }`}
        >
          {automated ? "automated" : "human reviewed"}
        </span>
      </div>
      <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-muted">
        {detail}
      </p>
    </li>
  );
}

export default function AboutPage() {
  return (
    <div className="space-y-6">
      <ResearchHeader
        eyebrow="About"
        title="About & Methodology"
        description="A solo-built equity research platform for semiconductor earnings, designed around one rule: AI drafts, humans approve, and every published claim links back to its exact SEC source."
        actions={
          <a
            href="https://github.com/AvyuktK17/earnings-intelligence-os"
            target="_blank"
            rel="noreferrer"
            className="rounded border border-edge px-3 py-1.5 text-[12px] text-foreground transition-colors hover:border-accent hover:text-accent"
          >
            View source on GitHub ↗
          </a>
        }
      />

      <Panel title="What this is">
        <div className="max-w-3xl space-y-3 text-[13px] leading-relaxed text-muted">
          <p>
            Earnings Intelligence OS continuously monitors SEC EDGAR for new
            filings from five semiconductor companies (NVDA, AMD, AVGO, QCOM,
            INTC), ingests and parses earnings releases, and turns them into
            trusted research outputs: evidence-linked claims, versioned
            earnings briefs, and professional research reports.
          </p>
          <p>
            The core design problem it solves is AI trustworthiness in a
            research setting. Large language models are excellent at reading
            filings and drafting claims — and unreliable enough that nothing
            they produce should be published unchecked. So the system is built
            as a governed pipeline: AI output is quarantined as drafts,
            every claim must literally quote its source document, and only a
            human reviewer can promote a claim into the trusted layer that
            briefs and reports are built from.
          </p>
        </div>
      </Panel>

      <Panel title="The trust pipeline">
        <ol className="mt-1">
          <Stage
            step="01 · Monitor"
            title="SEC EDGAR ingestion"
            detail="A scheduled job checks EDGAR every six hours, detects new filings, downloads and parses them, archives originals to private storage, and splits documents into AI-ready chunks."
            automated
          />
          <Stage
            step="02 · Extract"
            title="Grounded claim drafting"
            detail="On explicit analyst action only, an LLM drafts claims from the earnings-release exhibit. Each draft must include a supporting excerpt that is a literal substring of a source chunk — ungrounded output is rejected automatically."
            automated
          />
          <Stage
            step="03 · Review"
            title="Human approval gate"
            detail="Every draft sits in a review queue until an analyst approves, edits, or rejects it. Nothing reaches the trusted layer without a human decision."
            automated={false}
          />
          <Stage
            step="04 · Publish"
            title="Versioned briefs & reports"
            detail="Earnings briefs and research reports are assembled deterministically from trusted claims, audited fundamentals, and dated valuation snapshots — no AI in the publishing step, and every version is preserved."
            automated
          />
        </ol>
      </Panel>

      <Panel title="What it deliberately does not do">
        <ul className="max-w-3xl list-disc space-y-1.5 pl-5 text-[13px] leading-relaxed text-muted">
          <li>
            No forecasts, price targets, ratings, or DCF outputs — reports
            present reported facts and reviewed takeaways only.
          </li>
          <li>
            No live market feed — valuation figures are dated, manually
            reviewed snapshots and are always labelled as such.
          </li>
          <li>
            No autonomous AI publishing — extraction runs only on analyst
            action, and AI-assisted narratives require explicit approval
            before they become publicly visible.
          </li>
          <li>This is a research engineering project, not investment advice.</li>
        </ul>
      </Panel>

      <Panel title="How AI was used to build this">
        <div className="max-w-3xl space-y-3 text-[13px] leading-relaxed text-muted">
          <p>
            This project was built end-to-end by one person using modern AI
            development tools, treated the way an analyst should treat them:
            as powerful drafters whose output gets reviewed.
          </p>
          <ul className="list-disc space-y-1.5 pl-5">
            <li>
              <span className="text-foreground">Planning with ChatGPT</span> —
              product scoping, architecture decisions, and milestone planning
              were iterated conversationally before code was written.
            </li>
            <li>
              <span className="text-foreground">
                Building with Claude Code
              </span>{" "}
              — the Python ingestion pipeline, FastAPI service, and this
              Next.js terminal were implemented in AI pair-programming
              sessions, with every change reviewed, tested, and committed
              incrementally.
            </li>
            <li>
              <span className="text-foreground">
                A custom Claude Code skill
              </span>{" "}
              — a reusable, guardrailed skill drafts report narratives from
              exported trusted-data packets. It is forbidden from inventing
              forecasts or ratings, must cite chunk-level sources, and its
              drafts enter the same human review queue as everything else.
            </li>
            <li>
              <span className="text-foreground">
                Gemini for claim extraction
              </span>{" "}
              — manual, analyst-triggered extraction with literal-excerpt
              grounding enforced in code.
            </li>
          </ul>
          <p>
            The same governance that applies to the product applied to its
            construction: AI accelerates the work; a human owns the result.
          </p>
        </div>
      </Panel>

      <Panel title="Architecture at a glance">
        <div className="grid gap-3 text-[12.5px] leading-relaxed text-muted sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded border border-hairline p-3">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-foreground">
              Ingestion
            </div>
            <p className="mt-1">
              Python · SEC EDGAR · GitHub Actions cron · idempotent processing
            </p>
          </div>
          <div className="rounded border border-hairline p-3">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-foreground">
              Data
            </div>
            <p className="mt-1">
              Supabase Postgres (13 tables) · private document storage ·
              chunk-level provenance
            </p>
          </div>
          <div className="rounded border border-hairline p-3">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-foreground">
              API
            </div>
            <p className="mt-1">
              FastAPI on Render · public reads · token-protected analyst
              actions · redacted errors
            </p>
          </div>
          <div className="rounded border border-hairline p-3">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-foreground">
              Terminal
            </div>
            <p className="mt-1">
              Next.js + TypeScript + Tailwind on Vercel · this dashboard ·
              talks only to the API
            </p>
          </div>
        </div>
      </Panel>

      <Panel title="Explore">
        <div className="flex flex-wrap gap-2 text-[12.5px]">
          <Link
            href="/evidence"
            className="rounded border border-edge px-3 py-1.5 text-foreground transition-colors hover:border-accent hover:text-accent"
          >
            Evidence Explorer — every claim with its SEC source
          </Link>
          <Link
            href="/reports"
            className="rounded border border-edge px-3 py-1.5 text-foreground transition-colors hover:border-accent hover:text-accent"
          >
            Research Reports — deterministic & Claude-assisted
          </Link>
          <Link
            href="/peers"
            className="rounded border border-edge px-3 py-1.5 text-foreground transition-colors hover:border-accent hover:text-accent"
          >
            Peer Comparison — audited fundamentals
          </Link>
          <a
            href="https://earnings-intelligence-os-api.onrender.com/docs"
            target="_blank"
            rel="noreferrer"
            className="rounded border border-edge px-3 py-1.5 text-foreground transition-colors hover:border-accent hover:text-accent"
          >
            API documentation ↗
          </a>
        </div>
      </Panel>
    </div>
  );
}
