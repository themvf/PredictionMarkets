import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatCompactCurrency, formatRelativeTime } from "@/lib/utils";
import type { Market } from "@/db/schema";

interface MarketCardProps {
  market: Market;
  showPlatform?: boolean;
}

export function MarketCard({ market, showPlatform = true }: MarketCardProps) {
  const yesPercent = Math.min(100, Math.max(0, (market.yesPrice ?? 0) * 100));

  return (
    <Card className="hover:border-primary/40 transition-colors">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <Link
            href={`/markets/${market.id}`}
            className="font-medium text-sm hover:underline line-clamp-2 flex-1"
          >
            {market.title}
          </Link>
          {showPlatform && (
            <Badge variant="outline" className="capitalize shrink-0 text-xs">
              {market.platform}
            </Badge>
          )}
        </div>

        {/* Probability bar */}
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-green-400">
              Yes {yesPercent.toFixed(1)}%
            </span>
            <span className="text-red-400">
              No {(100 - yesPercent).toFixed(1)}%
            </span>
          </div>
          <div className="h-2 rounded-full bg-red-400/20 overflow-hidden">
            <div
              className="h-full rounded-full bg-green-400"
              style={{ width: `${yesPercent}%` }}
            />
          </div>
        </div>

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            {market.category && (
              <Badge variant="secondary" className="text-xs">
                {market.category}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span className="font-mono">
              {formatCompactCurrency(market.volume)}
            </span>
            {market.closeTime && (
              <span>{formatRelativeTime(market.closeTime)}</span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
