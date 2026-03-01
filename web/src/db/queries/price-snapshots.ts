import { db } from "@/db";
import { priceSnapshots } from "@/db/schema";
import { eq, desc } from "drizzle-orm";

export async function getPriceHistory(marketId: number, limit = 500) {
  return db
    .select()
    .from(priceSnapshots)
    .where(eq(priceSnapshots.marketId, marketId))
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
