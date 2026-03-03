import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { formatCompactCurrency } from "@/lib/utils";
import type { CategoryTopTrader } from "@/db/queries/category-hub";

interface SharpMoneyCardProps {
  trader: CategoryTopTrader;
  rank: number;
  categoryLabel?: string;
}

export function SharpMoneyCard({ trader, rank, categoryLabel = "Finance" }: SharpMoneyCardProps) {
  const name = trader.userName || trader.proxyWallet.slice(0, 12) + "...";
  const medal: Record<number, string> = { 1: "\u{1F947}", 2: "\u{1F948}", 3: "\u{1F949}" };
  const total = trader.buyVolume + trader.sellVolume;
  const buyPct = total > 0 ? (trader.buyVolume / total) * 100 : 50;

  return (
    <Card>
      <CardContent className="flex items-center gap-4 py-4">
        {/* Rank */}
        <span className="text-xl font-bold w-10 text-center shrink-0">
          {medal[rank] ?? `#${rank}`}
        </span>

        {/* Name & consistency */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1">
            <Link
              href={`/traders/${trader.proxyWallet}`}
              className="font-medium text-sm hover:underline truncate"
            >
              {name}
            </Link>
            {trader.verifiedBadge === 1 && <span>✅</span>}
          </div>
          <p className="text-xs text-muted-foreground">
            {trader.tradeCount} trades &middot; {formatCompactCurrency(trader.avgTradeSize)} avg
          </p>
        </div>

        {/* Buy/Sell ratio bar */}
        <div className="w-24 space-y-1 shrink-0">
          <div className="h-2 rounded-full overflow-hidden flex">
            <div
              className="bg-green-400 h-full"
              style={{ width: `${buyPct}%` }}
            />
            <div
              className="bg-red-400 h-full"
              style={{ width: `${100 - buyPct}%` }}
            />
          </div>
          <div className="flex justify-between text-[10px] text-muted-foreground">
            <span>Buy</span>
            <span>Sell</span>
          </div>
        </div>

        {/* PnL — the primary metric */}
        <div className="text-right shrink-0">
          <div className="text-sm font-medium font-mono text-green-500">
            +{formatCompactCurrency(trader.totalPnl)}
          </div>
          <div className="text-xs text-muted-foreground">PnL</div>
        </div>
      </CardContent>
    </Card>
  );
}
