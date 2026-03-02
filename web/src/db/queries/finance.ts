/**
 * Finance Hub queries — category-specific stats, whale trades,
 * sharp money leaderboard, and anomaly detection.
 *
 * All queries JOIN whale_trades → markets via condition_id/platform_id
 * to filter by category = 'Finance'.
 */

import { db } from "@/db";
import { markets, whaleTrades, traders } from "@/db/schema";
import { eq, and, sql, desc } from "drizzle-orm";

// ── Stats ──────────────────────────────────────────────────

export interface FinanceStats {
  totalMarkets: number;
  totalVolume: number;
  whaleTradeCount: number;
}

export async function getFinanceStats(): Promise<FinanceStats> {
  const [marketStats, whaleCount] = await Promise.all([
    db
      .select({
        totalMarkets: sql<number>`count(*)`,
        totalVolume: sql<number>`coalesce(sum(${markets.volume}), 0)`,
      })
      .from(markets)
      .where(and(eq(markets.category, "Finance"), eq(markets.status, "active"))),

    db.execute(sql`
      SELECT count(*) as cnt
      FROM whale_trades wt
      JOIN markets m
        ON wt.condition_id = m.platform_id
        AND m.platform = 'polymarket'
      WHERE m.category = 'Finance'
    `),
  ]);

  return {
    totalMarkets: Number(marketStats[0]?.totalMarkets ?? 0),
    totalVolume: Number(marketStats[0]?.totalVolume ?? 0),
    whaleTradeCount: Number(
      (whaleCount.rows[0] as Record<string, unknown>)?.cnt ?? 0
    ),
  };
}

// ── Subcategory Counts ─────────────────────────────────────

export interface SubcategoryCount {
  subcategory: string;
  count: number;
}

export async function getFinanceSubcategoryCounts(): Promise<
  SubcategoryCount[]
> {
  const rows = await db
    .select({
      subcategory: markets.subcategory,
      count: sql<number>`count(*)`,
    })
    .from(markets)
    .where(
      and(
        eq(markets.category, "Finance"),
        eq(markets.status, "active"),
        sql`${markets.subcategory} IS NOT NULL AND ${markets.subcategory} != ''`
      )
    )
    .groupBy(markets.subcategory)
    .orderBy(desc(sql`count(*)`));

  return rows.map((r) => ({
    subcategory: r.subcategory ?? "",
    count: Number(r.count),
  }));
}

// ── Whale Trades (Finance) ─────────────────────────────────

export interface FinanceWhaleTrade {
  id: number;
  traderId: number | null;
  userName: string | null;
  profileImage: string | null;
  verifiedBadge: number | null;
  conditionId: string | null;
  marketTitle: string | null;
  marketName: string | null;
  subcategory: string | null;
  side: string | null;
  size: number | null;
  price: number | null;
  usdcSize: number | null;
  outcome: string | null;
  transactionHash: string | null;
  tradeTimestamp: number | null;
  eventSlug: string | null;
}

export async function getFinanceWhaleTrades(
  subcategory?: string,
  limit = 50
): Promise<FinanceWhaleTrade[]> {
  const subFilter = subcategory
    ? sql`AND m.subcategory = ${subcategory}`
    : sql``;

  const result = await db.execute(sql`
    SELECT wt.id, wt.trader_id, wt.condition_id, wt.market_title,
           wt.side, wt.size, wt.price, wt.usdc_size, wt.outcome,
           wt.transaction_hash, wt.trade_timestamp, wt.event_slug,
           t.user_name, t.profile_image, t.verified_badge,
           m.subcategory, m.title as market_name
    FROM whale_trades wt
    LEFT JOIN traders t ON wt.trader_id = t.id
    JOIN markets m
      ON wt.condition_id = m.platform_id
      AND m.platform = 'polymarket'
    WHERE m.category = 'Finance'
      ${subFilter}
    ORDER BY wt.trade_timestamp DESC
    LIMIT ${limit}
  `);

  return (result.rows as Record<string, unknown>[]).map((r) => ({
    id: Number(r.id),
    traderId: r.trader_id != null ? Number(r.trader_id) : null,
    userName: r.user_name as string | null,
    profileImage: r.profile_image as string | null,
    verifiedBadge: r.verified_badge != null ? Number(r.verified_badge) : null,
    conditionId: r.condition_id as string | null,
    marketTitle: r.market_title as string | null,
    marketName: r.market_name as string | null,
    subcategory: r.subcategory as string | null,
    side: r.side as string | null,
    size: r.size != null ? Number(r.size) : null,
    price: r.price != null ? Number(r.price) : null,
    usdcSize: r.usdc_size != null ? Number(r.usdc_size) : null,
    outcome: r.outcome as string | null,
    transactionHash: r.transaction_hash as string | null,
    tradeTimestamp: r.trade_timestamp != null ? Number(r.trade_timestamp) : null,
    eventSlug: r.event_slug as string | null,
  }));
}

