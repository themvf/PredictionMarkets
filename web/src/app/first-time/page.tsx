import { Suspense } from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { FilterSelect } from "@/components/shared/filter-bar";
import { EmptyState } from "@/components/shared/empty-state";
import { getFirstTimeTrades } from "@/db/queries/whales";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";

export const metadata: Metadata = { title: "First-Time Trades" };
export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<{
    categories?: string;
    minSize?: string;
    limit?: string;
  }>;
}

async function FirstTimeContent({ searchParams }: Props) {
  const params = await searchParams;
  const categories = params.categories
    ? params.categories.split(",")
    : undefined;

  const trades = await getFirstTimeTrades({
    categories,
    minSize: params.minSize ? parseFloat(params.minSize) : undefined,
    limit: params.limit ? parseInt(params.limit) : undefined,
  });

  if (!trades || trades.length === 0) {
    return (
      <EmptyState
        icon={Sparkles}
        title="No first-time trades"
        description="No new whale traders found in the selected categories."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Trader</TableHead>
          <TableHead>Category</TableHead>
          <TableHead>Market</TableHead>
          <TableHead>Side</TableHead>
          <TableHead className="text-right">Size</TableHead>
          <TableHead>Time</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {trades.map((trade: Record<string, unknown>, i: number) => (
          <TableRow key={i}>
            <TableCell>
              <Link
                href={`/traders/${String(trade.proxy_wallet)}`}
                className="hover:underline font-medium"
              >
                {String(trade.user_name || String(trade.proxy_wallet).slice(0, 10) + "...")}
              </Link>
            </TableCell>
            <TableCell>
              <Badge variant="secondary">
                {String(trade.category ?? "Unknown")}
              </Badge>
            </TableCell>
            <TableCell className="max-w-[250px] truncate">
              {String(trade.market_title ?? trade.market_name ?? "Unknown")}
            </TableCell>
            <TableCell>
              <Badge
                variant={trade.side === "BUY" ? "default" : "destructive"}
              >
                {String(trade.side)}
              </Badge>
            </TableCell>
            <TableCell className="text-right font-mono">
              {formatCurrency(Number(trade.usdc_size), 0)}
            </TableCell>
            <TableCell className="text-muted-foreground text-sm">
              {trade.trade_timestamp
                ? formatRelativeTime(
                    new Date(Number(trade.trade_timestamp) * 1000).toISOString()
                  )
                : "—"}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export default function FirstTimePage(props: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          First-Time Trades
        </h1>
        <p className="text-muted-foreground">
          New whale traders entering prediction markets for the first time
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <FilterSelect
          paramKey="categories"
          label="Categories"
          defaultValue="Politics,Tech,Finance"
          options={[
            { value: "Politics,Tech,Finance", label: "Default (Pol/Tech/Fin)" },
            { value: "Politics", label: "Politics" },
            { value: "Sports", label: "Sports" },
            { value: "Crypto", label: "Crypto" },
            { value: "Tech", label: "Tech" },
            { value: "Finance", label: "Finance" },
          ]}
        />
        <FilterSelect
          paramKey="minSize"
          label="Min Trade Size"
          defaultValue="5000"
          options={[
            { value: "1000", label: "$1,000+" },
            { value: "5000", label: "$5,000+" },
            { value: "10000", label: "$10,000+" },
            { value: "50000", label: "$50,000+" },
          ]}
        />
      </div>

      <Suspense
        fallback={
          <div className="space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        }
      >
        <FirstTimeContent searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}
