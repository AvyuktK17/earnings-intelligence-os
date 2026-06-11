"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatUSD } from "@/lib/format";

/**
 * Recharts needs concrete color strings, so structural chart colors (grid,
 * axes, tooltip) are read from the live CSS design tokens and re-read whenever
 * the OS appearance flips between light and dark. Series/ticker hues stay as
 * stable brand colors that read on either background.
 */
function readToken(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  return value || fallback;
}

function useThemeColors() {
  const [colors, setColors] = useState({
    edge: "#1f2735",
    muted: "#8b96a8",
    accent: "#e8b93e",
    surface: "#161c29",
    foreground: "#d7dde8",
  });

  useEffect(() => {
    function sync() {
      setColors({
        edge: readToken("--edge", "#1f2735"),
        muted: readToken("--muted", "#8b96a8"),
        accent: readToken("--accent", "#e8b93e"),
        surface: readToken("--surface-raised", "#161c29"),
        foreground: readToken("--foreground", "#d7dde8"),
      });
    }
    sync();
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  return colors;
}

export const SERIES_COLORS = [
  "#d99a1c", // accent (amber — readable on light or dark)
  "#3b82f6", // info
  "#10b981", // positive
  "#ef4444", // negative
  "#8b5cf6", // violet
];

export const TICKER_COLORS: Record<string, string> = {
  AMD: "#ef4444",
  AVGO: "#d99a1c",
  INTC: "#3b82f6",
  NVDA: "#10b981",
  QCOM: "#8b5cf6",
};

type ValueFormatter = (value: number) => string;

/** Multi-line trend over fiscal periods. `data` rows are keyed by `period`. */
export function TrendLineChart({
  data,
  lines,
  format = formatUSD,
  height = 220,
}: {
  data: Record<string, string | number | null>[];
  lines: { key: string; label?: string; color?: string }[];
  format?: ValueFormatter;
  height?: number;
}) {
  const theme = useThemeColors();
  const axis = { fontSize: 11, fill: theme.muted } as const;
  const tooltip = {
    backgroundColor: theme.surface,
    border: `1px solid ${theme.edge}`,
    borderRadius: 6,
    fontSize: 12,
    color: theme.foreground,
  };
  if (!data.length) {
    return (
      <div className="py-10 text-center text-[12px] text-faint">
        No data available.
      </div>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 6, right: 12, bottom: 0, left: 4 }}>
        <CartesianGrid stroke={theme.edge} strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey="period" tick={axis} tickLine={false} axisLine={{ stroke: theme.edge }} />
        <YAxis
          tick={axis}
          tickLine={false}
          axisLine={{ stroke: theme.edge }}
          width={56}
          tickFormatter={(v) => format(Number(v))}
        />
        <Tooltip
          contentStyle={tooltip}
          formatter={(value) => format(Number(value))}
        />
        {lines.map((line, index) => (
          <Line
            key={line.key}
            type="monotone"
            dataKey={line.key}
            name={line.label ?? line.key}
            stroke={line.color ?? SERIES_COLORS[index % SERIES_COLORS.length]}
            strokeWidth={1.75}
            dot={false}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Horizontal ranked bar chart across tickers for one metric. */
export function PeerBarChart({
  data,
  format = formatUSD,
  highlightTicker,
  height = 220,
}: {
  data: { ticker: string; value: number | null }[];
  format?: ValueFormatter;
  highlightTicker?: string;
  height?: number;
}) {
  const theme = useThemeColors();
  const axis = { fontSize: 11, fill: theme.muted } as const;
  const tooltip = {
    backgroundColor: theme.surface,
    border: `1px solid ${theme.edge}`,
    borderRadius: 6,
    fontSize: 12,
    color: theme.foreground,
  };
  const rows = data.filter((d) => d.value != null);
  if (!rows.length) {
    return (
      <div className="py-10 text-center text-[12px] text-faint">
        No data available for this metric.
      </div>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        layout="vertical"
        data={rows}
        margin={{ top: 4, right: 16, bottom: 0, left: 4 }}
      >
        <CartesianGrid stroke={theme.edge} strokeDasharray="2 4" horizontal={false} />
        <XAxis
          type="number"
          tick={axis}
          tickLine={false}
          axisLine={{ stroke: theme.edge }}
          tickFormatter={(v) => format(Number(v))}
        />
        <YAxis
          type="category"
          dataKey="ticker"
          tick={axis}
          tickLine={false}
          axisLine={{ stroke: theme.edge }}
          width={52}
        />
        <Tooltip
          cursor={{ fill: theme.edge, fillOpacity: 0.25 }}
          contentStyle={tooltip}
          formatter={(value) => format(Number(value))}
        />
        <Bar dataKey="value" radius={[0, 3, 3, 0]} barSize={18}>
          {rows.map((row) => (
            <Cell
              key={row.ticker}
              fill={
                highlightTicker && row.ticker === highlightTicker
                  ? theme.accent
                  : TICKER_COLORS[row.ticker] ?? theme.muted
              }
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
