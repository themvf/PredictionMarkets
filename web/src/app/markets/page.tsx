import { Suspense } from "react";
import type { Metadata } from "next";
import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { FilterSelect, SearchInput } from "@/components/shared/filter-bar";
import { Pagination } from "@/components/shared/pagination";
import { EmptyState } from "@/components/shared/empty-state";
import { getMarkets } from "@/db/queries/markets";
import { formatCurrency, formatPrice, formatCompactCurrency } from "@/lib/utils";
import { CATEGORIES } from "@/lib/constants";
import { Store } from "lucide-react";

export const metadata: Metadata = { title: "Markets" };
export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<{
    platform?: string;
    status?: string;
    category?: string;
    search?: string;
    sort?: string;
    page?: string;
  }>;
}

async function MarketsTable({ searchParams }: Props) {
  const params = await searchParams;
  const { data, total, page, pageSize, totalPages } = await getMarkets({
    platform: params.platform,
    status: params.status,
    category: params.category,
    search: params.search,
    sort: params.sort,
    page: params.page ? parseInt(params.page) : 1,
  });

  if (data.length === 0) {
    return (
      <EmptyState
        icon={Store}
        title="No markets found"
        description="Try adjusting your filters or search query."
      />
    );
  }

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="min-w-[250px]">Market</TableHead>
            <TableHead>Platform</TableHead>
            <TableHead>Category</TableHead>
            <TableHead className="text-right">Yes</TableHead>
            <TableHead className="text-right">No</TableHead>
            <TableHead className="text-right">Volume</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((market) => (
            <TableRow key={market.id}>
              <TableCell className="font-medium">
                <Link
                  href={`/markets/${market.id}`}
                  className="hover:underline"
                >
                  {market.title}
                </Link>
              </TableCell>
              <TableCell>
                <Badge variant="outline" className="capitalize">
                  {market.platform}
                </Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {market.category || "—"}
              </TableCell>
              <TableCell className="text-right font-mono">
                {formatPrice(market.yesPrice)}
              </TableCell>
              <TableCell className="text-right font-mono">
                {formatPrice(market.noPrice)}
              </TableCell>
              <TableCell className="text-right font-mono">
                {formatCompactCurrency(market.volume)}
              </TableCell>
              <TableCell>
                <Badge
                  variant={market.status === "active" ? "default" : "secondary"}
                >
                  {market.status}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Pagination
        page={page}
        totalPages={totalPages}
        total={total}
        pageSize={pageSize}
      />
    </>
  );
}

export default function MarketsPage(props: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Markets</h1>
        <p className="text-muted-foreground">
          Browse prediction markets from Polymarket and Kalshi
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-4">
        <FilterSelect
          paramKey="platform"
          label="Platform"
          options={[
            { value: "all", label: "All Platforms" },
            { value: "polymarket", label: "Polymarket" },
            { value: "kalshi", label: "Kalshi" },
          ]}
        />
        <FilterSelect
          paramKey="status"
          label="Status"
          defaultValue="active"
          options={[
            { value: "all", label: "All" },
            { value: "active", label: "Active" },
            { value: "resolved", label: "Resolved" },
            { value: "closed", label: "Closed" },
          ]}
        />
        <FilterSelect
          paramKey="category"
          label="Category"
          options={CATEGORIES.map((c) => ({
            value: c === "All" ? "all" : c,
            label: c,
          }))}
        />
        <FilterSelect
          paramKey="sort"
          label="Sort By"
          defaultValue="volume_desc"
          options={[
            { value: "volume_desc", label: "Volume (High)" },
            { value: "volume_asc", label: "Volume (Low)" },
            { value: "yes_price_desc", label: "Price (High)" },
            { value: "yes_price_asc", label: "Price (Low)" },
            { value: "title_asc", label: "Title (A-Z)" },
          ]}
        />
        <SearchInput placeholder="Search markets..." />
      </div>

      {/* Table */}
      <Suspense
        fallback={
          <div className="space-y-2">
            {Array.from({ length: 10 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        }
      >
        <MarketsTable searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}
