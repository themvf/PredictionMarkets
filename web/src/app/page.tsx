import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { getMarkets } from "@/db/queries/markets";
import { getSmartFilteredMarkets } from "@/db/queries/smart-filters";
import { HeroSection } from "@/components/home/hero-section";
import { CategoryPills } from "@/components/home/category-pills";
import { SearchHero } from "@/components/home/search-hero";
import { FeaturedMarketCard } from "@/components/home/featured-market-card";
import { SmartFilterPills } from "@/components/home/smart-filter-pills";
import { CategorySidebar } from "@/components/home/category-sidebar";
import { MarketCard } from "@/components/markets/market-card";
import { Pagination } from "@/components/shared/pagination";
import { SMART_FILTERS } from "@/lib/constants";

export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<{
    category?: string;
    search?: string;
    filter?: string;
    page?: string;
    sort?: string;
  }>;
}

async function MarketGrid({
  category,
  search,
  filter,
  page,
  sort,
}: {
  category?: string;
  search?: string;
  filter?: string;
  page: number;
  sort?: string;
}) {
  // Use smart filter if one is active, otherwise regular query
  const validFilter = SMART_FILTERS.find((f) => f.key === filter);

  if (validFilter) {
    const data = await getSmartFilteredMarkets(filter!);
    const filterLabel = validFilter.label;

    if (data.length === 0) {
      return (
        <div className="flex min-h-[20vh] flex-col items-center justify-center text-muted-foreground gap-2">
          <p>No markets found for &ldquo;{filterLabel}&rdquo;.</p>
          <p className="text-xs">Try a different filter or check back later.</p>
        </div>
      );
    }

    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          {data.length} market{data.length !== 1 ? "s" : ""} &mdash;{" "}
          <span className="font-medium text-foreground">{filterLabel}</span>
        </p>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.map((market) => (
            <MarketCard key={market.id} market={market} />
          ))}
        </div>
      </div>
    );
  }

  const result = await getMarkets({
    category,
    search,
    page,
    sort: sort || "volume_desc",
    status: "active",
  });

  if (result.data.length === 0) {
    return (
      <div className="flex min-h-[20vh] items-center justify-center text-muted-foreground">
        No markets found matching your filters.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        {result.total.toLocaleString()} market
        {result.total !== 1 ? "s" : ""}
      </p>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {result.data.map((market) => (
          <MarketCard key={market.id} market={market} />
        ))}
      </div>
      {result.totalPages > 1 && (
        <Pagination
          page={result.page}
          totalPages={result.totalPages}
          total={result.total}
          pageSize={result.pageSize}
        />
      )}
    </div>
  );
}

function MarketGridSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 9 }).map((_, i) => (
        <Skeleton key={i} className="h-36 w-full rounded-xl" />
      ))}
    </div>
  );
}

export default async function HomePage({ searchParams }: Props) {
  const params = await searchParams;
  const page = Math.max(1, Math.min(Number(params.page) || 1, 1000));
  const showHero = !params.search && !params.filter;

  return (
    <div>
      {/* Hero area — hide when actively searching/filtering */}
      {showHero && (
        <>
          <Suspense fallback={<Skeleton className="mx-auto h-40 max-w-xl" />}>
            <HeroSection />
          </Suspense>
          <Suspense fallback={null}>
            <CategoryPills />
          </Suspense>
          <SearchHero />
          <Suspense
            fallback={<Skeleton className="mx-auto mt-8 h-40 max-w-3xl" />}
          >
            <FeaturedMarketCard />
          </Suspense>
        </>
      )}

      <Suspense fallback={null}>
        <SmartFilterPills />
      </Suspense>

      {/* Main content: sidebar + grid */}
      <div className="mx-auto mt-8 flex max-w-7xl gap-6 px-4 pb-12">
        <Suspense fallback={null}>
          <CategorySidebar activeCategory={params.category} />
        </Suspense>

        <div className="flex-1 min-w-0">
          <Suspense fallback={<MarketGridSkeleton />}>
            <MarketGrid
              category={params.category}
              search={params.search}
              filter={params.filter}
              page={page}
              sort={params.sort}
            />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
