"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import AdminAccess from "@/components/AdminAccess";
import { api } from "@/lib/api";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/peers", label: "Peer Comparison" },
  { href: "/filings", label: "Filings" },
  { href: "/extraction-ready", label: "Extraction Ready" },
  { href: "/review-queue", label: "Review Queue" },
  { href: "/briefs/latest/AVGO", label: "Latest Brief" },
];

// Fallback only if GET /companies fails; the live list comes from the API.
const FALLBACK_TICKERS = ["AMD", "AVGO", "INTC", "NVDA", "QCOM"];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href.startsWith("/briefs")) return pathname.startsWith("/briefs");
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function Nav() {
  const pathname = usePathname();
  const [tickers, setTickers] = useState<string[] | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadCompanies() {
      try {
        const result = await api.getCompanies();
        if (!cancelled) setTickers(result.companies.map((c) => c.ticker));
      } catch {
        if (!cancelled) setTickers(FALLBACK_TICKERS);
      }
    }

    loadCompanies();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <aside className="w-56 shrink-0 border-r border-edge bg-surface flex flex-col min-h-screen">
      <div className="px-4 py-5 border-b border-edge">
        <Link href="/" className="block">
          <div className="text-sm font-semibold tracking-wide">
            Earnings Intelligence OS
          </div>
          <div className="text-[11px] text-muted mt-0.5 tracking-wider uppercase">
            Semiconductor Research Terminal
          </div>
        </Link>
      </div>
      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={`block rounded px-3 py-1.5 text-[13px] transition-colors ${
              isActive(pathname, link.href)
                ? "bg-surface-raised text-accent font-medium"
                : "text-muted hover:text-foreground hover:bg-surface-raised"
            }`}
          >
            {link.label}
          </Link>
        ))}

        <div className="px-3 pb-1 pt-4 text-[10px] font-semibold uppercase tracking-wider text-faint">
          Companies
        </div>
        {(tickers ?? []).map((ticker) => (
          <Link
            key={ticker}
            href={`/companies/${encodeURIComponent(ticker)}`}
            className={`block rounded px-3 py-1 font-mono text-[12px] transition-colors ${
              pathname === `/companies/${ticker}`
                ? "bg-surface-raised text-accent font-medium"
                : "text-muted hover:text-foreground hover:bg-surface-raised"
            }`}
          >
            {ticker}
          </Link>
        ))}
        {tickers === null && (
          <div className="px-3 py-1 font-mono text-[11px] text-faint">
            loading…
          </div>
        )}
      </nav>
      <AdminAccess />
      <div className="px-4 py-3 border-t border-edge text-[11px] text-faint font-mono">
        live · SEC ingestion + analyst review
      </div>
    </aside>
  );
}
