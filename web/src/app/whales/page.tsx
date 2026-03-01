import { Suspense } from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { Waves } from "lucide-react";
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
import { getWhaleTrades } from "@/db/queries/whales";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";

export const metadata: Metadata = { title: "Whale Tracker" };
export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<{
    minSize?: string;
    side?: string;
    limit?: string;
  }>;
}

async function WhaleContent({ searchParams }: Props) {
  const params = await searchParams;
  const trades = await getWhaleTrades({
    minSize: params.minSize ? parseFloat(params.minSize) : 0,
    side: params.side,
    limit: params.limit ? parseInt(params.limit) : 100,
  });

  if (trades.length === 0) {
    return (
      <EmptyState
        icon={Waves}
        title="No whale trades"
        description="No trades match your filters. Try lowering the minimum size."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Trader</TableHead>
          <TableHead>Side</TableHead>
          <TableHead>Market</TableHead>
          <TableHead>Outcome</TableHead>
          <TableHead className="text-right">Size</TableHead>
          <TableHead>Time</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {trades.map((trade) => (
          <TableRow key={trade.id}>
            <TableCell>
              <Link
                href={`/traders/${trade.proxyWallet}`}
                className="hover:underline font-medium"
              >
                {trade.userName || trade.proxyWallet.slice(0, 10) + "..."}
              </Link>
              {trade.verifiedBadge === 1 && <span className="ml-1">✅</span>}
            </TableCell>
            <TableCell>
              <Badge
                variant={trade.side === "BUY" ? "default" : "destructive"}
              >
                {trade.side}
              </Badge>
            </TableCell>
            <TableCell className="max-w-[250px] truncate">
              {trade.marketTitle}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {trade.outcome}
            </TableCell>
            <TableCell className="text-right font-mono font-medium">
              {formatCurrency(trade.usdcSize, 0)}
            </TableCell>
            <TableCell className="text-muted-foreground text-sm">
              {trade.tradeTimestamp
                ? formatRelativeTime(
                    new Date(trade.tradeTimestamp * 1000).toISOString()
                  )
                : "—"}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export default function WhalesPage(props: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Whale Tracker</h1>
        <p className="text-muted-foreground">
          Large trades from top Polymarket traders
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <FilterSelect
          paramKey="minSize"
          label="Min Size"
          defaultValue="0"
          options={[
            { value: "0", label: "All Sizes" },
            { value: "1000", label: "$1,000+" },
            { value: "5000", label: "$5,000+" },
            { value: "10000", label: "$10,000+" },
            { value: "50000", label: "$50,000+" },
          ]}
        />
        <FilterSelect
          paramKey="side"
          label="Side"
          options={[
            { value: "all", label: "All" },
            { value: "BUY", label: "Buy" },
            { value: "SELL", label: "Sell" },
          ]}
        />
      </div>

      <Suspense
        fallback={
          <div className="space-y-2">
            {Array.from({ length: 10 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        }
      >
        <WhaleContent searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}
