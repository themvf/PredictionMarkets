import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import {
  ChevronLeft,
  ExternalLink,
  AlertTriangle,
  Target,
  BarChart3,
  Percent,
  TrendingUp,
  Activity,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  getTraderMetrics,
  getTraderCategoryPnl,
  getTraderAnomalies,
} from "@/db/queries/traders";
import { getWhaleTradesByTrader } from "@/db/queries/whales";
import { getMarketIdsByConditionIds } from "@/db/queries/markets";
import { formatCurrency, formatPrice, formatPercent, formatRelativeTime } from "@/lib/utils";
import { WatchlistStar } from "../../watchlist/watchlist-star";
import { CategoryPnlChart } from "./category-pnl-chart";

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

// ── Tier + Tag badges ────────────────────────────────────────

const TIER_COLORS: Record<string, string> = {
  whale: "bg-purple-500/15 text-purple-700 dark:text-purple-400 border-purple-500/30",
  shark: "bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/30",
  dolphin: "bg-cyan-500/15 text-cyan-700 dark:text-cyan-400 border-cyan-500/30",
  fish: "bg-gray-500/15 text-gray-700 dark:text-gray-400 border-gray-500/30",
};

function TierBadge({ tier }: { tier: string }) {
  if (!tier) return null;
  const label = tier.charAt(0).toUpperCase() + tier.slice(1);
  return (
    <Badge variant="outline" className={TIER_COLORS[tier] ?? ""}>
      {label}
    </Badge>
  );
}

const TAG_LABELS: Record<string, string> = {
  contrarian: "Contrarian",
  category_specialist: "Category Specialist",
  high_conviction: "High Conviction",
  early_mover: "Early Mover",
};

const ANOMALY_SEVERITY: Record<string, string> = {
  critical: "bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/30",
  warning: "bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30",
  info: "bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/30",
};

// ── Page ─────────────────────────────────────────────────────

// ── Live positions fetch for untracked wallets ───────────

interface LivePosition {
  title: string;
  outcome: string;
  size: number;
  curPrice: number;
  currentValue: number;
  cashPnl: number;
  percentPnl: number;
  conditionId: string;
  eventSlug: string;
}

async function fetchLivePositions(wallet: string): Promise<LivePosition[]> {
  try {
    const resp = await fetch(
      `https://data-api.polymarket.com/positions?user=${wallet}&sizeThreshold=0.1&limit=50&sortBy=CURRENT`,
      { next: { revalidate: 300 } }
    );
    if (!resp.ok) return [];
    const data = await resp.json();
    const list = Array.isArray(data) ? data : data?.data ?? data?.positions ?? [];
    return list.map((p: Record<string, unknown>) => ({
      title: String(p.title ?? p.marketTitle ?? ""),
      outcome: String(p.outcome ?? (p.outcomeIndex === 0 ? "Yes" : "No")),
      size: Number(p.size ?? 0),
      curPrice: Number(p.curPrice ?? p.price ?? 0),
      currentValue: Number(p.currentValue ?? p.current ?? 0),
      cashPnl: Number(p.cashPnl ?? 0),
      percentPnl: Number(p.percentPnl ?? 0),
      conditionId: String(p.conditionId ?? p.asset ?? ""),
      eventSlug: String(p.eventSlug ?? p.slug ?? ""),
    }));
  } catch {
    return [];
  }
}

/** Renders a market title as a link — internal page if in DB, Polymarket if not */
function MarketLink({
  title,
  marketId,
  eventSlug,
}: {
  title: string;
  marketId?: number;
  eventSlug?: string;
}) {
  if (marketId) {
    return (
      <Link href={`/markets/${marketId}`} className="hover:underline">
        {title}
      </Link>
    );
  }
  if (eventSlug) {
    return (
      <a
        href={`https://polymarket.com/event/${eventSlug}`}
        target="_blank"
        rel="noopener noreferrer"
        className="hover:underline"
      >
        {title}
        <ExternalLink className="inline ml-1 h-3 w-3 text-muted-foreground" />
      </a>
    );
  }
  return <>{title}</>;
}

// ── Page ─────────────────────────────────────────────────