// ── Top Traders (Sharp Money) ──────────────────────────────

export interface FinanceTopTrader {
  id: number;
  proxyWallet: string;
  userName: string | null;
  profileImage: string | null;
  verifiedBadge: number | null;
  totalPnl: number | null;
  financeTradeCount: number;
  financeVolume: number;
  buyVolume: number;
  sellVolume: number;
}

export async function getFinanceTopTraders(
  limit = 20
): Promise<FinanceTopTrader[]> {
  const result = await db.execute(sql`
    SELECT t.id, t.proxy_wallet, t.user_name, t.profile_image,
           t.verified_badge, t.total_pnl,
           count(wt.id)::int as finance_trade_count,
           coalesce(sum(wt.usdc_size), 0) as finance_volume,
           coalesce(sum(CASE WHEN wt.side = 'BUY' THEN wt.usdc_size ELSE 0 END), 0) as buy_volume,
           coalesce(sum(CASE WHEN wt.side = 'SELL' THEN wt.usdc_size ELSE 0 END), 0) as sell_volume
    FROM traders t
    JOIN whale_trades wt ON wt.trader_id = t.id
    JOIN markets m
      ON wt.condition_id = m.platform_id
      AND m.platform = 'polymarket'
    WHERE m.category = 'Finance'
    GROUP BY t.id
    ORDER BY sum(wt.usdc_size) DESC
    LIMIT ${limit}
  `);

  return (result.rows as Record<string, unknown>[]).map((r) => ({
    id: Number(r.id),
    proxyWallet: String(r.proxy_wallet ?? ""),
    userName: r.user_name as string | null,
    profileImage: r.profile_image as string | null,
    verifiedBadge: r.verified_badge != null ? Number(r.verified_badge) : null,
    totalPnl: r.total_pnl != null ? Number(r.total_pnl) : null,
    financeTradeCount: Number(r.finance_trade_count ?? 0),
    financeVolume: Number(r.finance_volume ?? 0),
    buyVolume: Number(r.buy_volume ?? 0),
    sellVolume: Number(r.sell_volume ?? 0),
  }));
}

// ── Anomalies (large single trades) ────────────────────────

export interface FinanceAnomaly {
  id: number;
  traderId: number | null;
  userName: string | null;
  marketTitle: string | null;
  marketName: string | null;
  subcategory: string | null;
  side: string | null;
  usdcSize: number;
  price: number | null;
  tradeTimestamp: number | null;
  avgTrade: number;
  multiplier: number;
}

export async function getFinanceAnomalies(
  limit = 10
): Promise<FinanceAnomaly[]> {
  const result = await db.execute(sql`
    WITH avg_size AS (
      SELECT NULLIF(coalesce(avg(wt.usdc_size), 0), 0) as avg_trade
      FROM whale_trades wt
      JOIN markets m
        ON wt.condition_id = m.platform_id
        AND m.platform = 'polymarket'
      WHERE m.category = 'Finance'
    )
    SELECT wt.id, wt.trader_id, wt.market_title, wt.side,
           wt.usdc_size, wt.price, wt.trade_timestamp,
           t.user_name,
           m.title as market_name, m.subcategory,
           a.avg_trade
    FROM whale_trades wt
    JOIN markets m
      ON wt.condition_id = m.platform_id
      AND m.platform = 'polymarket'
    LEFT JOIN traders t ON wt.trader_id = t.id
    CROSS JOIN avg_size a
    WHERE m.category = 'Finance'
      AND a.avg_trade IS NOT NULL
      AND wt.usdc_size >= a.avg_trade * 2
    ORDER BY wt.trade_timestamp DESC
    LIMIT ${limit}
  `);

  return (result.rows as Record<string, unknown>[]).map((r) => {
    const usdcSize = Number(r.usdc_size ?? 0);
    const avgTrade = Number(r.avg_trade ?? 1);
    return {
      id: Number(r.id),
      traderId: r.trader_id != null ? Number(r.trader_id) : null,
      userName: r.user_name as string | null,
      marketTitle: r.market_title as string | null,
      marketName: r.market_name as string | null,
      subcategory: r.subcategory as string | null,
      side: r.side as string | null,
      usdcSize,
      price: r.price != null ? Number(r.price) : null,
      tradeTimestamp: r.trade_timestamp != null ? Number(r.trade_timestamp) : null,
      avgTrade,
      multiplier: avgTrade > 0 ? usdcSize / avgTrade : 0,
    };
  });
}
