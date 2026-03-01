import { Suspense } from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { Star } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { getWatchlist } from "@/db/queries/traders";
import { formatCurrency, formatCompactCurrency, formatRelativeTime } from "@/lib/utils";
import { WatchlistStar } from "./watchlist-star";

export const metadata: Metadata = { title: "Watchlist" };
export const dynamic = "force-dynamic";

async function WatchlistContent() {
  const watchlist = await getWatchlist();

  if (watchlist.length === 0) {
    return (
      <EmptyState
        icon={Star}
        title="Your watchlist is empty"
        description="Add traders from the Leaderboard or Trader Profile pages."
      />
    );
  }

  return (
    <>
      <p className="text-sm text-muted-foreground">
        Watching {watchlist.length} trader{watchlist.length !== 1 ? "s" : ""}
      </p>
      <div className="space-y-3">
        {watchlist.map((trader) => {
          const name =
            trader.userName || trader.proxyWallet.slice(0, 12) + "...";
          return (
            <Card key={trader.id}>
              <CardContent className="flex items-center gap-4 py-4">
                {/* Name */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1">
                    <span className="font-medium truncate">{name}</span>
                    {trader.verifiedBadge === 1 && <span>✅</span>}
                  </div>
                  {trader.xUsername && (
                    <p className="text-xs text-muted-foreground">
                      @{trader.xUsername}
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground">
                    Added {formatRelativeTime(trader.watchedSince)}
                  </p>
                </div>

                {/* Stats */}
                <div className="text-right">
                  <div
                    className={`text-sm font-medium ${(trader.totalPnl ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}
                  >
                    {formatCurrency(trader.totalPnl)}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Vol: {formatCompactCurrency(trader.totalVolume)}
                  </div>
                </div>

                {/* Actions */}
                <Button variant="outline" size="sm" asChild>
                  <Link href={`/traders/${trader.proxyWallet}`}>Profile</Link>
                </Button>
                <WatchlistStar traderId={trader.id} watched={true} />
              </CardContent>
            </Card>
          );
        })}
      </div>
    </>
  );
}

export default function WatchlistPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Watchlist</h1>
        <p className="text-muted-foreground">
          Traders you&apos;re tracking. Add from the Leaderboard or Trader
          Profile pages.
        </p>
      </div>
      <Suspense
        fallback={
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full rounded-xl" />
            ))}
          </div>
        }
      >
        <WatchlistContent />
      </Suspense>
    </div>
  );
}
