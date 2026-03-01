import { db } from "@/db";
import { sql } from "drizzle-orm";

export async function getAllPairs(minGap?: number) {
  const whereClause = minGap
    ? sql`WHERE ABS(mp.price_gap) >= ${minGap}`
    : sql``;

  const result = await db.execute(sql`
    SELECT mp.*,
      km.title as kalshi_title, km.yes_price as kalshi_yes,
      km.no_price as kalshi_no, km.volume as kalshi_volume,
      km.category as kalshi_category,
      pm.title as poly_title, pm.yes_price as poly_yes,
      pm.no_price as poly_no, pm.volume as poly_volume,
      pm.category as poly_category
    FROM market_pairs mp
    LEFT JOIN markets km ON mp.kalshi_market_id = km.id
    LEFT JOIN markets pm ON mp.polymarket_market_id = pm.id
    ${whereClause}
    ORDER BY ABS(mp.price_gap) DESC
  `);

  return result.rows;
}
