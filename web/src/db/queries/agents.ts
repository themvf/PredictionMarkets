import { db } from "@/db";
import { agentLogs } from "@/db/schema";
import { eq, desc } from "drizzle-orm";

export async function getAgentLogs(agentName?: string, limit = 50) {
  const query = db.select().from(agentLogs);

  if (agentName && agentName !== "all") {
    return query
      .where(eq(agentLogs.agentName, agentName))
      .orderBy(desc(agentLogs.startedAt))
      .limit(limit);
  }

  return query.orderBy(desc(agentLogs.startedAt)).limit(limit);
}

export async function getLatestAgentRun(agentName: string) {
  const result = await db
    .select()
    .from(agentLogs)
    .where(eq(agentLogs.agentName, agentName))
    .orderBy(desc(agentLogs.startedAt))
    .limit(1);
  return result[0] ?? null;
}

export async function getLatestRunPerAgent() {
  // Fetch recent logs and deduplicate to latest per agent
  const recent = await db
    .select()
    .from(agentLogs)
    .orderBy(desc(agentLogs.id))
    .limit(50);

  const seen = new Set<string>();
  return recent.filter((log) => {
    if (seen.has(log.agentName)) return false;
    seen.add(log.agentName);
    return true;
  });
}
