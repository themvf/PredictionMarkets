import { Suspense } from "react";
import type { Metadata } from "next";
import { Bot, CheckCircle2, XCircle, Clock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { getLatestRunPerAgent, getAgentLogs } from "@/db/queries/agents";
import { formatRelativeTime } from "@/lib/utils";
import { AGENTS } from "@/lib/constants";

export const metadata: Metadata = { title: "Agent Status" };
export const dynamic = "force-dynamic";

async function AgentStatusContent() {
  const [latestRuns, recentLogs] = await Promise.all([
    getLatestRunPerAgent(),
    getAgentLogs(undefined, 20),
  ]);

  const runMap = new Map(latestRuns.map((r) => [r.agentName, r]));

  return (
    <>
      {/* Agent cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {AGENTS.map((agent) => {
          const run = runMap.get(agent.name);
          const isSuccess = run?.status === "success";
          const isError = run?.status === "error";

          return (
            <Card key={agent.name}>
              <CardHeader className="flex flex-row items-center gap-3 pb-2">
                {isSuccess ? (
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                ) : isError ? (
                  <XCircle className="h-5 w-5 text-red-500" />
                ) : (
                  <Clock className="h-5 w-5 text-muted-foreground" />
                )}
                <div>
                  <CardTitle className="text-base">{agent.label}</CardTitle>
                  <p className="text-xs text-muted-foreground">
                    {agent.description}
                  </p>
                </div>
              </CardHeader>
              <CardContent>
                {run ? (
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Status</span>
                      <Badge
                        variant={isSuccess ? "default" : "destructive"}
                      >
                        {run.status}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Last Run</span>
                      <span>
                        {formatRelativeTime(run.completedAt ?? run.startedAt)}
                      </span>
                    </div>
                    {run.durationSeconds != null && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Duration</span>
                        <span>{run.durationSeconds.toFixed(1)}s</span>
                      </div>
                    )}
                    {run.itemsProcessed != null && run.itemsProcessed > 0 && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">
                          Items Processed
                        </span>
                        <span>{run.itemsProcessed}</span>
                      </div>
                    )}
                    {run.summary && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {run.summary}
                      </p>
                    )}
                    {run.error && (
                      <p className="text-xs text-red-500 mt-1">{run.error}</p>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Never run</p>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Recent activity log */}
      {recentLogs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">
              Recent Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {recentLogs.map((log) => (
                <div
                  key={log.id}
                  className="flex items-center justify-between text-sm"
                >
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        log.status === "success" ? "default" : "destructive"
                      }
                      className="text-xs"
                    >
                      {log.status}
                    </Badge>
                    <span className="capitalize">{log.agentName}</span>
                    {log.summary && (
                      <span className="text-muted-foreground truncate max-w-[300px]">
                        — {log.summary}
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {formatRelativeTime(log.completedAt ?? log.startedAt)}
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

export default function AgentsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Agent Status</h1>
        <p className="text-muted-foreground">
          Data pipeline agents and their recent activity
        </p>
      </div>
      <Suspense
        fallback={
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-48 rounded-xl" />
            ))}
          </div>
        }
      >
        <AgentStatusContent />
      </Suspense>
    </div>
  );
}
