"use client";

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

// Terminal palette aligned with globals.css design tokens.
const EDGE = "#1f2735";
const MUTED = "#8b96a8";
const ACCENT = "#e8b93e";

export const SERIES_COLORS = [
  "#e8b93e", // accent
  "#539bf5", // info
  "#4cc38a", // positive
  "#e5534b", // negative
  "#a371f7", // violet
];

export const TICKER_COLORS: Record<string, string> = {
  AMD: "#e5534b",
  AVGO: "#e8b93e",
  INTC: "#539bf5",
  NVDA: "#4cc38a",
  QCOM: "#a371f7",
};

const AXIS = { fontSize: 11, fill: MUTED } as const;

type ValueFormatter = (value: number) => string;

function tooltipStyle() {
  return {
    backgroundColor: "#161c29",
    border: `1px solid ${EDGE}`,
    borderRadius: 6,
    fontSize: 12,
    color: "#d7dde8",
  };
}

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
        <CartesianGrid stroke={EDGE} strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey="period" tick={AXIS} tickLine={false} axisLine={{ stroke: EDGE }} />
        <YAxis
          tick={AXIS}
          tickLine={false}
          axisLine={{ stroke: EDGE }}
          width={56}
          tickFormatter={(v) => format(Number(v))}
        />
        <Tooltip
          contentStyle={tooltipStyle()}
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
        <CartesianGrid stroke={EDGE} strokeDasharray="2 4" horizontal={false} />
        <XAxis
          type="number"
          tick={AXIS}
          tickLine={false}
          axisLine={{ stroke: EDGE }}
          tickFormatter={(v) => format(Number(v))}
        />
        <YAxis
          type="category"
          dataKey="ticker"
          tick={AXIS}
          tickLine={false}
          axisLine={{ stroke: EDGE }}
          width={52}
        />
        <Tooltip
          cursor={{ fill: "#ffffff08" }}
          contentStyle={tooltipStyle()}
          formatter={(value) => format(Number(value))}
        />
        <Bar dataKey="value" radius={[0, 3, 3, 0]} barSize={18}>
          {rows.map((row) => (
            <Cell
              key={row.ticker}
              fill={
                highlightTicker && row.ticker === highlightTicker
                  ? ACCENT
                  : TICKER_COLORS[row.ticker] ?? MUTED
              }
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
