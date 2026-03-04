import { Suspense } from "react";
import type { Metadata } from "next";
import { DollarSign, Waves, TrendingUp, AlertTriangle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { Pagination } from "@/components/shared/pagination";
import { MarketCard } from "@/components/markets/market-card";
import { getMarkets } from "@/db/queries/markets";
import {
  getCategoryStats,
  getCategorySubcategoryCounts,
  getCategoryWhaleTrades,
  getCategoryTopTraders,
  getCategoryAnomalies,
  type CategoryStats,
} from "@/db/queries/category-hub";
import { formatCompactCurrency, formatCurrency, formatRelativeTime } from "@/lib/utils";
import { FilterSelect } from "@/components/shared/filter-bar";
import { FinanceTabs } from "./finance-tabs";
import { FinanceSidebar } from "./finance-sidebar";
import { SharpMoneyCard } from "./sharp-money-card";
import { AnomalyCard } from "./anomaly-card";

export const metadata: Metadata = { title: "Finance Hub" };
export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<{
    sub?: string;
    tab?: string;
    page?: string;
    sort?: string;
  }>;
}

// ── Stats Hero ─────────────────────────────────────────────

function StatsHero({ stats }: { stats: CategoryStats }) {
  const cards = [
    {
      label: "Finance Markets",
      value: stats.totalMarkets.toLocaleString(),
      icon: DollarSign,
    },
    {
      label: "Total Volume",
      value: formatCompactCurrency(stats.totalVolume),
      icon: TrendingUp,
    },
    {
      label: "Whale Trades",
      value: stats.whaleTradeCount.toLocaleString(),
      icon: Waves,
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {cards.map((c) => (
        <Card key={c.label}>
          <CardContent className="flex items-center gap-3 py-4">
            <c.icon className="h-8 w-8 text-primary/60" />
            <div>
              <p className="text-2xl font-bold">{c.value}</p>
              <p className="text-xs text-muted-foreground">{c.label}</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ── Markets Tab ────────────────────────────────────────────

async function MarketsTab({ subcategory, page, sort }: { subcategory?: string; page: number; sort?: string }) {
  const result = await getMarkets({
    category: "Finance",
    subcategory: subcategory || undefined,
    sort: sort || "volume_desc",
    page,
  });

  if (result.data.length === 0) {
    return (
      <EmptyState
        icon={DollarSign}
        title="No Finance markets"
        description="No markets found for this subcategory."
      />
    );
  }

  return (
    <>
      <div className="flex items-end gap-4 mb-4">
        <FilterSelect
          paramKey="sort"
          label="Sort By"
          defaultValue="volume_desc"
          options={[
            { value: "volume_desc", label: "Volume (High)" },
            { value: "volume_asc", label: "Volume (Low)" },
            { value: "close_time_asc", label: "Ending Soon" },
            { value: "close_time_desc", label: "Newest" },
          ]}
        />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {result.data.map((market) => (
          <MarketCard key={market.id} market={market} />
        ))}
      </div>
      <Pagination
        page={result.page}
        totalPages={result.totalPages}
        total={result.total}
        pageSize={result.pageSize}
      />
    </>
  );
}

// ── Whale Activity Tab ─────────────────────────────────────

async function WhaleTab({ subcategory }: { subcategory?: string }) {
  const trades = await getCategoryWhaleTrades("Finance", subcategory || undefined, 50);

  if (trades.length === 0) {
    return (
      <EmptyState
        icon={Waves}
        title="No whale trades"
        description="No whale trades found in Finance markets yet."
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
          <TableHead>Subcategory</TableHead>
          <TableHead className="text-right">Size</TableHead>
          <TableHead>Time</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {trades.map((trade) => (
          <TableRow key={trade.id}>
            <TableCell>
              <span className="font-medium">
                {trade.userName || "Unknown"}
              </span>
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
              {trade.marketName || trade.marketTitle}
            </TableCell>
            <TableCell>
              {trade.subcategory && (
                <Badge variant="outline" className="text-xs">
                  {trade.subcategory}
                </Badge>
              )}
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

// ── Sharp Money Tab ────────────────────────────────────────

async function SharpMoneyTab() {
  const [topTraders, anomalies] = await Promise.all([
    getCategoryTopTraders("Finance", 20),
    getCategoryAnomalies("Finance", 10),
  ]);

  return (
    <div className="space-y-8">
      {/* Leaderboard */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">Finance Leaderboard</h3>
        {topTraders.length > 0 ? (
          topTraders.map((trader, i) => (
            <SharpMoneyCard key={trader.id} trader={trader} rank={i + 1} />
          ))
        ) : (
          <EmptyState
            icon={TrendingUp}
            title="No trader data"
            description="No whale traders found in Finance markets yet."
          />
        )}
      </div>

      {/* Anomalies */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-500" />
          <h3 className="text-lg font-semibold">Unusual Activity</h3>
        </div>
        {anomalies.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {anomalies.map((a) => (
              <AnomalyCard key={a.id} anomaly={a} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No unusual trades detected recently.
          </p>
        )}
      </div>
    </div>
  );
}

// ── Main Content ───────────────────────────────────────────

async function FinanceContent({ searchParams }: Props) {
  const params = await searchParams;
  const tab = params.tab || "markets";
  const subcategory = params.sub || "";
  const page = Math.max(1, Math.min(Number(params.page) || 1, 1000));

  let subcategoryCounts: Awaited<ReturnType<typeof getCategorySubcategoryCounts>> = [];
  let stats: CategoryStats = { totalMarkets: 0, totalVolume: 0, whaleTradeCount: 0 };
  try {
    [subcategoryCounts, stats] = await Promise.all([
      getCategorySubcategoryCounts("Finance"),
      getCategoryStats("Finance"),
    ]);
  } catch {
    // Graceful degradation — sidebar and stats show zeros
  }

  return (
    <>
      <StatsHero stats={stats} />
      <FinanceTabs />

      <div className="flex flex-col md:flex-row gap-6">
        {/* Sidebar */}
        <aside className="w-full md:w-48 shrink-0">
          <FinanceSidebar
            counts={subcategoryCounts}
            totalMarkets={stats.totalMarkets}
          />
        </aside>

        {/* Tab content */}
        <div className="flex-1 min-w-0 space-y-6">
          {tab === "markets" && (
            <MarketsTab subcategory={subcategory} page={page} sort={params.sort} />
          )}
          {tab === "whales" && <WhaleTab subcategory={subcategory} />}
          {tab === "sharp" && <SharpMoneyTab />}
        </div>
      </div>
    </>
  );
}

// ── Page Shell ─────────────────────────────────────────────

export default function FinancePage(props: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Finance Hub</h1>
        <p className="text-muted-foreground">
          Equities, earnings, indices, macro markets, and smart money tracking
        </p>
      </div>

      <Suspense
        fallback={
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full rounded-xl" />
              ))}
            </div>
            <Skeleton className="h-10 w-full" />
            <div className="flex gap-6">
              <Skeleton className="h-64 w-48 rounded-xl" />
              <div className="flex-1 space-y-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-24 w-full rounded-xl" />
                ))}
              </div>
            </div>
          </div>
        }
      >
        <FinanceContent searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}
