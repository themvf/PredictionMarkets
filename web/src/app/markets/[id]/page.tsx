import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getMarketById } from "@/db/queries/markets";
import { formatCurrency, formatPrice, formatRelativeTime } from "@/lib/utils";

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const market = await getMarketById(parseInt(id));
  return { title: market?.title ?? "Market Not Found" };
}

export default async function MarketDetailPage({ params }: Props) {
  const { id } = await params;
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
