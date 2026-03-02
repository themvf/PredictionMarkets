import { Suspense } from "react";
import type { Metadata } from "next";
import { LineChart } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { FilterSelect, SearchInput } from "@/components/shared/filter-bar";
import { getMarkets } from "@/db/queries/markets";
import { getPriceHistoryWithRange } from "@/db/queries/price-snapshots";
import { CATEGORIES } from "@/lib/constants";
import { PriceChart } from "./price-chart";
import { TimeRangeSelector } from "./time-range-selector";

export const metadata: Metadata = { title: "Price Charts" };
export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<{
    marketId?: string;
    category?: string;
    platform?: string;
    search?: string;
    range?: string;
  }>;
}

async function ChartContent({ searchParams }: Props) {
  const params = await searchParams;
  const rawMarketId = params.marketId ? parseInt(params.marketId, 10) : null;
  const marketId = rawMarketId !== null && !isNaN(rawMarketId) ? rawMarketId : null;
  const range = params.range || "7d";

  // Get markets for the selector, applying filters
  const { data: marketList } = await getMarkets({
    category: params.category,
    platform: params.platform,
    search: params.search,
    sort: "volume_desc",
    page: 1,
  });

  if (marketList.length === 0) {
    return (
      <EmptyState
        icon={LineChart}
        title="No markets available"
        description="No markets found matching your filters. Try adjusting the category or search."
      />
    );
  }

  // Use selected market or the first market by volume
  const selectedId = marketId ?? marketList[0].id;
  const selectedMarket =
    marketList.find((m) => m.id === selectedId) ?? marketList[0];

  // Get price history with time range filter
  const history = await getPriceHistoryWithRange(selectedMarket.id, range, 500);

  return (
    <>
      {/* Filter bar */}
      <div className="flex flex-wrap items-end gap-4">
        <FilterSelect
          paramKey="category"
          label="Category"
          options={CATEGORIES.map((c) => ({
            value: c === "All" ? "all" : c,
            label: c,
          }))}
        />
        <FilterSelect
          paramKey="platform"
          label="Platform"
          options={[
            { value: "all", label: "All Platforms" },
            { value: "polymarket", label: "Polymarket" },
            { value: "kalshi", label: "Kalshi" },
          ]}
        />
        <SearchInput placeholder="Search markets..." />
      </div>

      {/* Market selector */}
      <FilterSelect
        paramKey="marketId"
        label="Market"
        defaultValue={String(selectedMarket.id)}
        options={marketList.slice(0, 50).map((m) => ({
          value: String(m.id),
          label:
            m.title.length > 60 ? m.title.slice(0, 60) + "..." : m.title,
        }))}
      />

      {/* Time range */}
      <TimeRangeSelector />

      {/* Chart card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{selectedMarket.title}</CardTitle>
          <div className="flex gap-2">
            {selectedMarket.category && (
              <Badge variant="secondary">{selectedMarket.category}</Badge>
            )}
            {selectedMarket.subcategory && (
              <Badge variant="outline">{selectedMarket.subcategory}</Badge>
            )}
            <Badge variant="outline" className="capitalize">
              {selectedMarket.platform}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          {history.length > 0 ? (
            <PriceChart data={history} />
          ) : (
            <p className="text-sm text-muted-foreground py-8 text-center">
              No price history available for this time range.
            </p>
          )}
        </CardContent>
      </Card>
    </>
  );
}

export default function ChartsPage(props: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Price Charts</h1>
        <p className="text-muted-foreground">
          Historical price data for prediction markets
        </p>
      </div>
      <Suspense
        fallback={
          <div className="space-y-4">
            <div className="flex gap-4">
              <Skeleton className="h-10 w-[150px]" />
              <Skeleton className="h-10 w-[150px]" />
              <Skeleton className="h-10 w-[200px]" />
            </div>
            <Skeleton className="h-10 w-64" />
            <Skeleton className="h-[400px] w-full rounded-xl" />
          </div>
        }
      >
        <ChartContent searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}
