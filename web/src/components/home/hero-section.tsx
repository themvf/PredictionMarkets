import { getDashboardStats } from "@/db/queries/dashboard";

function formatCompactNumber(value: number): string {
  return Intl.NumberFormat("en-US", { notation: "compact" }).format(value);
}

export async function HeroSection() {
  let stats = { totalMarkets: 0, totalTraders: 0, totalWhaleTrades: 0 };
  try {
    stats = await getDashboardStats();
  } catch {
    // Graceful degradation — show zeroes if DB is unreachable
  }

  return (
    <section className="py-12 text-center">
      <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
        Discover Every Prediction
      </h1>
      <p className="mt-3 text-muted-foreground text-lg max-w-xl mx-auto">
        Track markets, whale trades, and arbitrage across Polymarket &mdash;
        powered by smart money insights
      </p>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-4 text-sm">
        <span className="rounded-full bg-secondary px-4 py-1.5 font-medium">
          {stats.totalMarkets.toLocaleString()} Markets
        </span>
        <span className="rounded-full bg-secondary px-4 py-1.5 font-medium">
          {stats.totalTraders.toLocaleString()} Traders
        </span>
        <span className="rounded-full bg-secondary px-4 py-1.5 font-medium">
          {formatCompactNumber(stats.totalWhaleTrades)} Whale Trades
        </span>
      </div>
    </section>
  );
}
