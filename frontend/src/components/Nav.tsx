"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import AdminAccess from "@/components/AdminAccess";
import { useCompanyTickers } from "@/lib/hooks";

type NavLink = {
  href: string;
  label: string;
  /** Custom active matcher; defaults to exact or nested match. */
  match?: (pathname: string) => boolean;
};

type NavGroup = { label: string; links: NavLink[] };

// Grouped navigation: Markets / Research / Workflow. Active matching is
// explicit where prefixes overlap (e.g. /reports vs /reports/review) so only
// one item ever highlights.
const GROUPS: NavGroup[] = [
  {
    label: "Markets",
    links: [
      { href: "/", label: "Overview", match: (p) => p === "/" },
      { href: "/peers", label: "Peer Comparison" },
    ],
  },
  {
    label: "Research",
    links: [
      { href: "/evidence", label: "Evidence Explorer" },
      {
        href: "/reports",
        label: "Reports",
        // Reports index + per-company viewers, but NOT the review queue.
        match: (p) =>
          p === "/reports" || p.startsWith("/reports/latest"),
      },
      {
        href: "/briefs/latest/AVGO",
        label: "Latest Brief",
        match: (p) => p.startsWith("/briefs"),
      },
    ],
  },
  {
    label: "Workflow",
    links: [
      { href: "/filings", label: "Filings" },
      { href: "/extraction-ready", label: "Extraction Ready" },
      { href: "/review-queue", label: "Review Queue" },
      {
        href: "/reports/review",
        label: "Narrative Review",
        match: (p) => p.startsWith("/reports/review"),
      },
    ],
  },
];

function defaultMatch(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function Nav() {
  const pathname = usePathname();
  const tickers = useCompanyTickers();

  function NavItem({ link }: { link: NavLink }) {
    const active = link.match
      ? link.match(pathname)
      : defaultMatch(pathname, link.href);
    return (
      <Link
        href={link.href}
        aria-current={active ? "page" : undefined}
        className={`block rounded px-3 py-1.5 text-[13px] transition-colors ${
          active
            ? "bg-surface-raised font-medium text-accent shadow-[inset_2px_0_0_0_var(--accent)]"
            : "text-muted hover:bg-surface-raised hover:text-foreground"
        }`}
      >
        {link.label}
      </Link>
    );
  }

  return (
    <aside className="flex w-full shrink-0 flex-col border-b border-edge bg-surface lg:min-h-screen lg:w-60 lg:border-b-0 lg:border-r">
      <div className="border-b border-edge px-4 py-4">
        <Link href="/" className="block">
          <div className="text-sm font-semibold tracking-wide">
            Earnings Intelligence OS
          </div>
          <div className="mt-0.5 text-[10px] uppercase tracking-[0.18em] text-muted">
            Semiconductor Research Terminal
          </div>
        </Link>
      </div>

      <nav className="flex-1 space-y-4 px-2 py-3" aria-label="Primary">
        {GROUPS.map((group) => (
          <div key={group.label} className="space-y-0.5">
            <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-faint">
              {group.label}
            </div>
            {group.links.map((link) => (
              <NavItem key={link.href} link={link} />
            ))}
            {group.label === "Markets" && (
              <div className="pt-1">
                <div className="px-3 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-faint">
                  Companies
                </div>
                <div className="flex flex-wrap gap-1 px-2 lg:block lg:space-y-0.5">
                  {(tickers ?? []).map((ticker) => (
                    <Link
                      key={ticker}
                      href={`/companies/${encodeURIComponent(ticker)}`}
                      aria-current={
                        pathname === `/companies/${ticker}` ? "page" : undefined
                      }
                      className={`block rounded px-3 py-1 font-mono text-[12px] transition-colors ${
                        pathname === `/companies/${ticker}`
                          ? "bg-surface-raised font-medium text-accent"
                          : "text-muted hover:bg-surface-raised hover:text-foreground"
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
                </div>
              </div>
            )}
          </div>
        ))}
      </nav>

      <AdminAccess />
      <div className="hidden border-t border-edge px-4 py-2.5 font-mono text-[10.5px] text-faint lg:block">
        live · SEC ingestion + analyst review
      </div>
    </aside>
  );
}
