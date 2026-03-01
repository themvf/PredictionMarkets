import { db } from "@/db";
import { insights } from "@/db/schema";
import { eq, desc } from "drizzle-orm";

export async function getInsights(reportType?: string, limit = 20) {
  const query = db.select().from(insights);

  if (reportType && reportType !== "all") {
    return query
      .where(eq(insights.reportType, reportType))
      .orderBy(desc(insights.createdAt))
      .limit(limit);
  }

  return query.orderBy(desc(insights.createdAt)).limit(limit);
}
