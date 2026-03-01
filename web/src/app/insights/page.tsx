import { Suspense } from "react";
import type { Metadata } from "next";
import { Brain } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { FilterSelect } from "@/components/shared/filter-bar";
import { EmptyState } from "@/components/shared/empty-state";
import { getInsights } from "@/db/queries/insights";
import { formatRelativeTime } from "@/lib/utils";

export const metadata: Metadata = { title: "AI Insights" };
export const dynamic = "force-dynamic";

interface Props {
  searchParams: Promise<{ type?: string }>;
}

async function InsightsContent({ searchParams }: Props) {
  const params = await searchParams;
  const insightsData = await getInsights(params.type);

  if (insightsData.length === 0) {
    return (
      <EmptyState
        icon={Brain}
        title="No insights yet"
        description="Run the insight agent to generate market briefings and reports."
      />
    );
  }

  return (
    <div className="space-y-4">
      {insightsData.map((insight) => (
        <Card key={insight.id}>
          <CardHeader className="flex flex-row items-start justify-between gap-4">
            <div className="space-y-1">
              <CardTitle className="text-lg">{insight.title}</CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant="secondary">{insight.reportType}</Badge>
                {insight.modelUsed && (
                  <span className="text-xs text-muted-foreground">
                    {insight.modelUsed}
                  </span>
                )}
                <span className="text-xs text-muted-foreground">
                  {insight.marketsCovered} markets covered
                </span>
              </div>
            </div>
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              {formatRelativeTime(insight.createdAt)}
            </span>
          </CardHeader>
          <CardContent>
            <div className="prose prose-sm dark:prose-invert max-w-none">
              {/* Render markdown-style content as paragraphs */}
              {insight.content?.split("\n").map((line, i) => {
                if (!line.trim()) return null;
                if (line.startsWith("# ")) {
                  return (
                    <h3 key={i} className="text-base font-semibold mt-4">
                      {line.slice(2)}
                    </h3>
                  );
                }
                if (line.startsWith("## ")) {
                  return (
                    <h4 key={i} className="text-sm font-semibold mt-3">
                      {line.slice(3)}
                    </h4>
                  );
                }
                if (line.startsWith("- ")) {
                  return (
                    <li key={i} className="text-sm text-muted-foreground ml-4">
                      {line.slice(2)}
                    </li>
                  );
                }
                return (
                  <p key={i} className="text-sm text-muted-foreground">
                    {line}
                  </p>
                );
              })}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function InsightsPage(props: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">AI Insights</h1>
        <p className="text-muted-foreground">
          LLM-generated market analysis and briefings
        </p>
      </div>

      <FilterSelect
        paramKey="type"
        label="Report Type"
        options={[
          { value: "all", label: "All Types" },
          { value: "briefing", label: "Briefing" },
          { value: "alert_analysis", label: "Alert Analysis" },
          { value: "deep_dive", label: "Deep Dive" },
        ]}
      />

      <Suspense
        fallback={
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-48 w-full rounded-xl" />
            ))}
          </div>
        }
      >
        <InsightsContent searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}
