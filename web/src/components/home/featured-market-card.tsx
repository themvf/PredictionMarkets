import Link from "next/link";
import { DollarSign, TrendingUp, Zap } from "lucide-react";
import { getFeaturedMarket } from "@/db/queries/markets";
import { formatCompactCurrency, formatPrice } from "@/lib/utils";

export async function FeaturedMarketCard() {
  const market = await getFeaturedMarket();
  if (!market) return null;

  return (
    <section className="mx-auto mt-8 max-w-3xl px-4">
      <Link href={`/markets/${market.id}`} className="block">
        <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-orange-600/80 to-amber-700/80 p-6 transition-transform hover:scale-[1.01]">
          {/* Dollar icon */}
          <div className="absolute -right-4 -top-4 rounded-full bg-white/10 p-8">
            <DollarSign className="h-12 w-12 text-white/60" />
          </div>

          <div className="relative space-y-3">
            <span className="inline-block rounded bg-white/20 px-2 py-0.5 text-xs font-semibold uppercase tracking-wider text-white">
              Featured
            </span>

            <h3 className="text-xl font-bold text-white pr-16 line-clamp-2">
              {market.title}
            </h3>

            {market.description && (
              <p className="text-sm text-white/70 line-clamp-2">
                {market.description}
              </p>
            )}

            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span className="flex items-center gap-1 text-white/90">
                <TrendingUp className="h-3.5 w-3.5" />
                {formatCompactCurrency(market.volume)} Vol
              </span>
              <span className="flex items-center gap-1 text-white/90">
                <Zap className="h-3.5 w-3.5" />
                {formatPrice(market.yesPrice)} Yes
              </span>
              {market.status === "active" && (
                <span className="rounded-full bg-white/20 px-2.5 py-0.5 text-xs font-medium text-white">
                  Active Now
                </span>
              )}
              <span className="ml-auto font-medium text-white underline underline-offset-4">
                View Market &rarr;
              </span>
            </div>
          </div>
        </div>
      </Link>
    </section>
  );
}
