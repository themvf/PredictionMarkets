import { db } from "@/db";
import { priceSnapshots } from "@/db/schema";
import { eq, desc, and, gte, type SQL } from "drizzle-orm";

export async function getPriceHistory(marketId: number, limit = 500) {
  return db
    .select()
    .from(priceSnapshots)
    .where(eq(priceSnapshots.marketId, marketId))
    .orderBy(desc(priceSnapshots.timestamp))
    .limit(limit);
}

const RANGE_HOURS: Record<string, number> = {
  "24h": 24,
  "7d": 168,
  "30d": 720,
};

/** Fetch price history with optional time range filter.
 *  Uses ISO 8601 text comparison on the indexed (marketId, timestamp) columns. */
export async function getPriceHistoryWithRange(
  marketId: number,
  range?: string,
  limit = 500
) {
  const conditions: SQL[] = [eq(priceSnapshots.marketId, marketId)];

  if (range && range !== "all") {
    const hours = RANGE_HOURS[range];
    if (hours) {
      const cutoff = new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();
      conditions.push(gte(priceSnapshots.timestamp, cutoff));
    }
  }

  return db
    .select()
    .from(priceSnapshots)
    .where(and(...conditions))
    .orderBy(desc(priceSnapshots.timestamp))
    .limit(limit);
}

export async function getLatestSnapshot(marketId: number) {
  const result = await db
    .select()
    .from(priceSnapshots)
    .where(eq(priceSnapshots.marketId, marketId))
    .orderBy(desc(priceSnapshots.timestamp))
    .limit(1);
  return result[0] ?? null;
}
