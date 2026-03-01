import { Suspense } from "react";
import type { Metadata } from "next";
import { Bell } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { FilterSelect } from "@/components/shared/filter-bar";
import { EmptyState } from "@/components/shared/empty-state";
import { getAlerts } from "@/db/queries/alerts";
import { formatRelativeTime } from "@/lib/utils";
import { SEVERITY_COLORS } from "@/lib/constants";
import { AcknowledgeButton } from "./acknowledge-button";

export const metadata: Metadata = { title: "Alerts" };
export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<{
    type?: string;
    status?: string;
    limit?: string;
  }>;
}

async function AlertsList({ searchParams }: Props) {
  const params = await searchParams;
  const acknowledged =
    params.status === "acknowledged"
      ? true
      : params.status === "active"
        ? false
        : undefined;

  const alertsData = await getAlerts({
    type: params.type,
    acknowledged,
    limit: params.limit ? parseInt(params.limit) : 100,
  });

  if (alertsData.length === 0) {
    return (
      <EmptyState
        icon={Bell}
        title="No alerts"
        description="No alerts match your current filters."
      />
    );
  }

  return (
    <div className="space-y-3">
      {alertsData.map((alert) => (
        <Card key={alert.id}>
          <CardHeader className="flex flex-row items-start justify-between gap-4 pb-2">
            <div className="flex items-center gap-2">
              <Badge
                variant="outline"
                className={SEVERITY_COLORS[alert.severity ?? "info"] ?? ""}
              >
                {alert.severity}
              </Badge>
              <Badge variant="secondary">{alert.alertType}</Badge>
              {alert.acknowledged === 1 && (
                <Badge variant="outline" className="text-muted-foreground">
                  Acknowledged
                </Badge>
              )}
            </div>
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              {formatRelativeTime(alert.triggeredAt)}
            </span>
          </CardHeader>
          <CardContent className="space-y-2">
            <h3 className="font-medium">{alert.title}</h3>
            {alert.message && (
              <p className="text-sm text-muted-foreground">{alert.message}</p>
            )}
            {alert.marketTitle && (
              <p className="text-xs text-muted-foreground">
                Market: {alert.marketTitle}
              </p>
            )}
            {alert.acknowledged === 0 && (
              <AcknowledgeButton alertId={alert.id} />
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function AlertsPage(props: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Alerts</h1>
        <p className="text-muted-foreground">
          Price moves, arbitrage opportunities, and system alerts
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <FilterSelect
          paramKey="type"
          label="Alert Type"
          options={[
            { value: "all", label: "All Types" },
            { value: "price_move", label: "Price Move" },
            { value: "arbitrage", label: "Arbitrage" },
            { value: "volume_spike", label: "Volume Spike" },
            { value: "new_market", label: "New Market" },
          ]}
        />
        <FilterSelect
          paramKey="status"
          label="Status"
          options={[
            { value: "all", label: "All" },
            { value: "active", label: "Active" },
            { value: "acknowledged", label: "Acknowledged" },
          ]}
        />
      </div>

      <Suspense
        fallback={
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-32 w-full rounded-xl" />
            ))}
          </div>
        }
      >
        <AlertsList searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}
