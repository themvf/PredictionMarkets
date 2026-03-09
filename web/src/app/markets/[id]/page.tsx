import { Suspense } from "react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, Users } from "lucide-react";
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
import { getMarketById } from "@/db/queries/markets";
import { getPriceHistoryWithRange } from "@/db/queries/price-snapshots";
import { PriceChart } from "@/app/charts/price-chart";
import { TimeRangeSelector } from "@/app/charts/time-range-selector";
import { formatCurrency, formatPrice, formatRelativeTime } from "@/lib/utils";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ range?: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const market = await getMarketById(parseInt(id));
  return { title: market?.title ?? "Market Not Found" };
}

// ── Price Chart Section ──────────────────────────────────

async function MarketPriceChart({
  marketId,
  searchParams,
}: {
  marketId: number;
  searchParams: Promise<{ range?: string }>;
}) {
  const { range = "7d" } = await searchParams;
  const history = await getPriceHistoryWithRange(marketId, range, 500);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">Price History</CardTitle>
          <TimeRangeSelector />
        </div>
      </CardHeader>
      <CardContent>
        {history.length > 0 ? (
          <PriceChart
            data={history}
            yesColor="#3b82f6"
            noColor="#ef4444"
          />
        ) : (
          <p className="text-sm text-muted-foreground py-8 text-center">
            No price history available for this time range.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// ── Top Holders Section (live from Polymarket API) ───────

interface PolymarketHolder {
  proxyWallet: string;
  name: string;
  amount: number;
  outcomeIndex: number;
  verified: boolean;
}

async function fetchLiveHolders(conditionId: string): Promise<PolymarketHolder[]> {
  try {
    const resp = await fetch(
      `https://data-api.polymarket.com/holders?market=${conditionId}&limit=20`,
      { next: { revalidate: 300 } } // cache 5 min
    );
    if (!resp.ok) return [];
    const data = await resp.json();

    // API returns array of { token, holders[] } per outcome
    const all: PolymarketHolder[] = [];
    for (const group of data) {
      for (const h of group.holders ?? []) {
        all.push({
          proxyWallet: h.proxyWallet,
          name: h.name || h.pseudonym || "",
          amount: h.amount ?? 0,
          outcomeIndex: h.outcomeIndex ?? 0,
          verified: h.verified ?? false,
        });
      }
    }
    return all;
  } catch {
    return [];
  }
}

async function MarketTopHolders({
  conditionId,
  yesPrice,
  noPrice,
}: {
  conditionId: string;
  yesPrice: number | null;
  noPrice: number | null;
}) {
  const holders = await fetchLiveHolders(conditionId);

  if (holders.length === 0) return null;

  // Compute value per holder and sort by value descending
  const holdersWithValue = holders
    .map((h) => {
      const price = h.outcomeIndex === 0 ? (yesPrice ?? 0) : (noPrice ?? 0);
      return { ...h, value: h.amount * price };
    })
    .sort((a, b) => b.value - a.value);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-sm font-medium">Top Holders</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Trader</TableHead>
              <TableHead>Side</TableHead>
              <TableHead className="text-right">Shares</TableHead>
              <TableHead className="text-right">Value</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {holdersWithValue.map((h, i) => (
              <TableRow key={`${h.proxyWallet}-${h.outcomeIndex}-${i}`}>
                <TableCell>
                  <Link
                    href={`/traders/${h.proxyWallet}`}
                    className="hover:underline font-medium"
                  >
                    {h.name || h.proxyWallet.slice(0, 10) + "..."}
                  </Link>
                  {h.verified && <span className="ml-1">✅</span>}
                </TableCell>
                <TableCell>
                  <Badge
                    variant="outline"
                    className={`text-xs ${h.outcomeIndex === 0 ? "border-green-500 text-green-600" : "border-red-500 text-red-600"}`}
                  >
                    {h.outcomeIndex === 0 ? "Yes" : "No"}
                  </Badge>
                </TableCell>
                <TableCell className="text-right font-mono">
                  {h.amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </TableCell>
                <TableCell className="text-right font-mono">
                  {formatCurrency(h.value, 0)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────

export default async function MarketDetailPage(props: Props) {
  const { id } = await props.params;
  const market = await getMarketById(parseInt(id));

  if (!market) {
    notFound();
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <Button variant="ghost" size="sm" asChild>
        <Link href="/markets">
          <ChevronLeft className="mr-1 h-4 w-4" />
          Back to Markets
        </Link>
      </Button>

      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="capitalize">
            {market.platform}
          </Badge>
          <Badge
            variant={market.status === "active" ? "default" : "secondary"}
          >
            {market.status}
          </Badge>
          {market.category && (
            <Badge variant="secondary">{market.category}</Badge>
          )}
          {market.subcategory && (
            <Badge variant="outline">{market.subcategory}</Badge>
          )}
        </div>
        <h1 className="text-2xl font-bold tracking-tight">{market.title}</h1>
        {market.description && (
          <p className="text-muted-foreground">{market.description}</p>
        )}
      </div>

      {/* Stats cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Yes Price
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono">
              {formatPrice(market.yesPrice)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              No Price
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono">
              {formatPrice(market.noPrice)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Volume
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono">
              {formatCurrency(market.volume, 0)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Liquidity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono">
              {formatCurrency(market.liquidity, 0)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Price Chart */}
      <Suspense
        fallback={<Skeleton className="h-[460px] w-full rounded-xl" />}
      >
        <MarketPriceChart
          marketId={market.id}
          searchParams={props.searchParams}
        />
      </Suspense>

      {/* Top Holders */}
      <Suspense
        fallback={<Skeleton className="h-[200px] w-full rounded-xl" />}
      >
        <MarketTopHolders
          conditionId={market.platformId}
          yesPrice={market.yesPrice}
          noPrice={market.noPrice}
        />
      </Suspense>

      {/* Meta info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-3 sm:grid-cols-2 text-sm">
            <div>
              <dt className="text-muted-foreground">Platform ID</dt>
              <dd className="font-mono">{market.platformId}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Last Updated</dt>
              <dd>{formatRelativeTime(market.lastUpdated)}</dd>
            </div>
            {market.closeTime && (
              <div>
                <dt className="text-muted-foreground">Close Time</dt>
                <dd>{market.closeTime}</dd>
              </div>
            )}
            {market.url && (
              <div>
                <dt className="text-muted-foreground">URL</dt>
                <dd>
                  <a
                    href={market.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    View on {market.platform}
                  </a>
                </dd>
              </div>
            )}
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
