import { db } from "@/db";
import { alerts, markets } from "@/db/schema";
import { eq, and, desc, sql, SQL } from "drizzle-orm";

export interface GetAlertsParams {
  type?: string;
  acknowledged?: boolean;
  limit?: number;
}

export async function getAlerts(params: GetAlertsParams = {}) {
  const { type, acknowledged, limit = 100 } = params;

  const conditions: SQL[] = [];

  if (type && type !== "all") {
    conditions.push(eq(alerts.alertType, type));
  }
  if (acknowledged !== undefined) {
    conditions.push(eq(alerts.acknowledged, acknowledged ? 1 : 0));
  }

  const where = conditions.length > 0 ? and(...conditions) : undefined;

  const result = await db
    .select({
      id: alerts.id,
      alertType: alerts.alertType,
      severity: alerts.severity,
      marketId: alerts.marketId,
      pairId: alerts.pairId,
      title: alerts.title,
      message: alerts.message,
      data: alerts.data,
      acknowledged: alerts.acknowledged,
      triggeredAt: alerts.triggeredAt,
      marketTitle: markets.title,
    })
    .from(alerts)
    .leftJoin(markets, eq(alerts.marketId, markets.id))
    .where(where)
    .orderBy(desc(alerts.triggeredAt))
    .limit(limit);

  return result;
}

export async function getAlertTypes() {
  const result = await db
    .select({ alertType: alerts.alertType })
    .from(alerts)
    .groupBy(alerts.alertType)
    .orderBy(alerts.alertType);
  return result.map((r) => r.alertType);
}

export async function acknowledgeAlert(alertId: number) {
  await db
    .update(alerts)
    .set({ acknowledged: 1 })
    .where(eq(alerts.id, alertId));
}
