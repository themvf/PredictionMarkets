import { Suspense } from "react";
import type { Metadata } from "next";
import { GitCompare } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { getAllPairs } from "@/db/queries/pairs";
import { formatPrice, formatCompactCurrency } from "@/lib/utils";

export const metadata: Metadata = { title: "Cross-Platform" };
export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<{ minGap?: string }>;
}

async function PairsContent({ searchParams }: Props) {
  const params = await searchParams;
  const minGap = params.minGap ? parseFloat(params.minGap) : undefined;
  const pairs = await getAllPairs(minGap);

  if (!pairs || pairs.length === 0) {
    return (
      <EmptyState
        icon={GitCompare}
        title="No cross-platform pairs"
        description="Run the analysis agent to find matching markets across platforms."
      />
    );
  }

  return (
    <div className="space-y-4">
      {pairs.map((pair: Record<string, unknown>) => {
        const gap = Number(pair.price_gap ?? 0);
        const absGap = Math.abs(gap);
        return (
          <Card key={String(pair.id)}>
            <CardContent className="pt-6">
              <div className="grid gap-4 md:grid-cols-[1fr_auto_1fr]">
                {/* Kalshi side */}
                <div className="space-y-1">
                  <Badge variant="outline">Kalshi</Badge>
                  <p className="font-medium text-sm">
                    {String(pair.kalshi_title ?? "Unknown")}
                  </p>
                  <div className="flex gap-4 text-sm text-muted-foreground">
                    <span>Yes: {formatPrice(Number(pair.kalshi_yes))}</span>
                    <span>
                      Vol: {formatCompactCurrency(Number(pair.kalshi_volume))}
                    </span>
                  </div>
                </div>

                {/* Gap indicator */}
                <div className="flex flex-col items-center justify-center">
                  <Badge
                    variant={absGap >= 0.05 ? "destructive" : "secondary"}
                    className="text-lg px-4 py-1"
                  >
                    {(absGap * 100).toFixed(1)}%
                  </Badge>
                  <span className="text-xs text-muted-foreground mt-1">
                    price gap
                  </span>
                </div>

                {/* Polymarket side */}
                <div className="space-y-1 md:text-right">
                  <Badge variant="outline">Polymarket</Badge>
                  <p className="font-medium text-sm">
                    {String(pair.poly_title ?? "Unknown")}
                  </p>
                  <div className="flex gap-4 text-sm text-muted-foreground md:justify-end">
                    <span>Yes: {formatPrice(Number(pair.poly_yes))}</span>
                    <span>
                      Vol: {formatCompactCurrency(Number(pair.poly_volume))}
                    </span>
                  </div>
                </div>
              </div>

              {pair.match_reason ? (
                <p className="text-xs text-muted-foreground mt-3 border-t pt-2">
                  Match: {String(pair.match_reason)} (
                  {((Number(pair.match_confidence ?? 0)) * 100).toFixed(0)}%
                  confidence)
                </p>
              ) : null}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

export default function CrossPlatformPage(props: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Cross-Platform Analysis
        </h1>
        <p className="text-muted-foreground">
          Matching markets across Polymarket and Kalshi with price gap analysis
        </p>
      </div>
      <Suspense
        fallback={
          <div className="space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-36 w-full rounded-xl" />
            ))}
          </div>
        }
      >
        <PairsContent searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}
