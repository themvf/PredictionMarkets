import { db } from "@/db";
import { markets } from "@/db/schema";
import { eq, and, sql, desc, gte, lte } from "drizzle-orm";
import type { Market } from "@/db/schema";

const DEFAULT_LIMIT = 50;

/** Markets most traded by whales — ranked by whale trade count */
export async function getWhaleFavoriteMarkets(
  limit = DEFAULT_LIMIT
): Promise<Market[]> {
  const rows = await db.execute(sql`
    SELECT m.*
    FROM markets m
    JOIN whale_trades wt ON wt.condition_id = m.platform_id
      AND m.platform = 'polymarket'
    WHERE m.status = 'active'
    GROUP BY m.id
    ORDER BY COUNT(wt.id) DESC
    LIMIT ${limit}
  `);
  return rows.rows as unknown as Market[];
}

/** Active markets closing within the next 24 hours */
export async function getClosingSoonMarkets(
  limit = DEFAULT_LIMIT
): Promise<Market[]> {
  try {
    const rows = await db.execute(sql`
      SELECT * FROM markets
      WHERE status = 'active'
        AND close_time IS NOT NULL
        AND close_time != ''
        AND close_time ~ '^\d{4}-\d{2}-\d{2}'
        AND close_time::timestamptz > NOW()
        AND close_time::timestamptz <= NOW() + INTERVAL '24 hours'
      ORDER BY close_time::timestamptz ASC
      LIMIT ${limit}
    `);
    return rows.rows as unknown as Market[];
  } catch {
    return [];
  }
}

/** Markets with yes_price between 0.45 and 0.55 — most uncertain */
export async function getNear5050Markets(
  limit = DEFAULT_LIMIT
): Promise<Market[]> {
  return db
    .select()
    .from(markets)
    .where(
      and(
        eq(markets.status, "active"),
        gte(markets.yesPrice, 0.45),
        lte(markets.yesPrice, 0.55)
      )
    )
    .orderBy(desc(markets.volume))
    .limit(limit);
}

/** Markets with highest cross-platform arbitrage gaps */
export async function getHighArbMarkets(
  limit = DEFAULT_LIMIT
): Promise<Market[]> {
  const rows = await db.execute(sql`
    SELECT DISTINCT m.*
    FROM market_pairs mp
    JOIN markets m
      ON m.id = mp.polymarket_market_id OR m.id = mp.kalshi_market_id
    WHERE ABS(COALESCE(mp.price_gap, 0)) >= 0.03
      AND m.status = 'active'
    ORDER BY m.volume DESC NULLS LAST
    LIMIT ${limit}
  `);
  return rows.rows as unknown as Market[];
}

/** Markets with biggest price movement in the last 24 hours */
export async function getHottestMarkets(
  limit = DEFAULT_LIMIT
): Promise<Market[]> {
  try {
    const rows = await db.execute(sql`
      WITH latest AS (
        SELECT DISTINCT ON (market_id)
          market_id, yes_price AS current_price
        FROM price_snapshots
        WHERE timestamp IS NOT NULL AND timestamp != ''
        ORDER BY market_id, timestamp::timestamptz DESC
      ),
      day_ago AS (
        SELECT DISTINCT ON (market_id)
          market_id, yes_price AS old_price
        FROM price_snapshots
        WHERE timestamp IS NOT NULL AND timestamp != ''
          AND timestamp::timestamptz <= NOW() - INTERVAL '24 hours'
        ORDER BY market_id, timestamp::timestamptz DESC
      )
      SELECT m.*
      FROM markets m
      JOIN latest l ON l.market_id = m.id
      JOIN day_ago d ON d.market_id = m.id
      WHERE m.status = 'active'
      ORDER BY ABS(COALESCE(l.current_price, 0) - COALESCE(d.old_price, 0)) DESC
      LIMIT ${limit}
    `);
    return rows.rows as unknown as Market[];
  } catch {
    return [];
  }
}

/** Dispatch to the appropriate smart filter function */
export async function getSmartFilteredMarkets(
  filterKey: string,
  limit = DEFAULT_LIMIT
): Promise<Market[]> {
  switch (filterKey) {
    case "whale_favorites":
      return getWhaleFavoriteMarkets(limit);
    case "closing_soon":
      return getClosingSoonMarkets(limit);
    case "near_5050":
      return getNear5050Markets(limit);
    case "high_arb":
      return getHighArbMarkets(limit);
    case "hottest_24h":
      return getHottestMarkets(limit);
    default:
      return [];
  }
}
