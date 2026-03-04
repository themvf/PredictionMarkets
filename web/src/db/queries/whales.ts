import { db } from "@/db";
import { whaleTrades, traders, traderPositions, markets } from "@/db/schema";
import { eq, desc, gte, and, sql, SQL } from "drizzle-orm";

export interface GetWhaleTradesParams {
  minSize?: number;
  side?: string;
  limit?: number;
}

export async function getWhaleTrades(params: GetWhaleTradesParams = {}) {
  const { minSize = 0, side, limit = 100 } = params;

  const conditions: SQL[] = [];
  if (minSize > 0) {
    conditions.push(gte(whaleTrades.usdcSize, minSize));
  }
  if (side && side !== "all") {
    conditions.push(eq(whaleTrades.side, side.toUpperCase()));
  }

  const where = conditions.length > 0 ? and(...conditions) : undefined;

  return db
    .select({
      id: whaleTrades.id,
      traderId: whaleTrades.traderId,
      proxyWallet: whaleTrades.proxyWallet,
      conditionId: whaleTrades.conditionId,
      marketTitle: whaleTrades.marketTitle,
      side: whaleTrades.side,
      size: whaleTrades.size,
      price: whaleTrades.price,
      usdcSize: whaleTrades.usdcSize,
      outcome: whaleTrades.outcome,
      transactionHash: whaleTrades.transactionHash,
      tradeTimestamp: whaleTrades.tradeTimestamp,
      eventSlug: whaleTrades.eventSlug,
      createdAt: whaleTrades.createdAt,
      userName: traders.userName,
      profileImage: traders.profileImage,
      verifiedBadge: traders.verifiedBadge,
    })
    .from(whaleTrades)
    .leftJoin(traders, eq(whaleTrades.traderId, traders.id))
    .where(where)
    .orderBy(desc(whaleTrades.tradeTimestamp))
    .limit(limit);
}

export async function getWhaleTradesByTrader(traderId: number, limit = 50) {
  return db
    .select()
    .from(whaleTrades)
    .where(eq(whaleTrades.traderId, traderId))
    .orderBy(desc(whaleTrades.tradeTimestamp))
    .limit(limit);
}

export interface GetFirstTimeTradesParams {
  categories?: string[];
  minSize?: number;
  limit?: number;
}

export async function getFirstTimeTrades(
  params: GetFirstTimeTradesParams = {}
) {
  const {
    categories = ["Politics", "Tech", "Finance"],
    minSize = 5000,
    limit = 100,
  } = params;

  // Whitelist categories to prevent injection — only known values pass through
  const ALLOWED_CATEGORIES = new Set([
    "Politics", "Sports", "Crypto", "Culture",
    "Weather", "Economics", "Tech", "Finance",
  ]);
  const safeCats = categories.filter((c) => ALLOWED_CATEGORIES.has(c));
  if (safeCats.length === 0) return [];

  // Build parameterized IN clause using Drizzle's sql template
  const categoryConditions = sql.join(
    safeCats.map((c) => sql`${c}`),
    sql`, `
  );

  const result = await db.execute(
    sql`
      WITH first_trades AS (
        SELECT trader_id, MIN(trade_timestamp) as first_ts
        FROM whale_trades
        GROUP BY trader_id
      )
      SELECT wt.*, t.user_name, t.profile_image, t.verified_badge,
             t.first_seen, m.category, m.title as market_name
      FROM whale_trades wt
      JOIN first_trades ft
        ON wt.trader_id = ft.trader_id
        AND wt.trade_timestamp = ft.first_ts
      LEFT JOIN traders t ON wt.trader_id = t.id
      LEFT JOIN markets m
        ON wt.condition_id = m.platform_id
        AND m.platform = 'polymarket'
      WHERE wt.usdc_size >= ${minSize}
        AND m.category IN (${categoryConditions})
      ORDER BY wt.trade_timestamp DESC
      LIMIT ${limit}
    `
  );

  return result.rows;
}

// ── Market Holders ────────────────────────────

export async function getMarketHolders(conditionId: string, limit = 20) {
  // Get the latest snapshot time for positions on this market
  const snapshotResult = await db
    .select({ t: sql<string>`MAX(${traderPositions.snapshotTime})` })
    .from(traderPositions)
    .where(eq(traderPositions.conditionId, conditionId));

  const latestTime = snapshotResult[0]?.t;
  if (!latestTime) return [];

  return db
    .select({
      id: traderPositions.id,
      traderId: traderPositions.traderId,
      proxyWallet: traderPositions.proxyWallet,
      outcome: traderPositions.outcome,
      size: traderPositions.size,
      avgPrice: traderPositions.avgPrice,
      currentValue: traderPositions.currentValue,
      cashPnl: traderPositions.cashPnl,
      userName: traders.userName,
      profileImage: traders.profileImage,
      verifiedBadge: traders.verifiedBadge,
      traderTier: traders.traderTier,
    })
    .from(traderPositions)
    .leftJoin(traders, eq(traderPositions.traderId, traders.id))
    .where(
      and(
        eq(traderPositions.conditionId, conditionId),
        eq(traderPositions.snapshotTime, latestTime)
      )
    )
    .orderBy(desc(traderPositions.currentValue))
    .limit(limit);
}
