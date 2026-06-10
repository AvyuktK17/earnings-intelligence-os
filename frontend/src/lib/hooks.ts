"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import {
  api,
  getAdminToken,
  subscribeAdminToken,
  type Company,
} from "@/lib/api";

// Fallback only if GET /companies fails; the live list comes from the API.
export const FALLBACK_TICKERS = ["AMD", "AVGO", "INTC", "NVDA", "QCOM"];

/** Reactive admin token from session storage (SSR-safe). */
export function useAdminToken(): string | null {
  return useSyncExternalStore(
    subscribeAdminToken,
    () => getAdminToken(),
    () => null,
  );
}

/**
 * Loads the watchlist tickers once. Returns `null` while loading and the
 * static fallback if the endpoint is unavailable, so navigation never breaks.
 */
export function useCompanyTickers(): string[] | null {
  const [tickers, setTickers] = useState<string[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    api
      .getCompanies()
      .then((r) => {
        if (!cancelled) setTickers(r.companies.map((c) => c.ticker));
      })
      .catch(() => {
        if (!cancelled) setTickers(FALLBACK_TICKERS);
      });
    return () => {
      cancelled = true;
    };
  }, []);
  return tickers;
}

/** Loads full company rows (for filter dropdowns). Empty array on failure. */
export function useCompanies(): Company[] {
  const [companies, setCompanies] = useState<Company[]>([]);
  useEffect(() => {
    let cancelled = false;
    api
      .getCompanies()
      .then((r) => {
        if (!cancelled) setCompanies(r.companies);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  return companies;
}
