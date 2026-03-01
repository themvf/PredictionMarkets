import { Suspense } from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { Trophy } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { Pagination } from "@/components/shared/pagination";
import { FilterSelect, SearchInput } from "@/components/shared/filter-bar";
import { getTopTraders, searchTraders, getWatchlistIds } from "@/db/queries/traders";
import { formatCurrency, formatCompactCurrency } from "@/lib/utils";
import { WatchlistStar } from "../watchlist/watchlist-star";

export const metadata: Metadata = { title: "Leaderboard" };
export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<{
    sort?: string;
    page?: string;
    search?: string;
  }>;
}

async function LeaderboardContent({ searchParams }: Props) {
  const params = await searchParams;

  // Handle search mode
  if (params.search) {
    const results = await searchTraders(params.search);
    if (results.length === 0) {
      return (
        <EmptyState
          icon={Trophy}
          title="No traders found"
          description={`No traders matching "${params.search}".`}
        />
      );
    }
    return (
      <div className="space-y-3">
        {results.map((trader) => (
          <TraderCard key={trader.id} trader={trader} rank={null} watched={false} />
        ))}
      </div>
    );
  }

  const orderBy =
    params.sort === "volume" ? "total_volume" as const : "total_pnl" as const;
  const page = params.page ? parseInt(params.page) : 1;

  const [result, watchedIds] = await Promise.all([
    getTopTraders(orderBy, page),
    getWatchlistIds(),
  ]);

  if (result.data.length === 0) {
    return (
      <EmptyState
        icon={Trophy}
        title="No traders tracked"
        description="Run the trader agent or fetch the leaderboard to populate data."
      />
    );
  }

  return (
    <>
      <div className="space-y-3">
        {result.data.map((trader, i) => {
          const rank = (result.page - 1) * result.pageSize + i + 1;
          return (
            <TraderCard
              key={trader.id}
              trader={trader}
              rank={rank}
              watched={watchedIds.has(trader.id)}
            />
          );
        })}
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

function TraderCard({
  trader,
  rank,
  watched,
}: {
  trader: {
    id: number;
    proxyWallet: string;
    userName: string | null;
    xUsername: string | null;
    verifiedBadge: number | null;
    totalPnl: number | null;
    totalVolume: number | null;
  };
  rank: number | null;
  watched: boolean;
}) {
  const medal: Record<number, string> = { 1: "\u{1F947}", 2: "\u{1F948}", 3: "\u{1F949}" };
  const name = trader.userName || trader.proxyWallet.slice(0, 12) + "...";

  return (
    <Card>
      <CardContent className="flex items-center gap-4 py-4">
        {/* Rank */}
        {rank !== null && (
          <span className="text-xl font-bold w-10 text-center">
            {medal[rank] ?? `#${rank}`}
          </span>
        )}

        {/* Name */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1">
            <span className="font-medium truncate">{name}</span>
            {trader.verifiedBadge === 1 && (
              <span title="Verified">✅</span>
            )}
          </div>
          {trader.xUsername && (
            <p className="text-xs text-muted-foreground">@{trader.xUsername}</p>
          )}
        </div>

        {/* Stats */}
        <div className="text-right">
          <div className="text-sm font-medium">
            {formatCurrency(trader.totalPnl)}
          </div>
          <div className="text-xs text-muted-foreground">
            Vol: {formatCompactCurrency(trader.totalVolume)}
          </div>
        </div>

        {/* Watchlist star */}
        <WatchlistStar traderId={trader.id} watched={watched} />

        {/* Profile link */}
        <Button variant="outline" size="sm" asChild>
          <Link href={`/traders/${trader.proxyWallet}`}>Profile</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

export default function LeaderboardPage(props: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Leaderboard</h1>
        <p className="text-muted-foreground">
          Top Polymarket traders ranked by profit/loss and trading volume
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <FilterSelect
          paramKey="sort"
          label="Sort By"
          defaultValue="pnl"
          options={[
            { value: "pnl", label: "P&L" },
            { value: "volume", label: "Volume" },
          ]}
        />
        <SearchInput paramKey="search" placeholder="Search traders..." />
      </div>

      <Suspense
        fallback={
          <div className="space-y-3">
            {Array.from({ length: 10 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full rounded-xl" />
            ))}
          </div>
        }
      >
        <LeaderboardContent searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}
