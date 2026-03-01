import { Suspense } from "react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, User, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  getTraderByWallet,
  getLatestTraderPositions,
  getWatchlistIds,
} from "@/db/queries/traders";
import { getWhaleTradesByTrader } from "@/db/queries/whales";
import { formatCurrency, formatPrice, formatPercent } from "@/lib/utils";
import { WatchlistStar } from "../../watchlist/watchlist-star";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ wallet: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { wallet } = await params;
  const trader = await getTraderByWallet(wallet);
  return {
    title: trader?.userName || `Trader ${wallet.slice(0, 10)}...`,
  };
}

export default async function TraderProfilePage({ params }: Props) {
  const { wallet } = await params;
  const trader = await getTraderByWallet(wallet);

  if (!trader) {
    notFound();
  }

  const [positions, recentTrades, watchedIds] = await Promise.all([
    getLatestTraderPositions(trader.id),
    getWhaleTradesByTrader(trader.id, 20),
    getWatchlistIds(),
  ]);

  const name = trader.userName || wallet.slice(0, 16) + "...";
  const watched = watchedIds.has(trader.id);

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <Button variant="ghost" size="sm" asChild>
        <Link href="/leaderboard">
          <ChevronLeft className="mr-1 h-4 w-4" />
          Back to Leaderboard
        </Link>
      </Button>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">{name}</h1>
            {trader.verifiedBadge === 1 && <span>✅</span>}
            <WatchlistStar traderId={trader.id} watched={watched} />
          </div>
          {trader.xUsername && (
            <a
              href={`https://x.com/${trader.xUsername}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-muted-foreground hover:underline"
            >
              @{trader.xUsername} <ExternalLink className="inline h-3 w-3" />
            </a>
          )}
          <p className="text-xs text-muted-foreground font-mono">{wallet}</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total P&L
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div
              className={`text-2xl font-bold ${(trader.totalPnl ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}
            >
              {formatCurrency(trader.totalPnl)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Volume
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCurrency(trader.totalVolume, 0)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Portfolio Value
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCurrency(trader.portfolioValue)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Positions */}
      <Card>
        <CardHeader>
          <CardTitle>Current Positions</CardTitle>
        </CardHeader>
        <CardContent>
          {positions.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="min-w-[200px]">Market</TableHead>
                  <TableHead>Outcome</TableHead>
                  <TableHead className="text-right">Avg Price</TableHead>
                  <TableHead className="text-right">Cur Price</TableHead>
                  <TableHead className="text-right">Value</TableHead>
                  <TableHead className="text-right">P&L</TableHead>
                  <TableHead className="text-right">% P&L</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {positions.map((pos) => (
                  <TableRow key={pos.id}>
                    <TableCell className="font-medium">
                      {pos.marketTitle}
                    </TableCell>
                    <TableCell>{pos.outcome}</TableCell>
                    <TableCell className="text-right font-mono">
                      {formatPrice(pos.avgPrice)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatPrice(pos.curPrice)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(pos.currentValue)}
                    </TableCell>
                    <TableCell
                      className={`text-right font-mono ${(pos.cashPnl ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}
                    >
                      {formatCurrency(pos.cashPnl)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatPercent(pos.percentPnl)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No positions found for this trader.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Recent Whale Trades */}
      {recentTrades.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Recent Large Trades</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {recentTrades.map((trade) => (
                <div
                  key={trade.id}
                  className="flex items-center justify-between text-sm"
                >
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        trade.side === "BUY" ? "default" : "destructive"
                      }
                      className="text-xs"
                    >
                      {trade.side}
                    </Badge>
                    <span className="truncate max-w-[300px]">
                      {trade.marketTitle}
                    </span>
                  </div>
                  <span className="font-mono font-medium">
                    {formatCurrency(trade.usdcSize, 0)}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
