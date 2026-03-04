"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
} from "recharts";
import type { TraderCategoryPnl } from "@/db/schema";

interface CategoryPnlChartProps {
  data: TraderCategoryPnl[];
}

export function CategoryPnlChart({ data }: CategoryPnlChartProps) {
  const chartData = data
    .filter((d) => d.volume && d.volume > 0)
    .map((d) => ({
      category: d.category,
      pnl: d.pnl ?? 0,
      volume: d.volume ?? 0,
      trades: d.tradeCount ?? 0,
    }));

  if (chartData.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={chartData} layout="vertical" margin={{ left: 60 }}>
        <XAxis
          type="number"
          tickFormatter={(v: number) =>
            v >= 1000 ? `$${(v / 1000).toFixed(0)}K` : `$${v.toFixed(0)}`
          }
          className="text-xs"
        />
        <YAxis
          type="category"
          dataKey="category"
          className="text-xs"
          width={70}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--popover))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "var(--radius)",
          }}
          formatter={(value: unknown, name?: string) => {
            const v = value as number;
            if (name === "P&L") {
              const prefix = v >= 0 ? "+" : "";
              return [`${prefix}$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, name];
            }
            return [`$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, name];
          }}
        />
        <Bar dataKey="pnl" name="P&L" radius={[0, 4, 4, 0]}>
          {chartData.map((entry, i) => (
            <Cell
              key={i}
              fill={entry.pnl >= 0 ? "hsl(var(--chart-1))" : "hsl(var(--chart-2))"}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
