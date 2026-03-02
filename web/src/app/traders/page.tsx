import type { Metadata } from "next";
import { Suspense } from "react";
import { User } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { searchTraders } from "@/db/queries/traders";
import { TraderSearchForm } from "./trader-search-form";
import { TraderSearchResults } from "./trader-search-results";

export const metadata: Metadata = { title: "Trader Search" };
export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<{ q?: string; wallet?: string }>;
}

async function SearchResults({ query }: { query: string }) {
  const results = await searchTraders(query);

  if (results.length === 0) {
    return (
      <EmptyState
        icon={User}
        title="No traders found"
        description={`No traders matching "${query}" in the database.`}
      />
    );
  }

  return <TraderSearchResults traders={results} />;
}

export default async function TradersPage({ searchParams }: Props) {
  const params = await searchParams;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Trader Profile</h1>
        <p className="text-muted-foreground">
          Search by username or enter a wallet address directly
        </p>
      </div>

      <TraderSearchForm />

      {params.q && (
        <Suspense
          fallback={
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full rounded-xl" />
              ))}
            </div>
          }
        >
          <SearchResults query={params.q} />
        </Suspense>
      )}

      {!params.q && (
        <EmptyState
          icon={User}
          title="Search for a trader"
          description="Enter a username to search, or paste a wallet address (0x...) to go directly to their profile."
        />
      )}
    </div>
  );
}
