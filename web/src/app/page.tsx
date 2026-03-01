import { Suspense } from "react";
import {
  Store,
  Bell,
  Users,
  Waves,
  Brain,
  Bot,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { getDashboardStats } from "@/db/queries/dashboard";
import { formatRelativeTime } from "@/lib/utils";

export const dynamic = "force-dynamic";

function StatCard({
  title,
  value,
  icon: Icon,
  subtitle,
}: {
  title: string;
  value: string | number;
  icon: React.ElementType;
  subtitle?: string;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {subtitle && (
          <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
        )}
      </CardContent>
    </Card>
  );
}

async function DashboardContent() {
  const stats = await getDashboardStats();

  return (
    <>
      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Markets"
          value={stats.totalMarkets.toLocaleString()}
          icon={Store}
          subtitle={`${stats.activeMarkets.toLocaleString()} active`}
        />
        <StatCard
          title="Active Alerts"
          value={stats.unacknowledgedAlerts}
          icon={Bell}
        />
        <StatCard
          title="Traders Tracked"
          value={stats.totalTraders.toLocaleString()}
          icon={Users}
        />
        <StatCard
          title="Whale Trades"
          value={stats.totalWhaleTrades.toLocaleString()}
          icon={Waves}
        />
      </div>

      {/* Latest Insight */}
      {stats.latestInsight && (
        <Card>
          <CardHeader className="flex flex-row items-center gap-2 pb-2">
            <Brain className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-sm font-medium">
              Latest AI Insight
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="font-medium">{stats.latestInsight.title}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {formatRelativeTime(stats.latestInsight.createdAt)}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Agent Status */}
      {stats.recentAgentRuns.length > 0 && (
        <Card>
          <CardHeader className="flex flex-row items-center gap-2 pb-2">
            <Bot className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-sm font-medium">
              Recent Agent Runs
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {stats.recentAgentRuns.map((run) => (
                <div
                  key={run.agentName}
                  className="flex items-center justify-between"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium capitalize">
                      {run.agentName}
                    </span>
                    <Badge
                      variant={
                        run.status === "success" ? "default" : "destructive"
                      }
                      className="text-xs"
                    >
                      {run.status}
                    </Badge>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {formatRelativeTime(run.completedAt)}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </>
  );
}

function DashboardSkeleton() {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <Skeleton className="h-4 w-24" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader className="pb-2">
          <Skeleton className="h-4 w-32" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3 mt-2" />
        </CardContent>
      </Card>
    </>
  );
}

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Prediction market analytics overview
        </p>
      </div>
      <Suspense fallback={<DashboardSkeleton />}>
        <DashboardContent />
      </Suspense>
    </div>
  );
}
