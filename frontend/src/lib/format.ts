/**
 * Deterministic display formatting for the quantitative research terminal.
 * All formatters are null-safe: a missing value renders as an em dash rather
 * than a fabricated number.
 */

const DASH = "—";

/** Compact USD, e.g. 14_916_000_000 -> "$14.92B". */
export function formatUSD(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return DASH;
  const sign = value < 0 ? "-" : "";
  const abs = Math.abs(value);
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(1)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

/** Ratio (0.56) -> "56.0%". Pass already-percent values with fromRatio=false. */
export function formatPercent(
  value: number | null | undefined,
  fromRatio = true,
): string {
  if (value == null || Number.isNaN(value)) return DASH;
  const pct = fromRatio ? value * 100 : value;
  return `${pct.toFixed(1)}%`;
}

/** Valuation multiple, e.g. 31.84 -> "31.8×". */
export function formatMultiple(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return DASH;
  return `${value.toFixed(1)}×`;
}

/** Plain dollar amount with two decimals, e.g. share price or EPS. */
export function formatPrice(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return DASH;
  return `$${value.toFixed(2)}`;
}

/** Pick the right formatter for a known operating metric name. */
export function formatMetricValue(
  metricName: string,
  value: number | null | undefined,
): string {
  if (value == null || Number.isNaN(value as number)) return DASH;
  if (metricName === "Diluted EPS") return formatPrice(value);
  if (
    metricName.includes("Margin") ||
    metricName.includes("% of Revenue") ||
    metricName.includes("Growth") ||
    metricName.includes("Yield")
  ) {
    return formatPercent(value);
  }
  return formatUSD(value);
}

/**
 * Merge per-metric point arrays into a single recharts-ready row array keyed
 * by fiscal period, preserving chronological order.
 */
export function mergeSeriesByPeriod(
  series: { name: string; points: { period: string; value: number | null }[] }[],
): Record<string, string | number | null>[] {
  const byPeriod = new Map<string, Record<string, string | number | null>>();
  const order: string[] = [];
  for (const s of series) {
    for (const point of s.points) {
      if (!byPeriod.has(point.period)) {
        byPeriod.set(point.period, { period: point.period });
        order.push(point.period);
      }
      byPeriod.get(point.period)![s.name] = point.value;
    }
  }
  return order.map((period) => byPeriod.get(period)!);
}
