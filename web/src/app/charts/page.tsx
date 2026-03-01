import { Suspense } from "react";
import type { Metadata } from "next";
import { LineChart } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { FilterSelect } from "@/components/shared/filter-bar";
import { getMarkets } from "@/db/queries/markets";
import { getPriceHistory } from "@/db/queries/price-snapshots";
import { PriceChart } from "./price-chart";

export const metadata: Metadata = { title: "Price Charts" };
export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<{
    marketId?: string;
    category?: string;
  }>;
}

async function ChartContent({ searchParams }: Props) {
  const params = await searchParams;
  const marketId = params.marketId ? parseInt(params.marketId) : null;

  // Get markets for the selector
  const { data: marketList } = await getMarkets({
    category: params.category,
    sort: "volume_desc",
    page: 1,
  });

  if (marketList.length === 0) {
    return (
      <EmptyState
        icon={LineChart}
        title="No markets available"
        description="No markets found. Run the discovery agent to populate data."
      />
    );
  }

  // Use selected market or the first market by volume
  const selectedId = marketId ?? marketList[0].id;
  const selectedMarket = marketList.find((m) => m.id === selectedId) ?? marketList[0];

  // Get price history for selected market
  const history = await getPriceHistory(selectedMarket.id, 200);

  return (
    <>
      <FilterSelect
        paramKey="marketId"
        label="Market"
        defaultValue={String(selectedMarket.id)}
        options={marketList.slice(0, 30).map((m) => ({
          value: String(m.id),
          label: m.title.length > 50 ? m.title.slice(0, 50) + "..." : m.title,
        }))}
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{selectedMarket.title}</CardTitle>
        </CardHeader>
        <CardContent>
          {history.length > 0 ? (
            <PriceChart data={history} />
          ) : (
            <p className="text-sm text-muted-foreground py-8 text-center">
              No price history available for this market.
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