export default async function TraderProfilePage({ params }: Props) {
  const { wallet } = await params;
  const trader = await getTraderByWallet(wallet);

  // Unknown wallet: show live-only profile from Polymarket API
  if (!trader) {
    const livePositions = await fetchLivePositions(wallet);
    const liveConditionIds = livePositions
      .map((p) => p.conditionId)
      .filter(Boolean);
    const liveMarketMap = await getMarketIdsByConditionIds(liveConditionIds);

    return (
      <div className="space-y-6">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/leaderboard">
            <ChevronLeft className="mr-1 h-4 w-4" />
            Back to Leaderboard
          </Link>
        </Button>

        <div className="space-y-1">
          <h1 className="text-2xl font-bold">{wallet.slice(0, 16)}...</h1>
          <Badge variant="secondary" className="text-xs">Untracked Wallet</Badge>
          <p className="text-xs text-muted-foreground font-mono">{wallet}</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Positions (Live from Polymarket)</CardTitle>
          </CardHeader>
          <CardContent>
            {livePositions.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="min-w-[200px]">Market</TableHead>
                    <TableHead>Outcome</TableHead>
                    <TableHead className="text-right">Cur Price</TableHead>
                    <TableHead className="text-right">Value</TableHead>
                    <TableHead className="text-right">P&L</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {livePositions.map((pos, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-medium">
                        <MarketLink
                          title={pos.title}
                          marketId={liveMarketMap.get(pos.conditionId)}
                          eventSlug={pos.eventSlug}
                        />
                      </TableCell>
                      <TableCell>{pos.outcome}</TableCell>
                      <TableCell className="text-right font-mono">
                        {formatPrice(pos.curPrice)}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {formatCurrency(pos.currentValue)}
                      </TableCell>
                      <TableCell
                        className={`text-right font-mono ${pos.cashPnl >= 0 ? "text-green-600" : "text-red-600"}`}
                      >
                        {formatCurrency(pos.cashPnl)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No open positions found for this wallet.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  const [positions, recentTrades, watchedIds, metrics, categoryPnl, anomalies] =
    await Promise.all([
      getLatestTraderPositions(trader.id),
      getWhaleTradesByTrader(trader.id, 20),
      getWatchlistIds(),
      getTraderMetrics(trader.id),
      getTraderCategoryPnl(trader.id),
      getTraderAnomalies(trader.id, 10),
    ]);

  // Batch lookup: conditionId → internal market ID for linking
  const allConditionIds = [
    ...positions.map((p) => p.conditionId).filter(Boolean),
    ...recentTrades.map((t) => t.conditionId).filter(Boolean),
  ] as string[];
  const marketIdMap = await getMarketIdsByConditionIds(allConditionIds);

  const name = trader.userName || wallet.slice(0, 16) + "...";
  const watched = watchedIds.has(trader.id);
  const tags = (trader.tags ?? "").split(",").filter(Boolean);

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
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl font-bold">{name}</h1>
            {trader.verifiedBadge === 1 && <span>✅</span>}
            <TierBadge tier={trader.traderTier ?? ""} />
            <WatchlistStar traderId={trader.id} watched={watched} />
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {trader.primaryCategory && (
              <Badge variant="secondary" className="text-xs">
                {trader.primaryCategory}
              </Badge>
            )}
            {tags.map((tag) => (
              <Badge key={tag} variant="outline" className="text-xs">
                {TAG_LABELS[tag] ?? tag}
              </Badge>
            ))}
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

      {/* Primary Stats */}
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

      {/* Metrics Grid */}
      {metrics && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardContent className="flex items-center gap-3 py-4">
              <Percent className="h-6 w-6 text-primary/60" />
              <div>
                <p className="text-lg font-bold">
                  {metrics.winRate != null
                    ? `${(metrics.winRate * 100).toFixed(1)}%`
                    : "—"}
                </p>
                <p className="text-xs text-muted-foreground">Win Rate</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex items-center gap-3 py-4">
              <BarChart3 className="h-6 w-6 text-primary/60" />
              <div>
                <p className="text-lg font-bold">
                  {metrics.totalTrades?.toLocaleString() ?? "—"}
                </p>
                <p className="text-xs text-muted-foreground">Total Trades</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex items-center gap-3 py-4">
              <Target className="h-6 w-6 text-primary/60" />
              <div>
                <p className="text-lg font-bold">
                  {metrics.avgTradeSize != null
                    ? formatCurrency(metrics.avgTradeSize, 0)
                    : "—"}
                </p>
                <p className="text-xs text-muted-foreground">Avg Trade Size</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="flex items-center gap-3 py-4">
              <Activity className="h-6 w-6 text-primary/60" />
              <div>
                <p className="text-lg font-bold">
                  {metrics.consistencyScore != null
                    ? `${(metrics.consistencyScore * 100).toFixed(0)}%`
                    : "—"}
                </p>
                <p className="text-xs text-muted-foreground">Consistency</p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Category P&L Chart */}
      {categoryPnl.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">
              Category P&L Breakdown
            </CardTitle>
          </CardHeader>
          <CardContent>
            <CategoryPnlChart data={categoryPnl} />
          </CardContent>
        </Card>
      )}

      {/* Anomalies */}
      {anomalies.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              <CardTitle className="text-sm font-medium">
                Detected Anomalies
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {anomalies.map((a) => (
                <div
                  key={a.id}
                  className="flex items-start justify-between gap-3 text-sm"
                >
                  <div className="flex items-start gap-2 min-w-0">
                    <Badge
                      variant="outline"
                      className={`text-xs shrink-0 ${ANOMALY_SEVERITY[a.severity ?? "info"] ?? ""}`}
                    >
                      {a.severity}
                    </Badge>
                    <div className="min-w-0">
                      <p className="font-medium">
                        {(a.anomalyType ?? "").replace(/_/g, " ")}
                      </p>
                      <p className="text-muted-foreground truncate">
                        {a.description}
                      </p>
                      {a.marketTitle && (
                        <p className="text-xs text-muted-foreground truncate">
                          {a.marketTitle}
                        </p>
                      )}
                    </div>
                  </div>
                  <span className="text-xs text-muted-foreground shrink-0">
                    {a.detectedAt ? formatRelativeTime(a.detectedAt) : "—"}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

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
                      <MarketLink
                        title={pos.marketTitle ?? ""}
                        marketId={marketIdMap.get(pos.conditionId ?? "")}
                        eventSlug={pos.eventSlug ?? ""}
                      />
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
                      <MarketLink
                        title={trade.marketTitle ?? ""}
                        marketId={marketIdMap.get(trade.conditionId ?? "")}
                        eventSlug={trade.eventSlug ?? ""}
                      />
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
