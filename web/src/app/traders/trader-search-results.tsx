"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatCurrency, formatCompactCurrency } from "@/lib/utils";

interface Trader {
  id: number;
  proxyWallet: string;
  userName: string | null;
  xUsername: string | null;
  verifiedBadge: number | null;
  totalPnl: number | null;
  totalVolume: number | null;
}

export function TraderSearchResults({ traders }: { traders: Trader[] }) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        {traders.length} result{traders.length !== 1 ? "s" : ""}
      </p>
      {traders.map((trader) => {
        const name =
          trader.userName || trader.proxyWallet.slice(0, 12) + "...";
        return (
          <Card key={trader.id}>
            <CardContent className="flex items-center gap-4 py-4">
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
              </div>
              <div className="text-right">
                <div className="text-sm font-medium">
                  {formatCurrency(trader.totalPnl)}
                </div>
                <div className="text-xs text-muted-foreground">
                  Vol: {formatCompactCurrency(trader.totalVolume)}
                </div>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link href={`/traders/${trader.proxyWallet}`}>Profile</Link>
              </Button>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
