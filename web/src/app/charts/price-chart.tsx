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
}

export function PriceChart({ data }: PriceChartProps) {
  // Reverse so oldest is first (data comes DESC from DB)
  const chartData = [...data].reverse().map((d) => ({
    time: d.timestamp ?? "",
    yes: d.yesPrice,
    no: d.noPrice,
    volume: d.volume,
  }));

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
          domain={[0, 1]}
          tickFormatter={(v: number) => `$${v.toFixed(2)}`}
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
        />
        <Legend />
        <Area
          yAxisId="vol"
          type="monotone"
          dataKey="volume"
          fill="hsl(var(--chart-3))"
          stroke="none"
          fillOpacity={0.15}
          name="Volume"
        />
        <Line
          yAxisId="price"
          type="monotone"
          dataKey="yes"
          stroke="hsl(var(--chart-1))"
          strokeWidth={2}
          dot={false}
          name="Yes Price"
        />
        <Line
          yAxisId="price"
          type="monotone"
          dataKey="no"
          stroke="hsl(var(--chart-2))"
          strokeWidth={2}
          dot={false}
          name="No Price"
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
