"use client";

import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import type { PriceSnapshot } from "@/db/schema";

interface PriceChartProps {
  data: PriceSnapshot[];
  yesColor?: string;
  noColor?: string;
}

export function PriceChart({ data, yesColor, noColor }: PriceChartProps) {
  // Reverse so oldest is first (data comes DESC from DB), filter out blank timestamps
  const chartData = [...data]
    .reverse()
    .filter((d) => d.timestamp)
    .map((d) => ({
      time: d.timestamp ?? "",
      yes: d.yesPrice,
      no: d.noPrice,
      volume: d.volume,
      bestBid: d.bestBid ?? undefined,
      bestAsk: d.bestAsk ?? undefined,
    }));

  const hasBidAsk = chartData.some((d) => d.bestBid != null && d.bestAsk != null);

  // Auto-scale Y axis to visible data range with padding
  const allPrices = chartData.flatMap((d) =>
    [d.yes, d.no].filter((v): v is number => v != null)
  );
  const dataMin = allPrices.length > 0 ? Math.min(...allPrices) : 0;
  const dataMax = allPrices.length > 0 ? Math.max(...allPrices) : 1;
  const padding = Math.max((dataMax - dataMin) * 0.1, 0.02);
  const yMin = Math.max(0, Math.floor((dataMin - padding) * 100) / 100);
  const yMax = Math.min(1, Math.ceil((dataMax + padding) * 100) / 100);

  return (
    <ResponsiveContainer width="100%" height={400}>
      <ComposedChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
        <XAxis
          dataKey="time"
          tickFormatter={(v: string) => {
            if (!v) return "";
            const d = new Date(v);
            return isNaN(d.getTime())
              ? v.slice(0, 10)
              : d.toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                });
          }}
          className="text-xs"
        />
        <YAxis
          yAxisId="price"
          domain={[yMin, yMax]}
          tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
          className="text-xs"
        />
        <YAxis
          yAxisId="vol"
          orientation="right"
          tickFormatter={(v: number) =>
            v >= 1_000_000
              ? `$${(v / 1_000_000).toFixed(1)}M`
              : v >= 1_000
                ? `$${(v / 1_000).toFixed(0)}K`
                : `$${v}`
          }
          className="text-xs"
          hide
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--popover))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "var(--radius)",
          }}
          labelStyle={{ color: "hsl(var(--popover-foreground))" }}
          formatter={(value: unknown, name?: string) => {
            if (name === "Bid" || name === "Bid-Ask Spread") {
              return [`${((value as number) * 100)?.toFixed(1)}%`, name];
            }
            if (name === "Volume") {
              const v = value as number;
              if (v >= 1_000_000) return [`$${(v / 1_000_000).toFixed(1)}M`, name];
              if (v >= 1_000) return [`$${(v / 1_000).toFixed(0)}K`, name];
              return [`$${v}`, name];
            }
            return [`${((value as number) * 100)?.toFixed(1)}%`, name];
          }}
        />
        <Legend />

        {/* Volume as background area */}
        <Area
          yAxisId="vol"
          type="monotone"
          dataKey="volume"
          fill="hsl(var(--chart-3))"
          stroke="none"
          fillOpacity={0.15}
          name="Volume"
        />

        {/* Bid-ask spread band: two stacked areas create a filled band between bid and ask */}
        {hasBidAsk && (
          <>
            <Area
              yAxisId="price"
              type="monotone"
              dataKey="bestBid"
              stroke="none"
              fill="transparent"
              dot={false}
              stackId="spread"
              legendType="none"
              name="Bid"
            />
            <Area
              yAxisId="price"
              type="monotone"
              dataKey="bestAsk"
              stroke="hsl(var(--chart-4))"
              strokeWidth={0.5}
              strokeDasharray="2 2"
              fill="hsl(var(--chart-4))"
              fillOpacity={0.12}
              dot={false}
              stackId="spread"
              name="Bid-Ask Spread"
            />
          </>
        )}

        {/* Yes/No price lines */}
        <Line
          yAxisId="price"
          type="monotone"
          dataKey="yes"
          stroke={yesColor ?? "hsl(var(--chart-1))"}
          strokeWidth={2}
          dot={false}
          name="Yes Price"
        />
        <Line
          yAxisId="price"
          type="monotone"
          dataKey="no"
          stroke={noColor ?? "hsl(var(--chart-2))"}
          strokeWidth={2}
          dot={false}
          name="No Price"
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
