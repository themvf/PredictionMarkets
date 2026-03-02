import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import type { FinanceAnomaly } from "@/db/queries/finance";

interface AnomalyCardProps {
  anomaly: FinanceAnomaly;
}

export function AnomalyCard({ anomaly }: AnomalyCardProps) {
  const name = anomaly.userName ?? "Unknown";
  const title = anomaly.marketName || anomaly.marketTitle || "Unknown market";
  const timeStr = anomaly.tradeTimestamp
    ? formatRelativeTime(new Date(anomaly.tradeTimestamp * 1000).toISOString())
    : "—";

  return (
    <Card className="border-amber-500/30 bg-amber-500/5">
      <CardContent className="py-4 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Badge
              variant={anomaly.side === "BUY" ? "default" : "destructive"}
              className="text-xs"
            >
              {anomaly.side ?? "TRADE"}
            </Badge>
            <span className="font-medium text-sm font-mono">
              {formatCurrency(anomaly.usdcSize, 0)}
            </span>
            <span className="text-xs text-amber-500 font-semibold">
              {anomaly.multiplier.toFixed(1)}x avg
            </span>
          </div>
          <span className="text-xs text-muted-foreground">{timeStr}</span>
        </div>

        <p className="text-sm truncate">{title}</p>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {anomaly.subcategory && (
            <Badge variant="outline" className="text-xs">
              {anomaly.subcategory}
            </Badge>
          )}
          <span>by {name}</span>
        </div>
      </CardContent>
    </Card>
  );
}
