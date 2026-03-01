import { db } from "@/db";
import { traders, traderPositions, traderWatchlist } from "@/db/schema";
import { eq, desc, ilike, sql, and, isNotNull } from "drizzle-orm";
import { PAGE_SIZE } from "@/lib/constants";

export async function getTopTraders(
  orderBy: "total_pnl" | "total_volume" = "total_pnl",
  page = 1
) {
  const col = orderBy === "total_volume" ? traders.totalVolume : traders.totalPnl;
  const offset = (page - 1) * PAGE_SIZE;

  const [data, countResult] = await Promise.all([
    db
      .select()
      .from(traders)
      .where(isNotNull(col))
      .orderBy(desc(col))
      .limit(PAGE_SIZE)
      .offset(offset),
    db
      .select({ count: sql<number>`count(*)` })
      .from(traders)
      .where(isNotNull(col)),
  ]);

  return {
    data,
    total: Number(countResult[0]?.count ?? 0),
    page,
    pageSize: PAGE_SIZE,
    totalPages: Math.ceil(Number(countResult[0]?.count ?? 0) / PAGE_SIZE),
  };
}

export async function getTraderByWallet(wallet: string) {
  const result = await db
    .select()
    .from(traders)
    .where(eq(traders.proxyWallet, wallet))
    .limit(1);
  return result[0] ?? null;
}

export async function searchTraders(query: string) {
  return db
    .select()
    .from(traders)
    .where(ilike(traders.userName, `%${query}%`))
    .orderBy(desc(traders.totalPnl))
    .limit(20);
}

export async function getLatestTraderPositions(traderId: number) {
  // Get latest snapshot time for this trader
  const snapshotResult = await db
    .select({ t: sql<string>`MAX(snapshot_time)` })
    .from(traderPositions)
    .where(eq(traderPositions.traderId, traderId));

  const latestTime = snapshotResult[0]?.t;
  if (!latestTime) return [];

  return db
    .select()
    .from(traderPositions)
    .where(
      and(
        eq(traderPositions.traderId, traderId),
        eq(traderPositions.snapshotTime, latestTime)
      )
    )
    .orderBy(desc(traderPositions.currentValue));
}

// ── Watchlist ──────────────────────────────────

export async function getWatchlist() {
  return db
    .select({
      id: traders.id,
      proxyWallet: traders.proxyWallet,
      userName: traders.userName,
      profileImage: traders.profileImage,
      xUsername: traders.xUsername,
      verifiedBadge: traders.verifiedBadge,
      totalPnl: traders.totalPnl,
      totalVolume: traders.totalVolume,
      portfolioValue: traders.portfolioValue,
      watchedSince: traderWatchlist.createdAt,
    })
    .from(traderWatchlist)
    .innerJoin(traders, eq(traderWatchlist.traderId, traders.id))
    .orderBy(desc(traderWatchlist.createdAt));
}

export async function getWatchlistIds(): Promise<Set<number>> {
  const rows = await db
    .select({ traderId: traderWatchlist.traderId })
    .from(traderWatchlist);
  return new Set(rows.map((r) => r.traderId));
}

export async function addToWatchlist(traderId: number) {
  try {
    await db.insert(traderWatchlist).values({
      traderId,
      createdAt: new Date().toISOString(),
    });
    return true;
  } catch (e: unknown) {
    const msg = String(e).toLowerCase();
    if (msg.includes("unique") || msg.includes("duplicate")) {
      return false;
    }
    throw e;
  }
}

export async function removeFromWatchlist(traderId: number) {
  await db
    .delete(traderWatchlist)
    .where(eq(traderWatchlist.traderId, traderId));
}
