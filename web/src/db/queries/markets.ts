import { db } from "@/db";
import { markets } from "@/db/schema";
import { eq, and, ilike, desc, asc, sql, SQL } from "drizzle-orm";
import { PAGE_SIZE } from "@/lib/constants";

export interface GetMarketsParams {
  platform?: string;
  status?: string;
  category?: string;
  search?: string;
  sort?: string;
  page?: number;
}

export async function getMarkets(params: GetMarketsParams = {}) {
  const {
    platform,
    status = "active",
    category,
    search,
    sort = "volume_desc",
    page = 1,
  } = params;

  const conditions: SQL[] = [];

  if (status && status !== "all") {
    conditions.push(eq(markets.status, status));
  }
  if (platform && platform !== "all") {
    conditions.push(eq(markets.platform, platform));
  }
  if (category && category !== "All" && category !== "all") {
    conditions.push(eq(markets.category, category));
  }
  if (search) {
    conditions.push(ilike(markets.title, `%${search}%`));
  }

  const where = conditions.length > 0 ? and(...conditions) : undefined;

  // Determine sort order
  let orderBy;
  switch (sort) {
    case "volume_asc":
      orderBy = asc(markets.volume);
      break;
    case "title_asc":
      orderBy = asc(markets.title);
      break;
    case "title_desc":
      orderBy = desc(markets.title);
      break;
    case "yes_price_desc":
      orderBy = desc(markets.yesPrice);
      break;
    case "yes_price_asc":
      orderBy = asc(markets.yesPrice);
      break;
    case "volume_desc":
    default:
      orderBy = desc(markets.volume);
      break;
  }

  const offset = (page - 1) * PAGE_SIZE;

  const [data, countResult] = await Promise.all([
    db
      .select()
      .from(markets)
      .where(where)
      .orderBy(orderBy)
      .limit(PAGE_SIZE)
      .offset(offset),
    db
      .select({ count: sql<number>`count(*)` })
      .from(markets)
      .where(where),
  ]);

  return {
    data,
    total: Number(countResult[0]?.count ?? 0),
    page,
    pageSize: PAGE_SIZE,
    totalPages: Math.ceil(Number(countResult[0]?.count ?? 0) / PAGE_SIZE),
  };
}

export async function getMarketById(id: number) {
  const result = await db
    .select()
    .from(markets)
    .where(eq(markets.id, id))
    .limit(1);
  return result[0] ?? null;
}

export async function searchMarkets(query: string, limit = 20) {
  return db
    .select()
    .from(markets)
    .where(and(ilike(markets.title, `%${query}%`), eq(markets.status, "active")))
    .orderBy(desc(markets.volume))
    .limit(limit);
}

export async function getMarketCategories() {
  const result = await db
    .select({ category: markets.category })
    .from(markets)
    .where(eq(markets.status, "active"))
    .groupBy(markets.category)
    .orderBy(markets.category);
  return result.map((r) => r.category).filter(Boolean) as string[];
}
