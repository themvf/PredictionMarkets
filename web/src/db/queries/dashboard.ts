import { db } from "@/db";
import { markets, alerts, traders, agentLogs, insights, whaleTrades } from "@/db/schema";
import { eq, sql, desc, and } from "drizzle-orm";

export interface DashboardStats {
  totalMarkets: number;
  activeMarkets: number;
  totalTraders: number;
  unacknowledgedAlerts: number;
  totalWhaleTrades: number;
  latestInsight: { title: string; createdAt: string | null } | null;
  recentAgentRuns: {
    agentName: string;
    status: string;
    completedAt: string | null;
    summary: string | null;
  }[];
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const [
    marketCountResult,
    activeMarketCountResult,
    traderCountResult,
    alertCountResult,
    whaleTradeCountResult,
    latestInsightResult,
    recentAgentRunsResult,
  ] = await Promise.all([
    // Total markets
    db
      .select({ count: sql<number>`count(*)` })
      .from(markets),

    // Active markets
    db
      .select({ count: sql<number>`count(*)` })
      .from(markets)
      .where(eq(markets.status, "active")),

    // Total traders
    db
      .select({ count: sql<number>`count(*)` })
      .from(traders),

    // Unacknowledged alerts
    db
      .select({ count: sql<number>`count(*)` })
      .from(alerts)
      .where(eq(alerts.acknowledged, 0)),

    // Total whale trades
    db
      .select({ count: sql<number>`count(*)` })
      .from(whaleTrades),

    // Latest insight
    db
      .select({
        title: insights.title,
        createdAt: insights.createdAt,
      })
      .from(insights)
      .orderBy(desc(insights.id))
      .limit(1),

    // Latest run per agent (last 5 agent runs)
    db
      .select({
        agentName: agentLogs.agentName,
        status: agentLogs.status,
        completedAt: agentLogs.completedAt,
        summary: agentLogs.summary,
      })
      .from(agentLogs)
      .orderBy(desc(agentLogs.id))
      .limit(10),
  ]);

  // Deduplicate agent runs to latest per agent
  const seenAgents = new Set<string>();
  const recentAgentRuns = recentAgentRunsResult.filter((run) => {
    if (seenAgents.has(run.agentName)) return false;
    seenAgents.add(run.agentName);
    return true;
  });

  return {
    totalMarkets: Number(marketCountResult[0]?.count ?? 0),
    activeMarkets: Number(activeMarketCountResult[0]?.count ?? 0),
    totalTraders: Number(traderCountResult[0]?.count ?? 0),
    unacknowledgedAlerts: Number(alertCountResult[0]?.count ?? 0),
    totalWhaleTrades: Number(whaleTradeCountResult[0]?.count ?? 0),
    latestInsight: latestInsightResult[0] ?? null,
    recentAgentRuns,
  };
}
