import { useGetDashboard } from "@workspace/api-client-react";
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, ResponsiveContainer, PieChart, Pie, Cell as PieCell } from "recharts";
import { Calendar, ChevronRight, Database, GitMerge, HardDrive, Network, Sparkles } from "lucide-react";
import { StatusBadge } from "@/components/badges";
import { Link } from "wouter";
import { PageShell, HeroBanner, StatCard, SurfaceCard, EmptyState } from "@/components/page-shell";

const CHART_COLORS = ["#3b82f6", "#06b6d4", "#8b5cf6", "#f59e0b", "#10b981", "#ef4444", "#ec4899", "#14b8a6"];

const ENTITY_LABELS: Record<string, string> = {
  person: "People",
  project: "Projects",
  decision: "Decisions",
  task: "Tasks",
  topic: "Topics",
  risk: "Risks",
  blocker: "Blockers",
  document: "Documents",
  question: "Questions",
  deadline: "Deadlines",
  meeting: "Meetings",
};

function formatEntityType(type: string): string {
  return ENTITY_LABELS[type] || type.charAt(0).toUpperCase() + type.slice(1);
}

export default function Dashboard() {
  const { data, isLoading } = useGetDashboard();

  if (isLoading) {
    return (
      <PageShell className="space-y-6">
        <Skeleton className="h-28 w-full rounded-xl" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      </PageShell>
    );
  }

  if (!data) return null;

  const entityData = Object.entries(data.memory_stats.entity_breakdown || {})
    .map(([name, value]) => ({ name, value, label: formatEntityType(name) }))
    .sort((a, b) => b.value - a.value);

  const totalEntities = entityData.reduce((sum, e) => sum + e.value, 0);
  const recentMeetings = data.recent_meetings.slice(0, 5);

  return (
    <PageShell className="space-y-8">
      <HeroBanner
        eyebrow="Mission Control"
        eyebrowIcon={Sparkles}
        title="Your organizational memory at a glance"
        description="Track meetings, entities, and decisions indexed into your knowledge graph."
        pills={
          <>
            <span className="inline-flex items-center gap-1.5 text-xs font-mono px-3 py-1.5 rounded-lg border border-border/50 bg-background/40 text-muted-foreground">
              <HardDrive className="w-3.5 h-3.5 text-primary" />
              {(data.memory_stats.memory_size_mb || 0).toFixed(2)} MB
            </span>
            <span className="inline-flex items-center gap-1.5 text-xs font-mono px-3 py-1.5 rounded-lg border border-border/50 bg-background/40 text-muted-foreground">
              <Calendar className="w-3.5 h-3.5 text-cyan-400" />
              {data.memory_stats.last_updated
                ? new Date(data.memory_stats.last_updated).toLocaleDateString()
                : "Not synced"}
            </span>
          </>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        <StatCard
          title="Total Meetings"
          value={data.memory_stats.total_meetings}
          icon={Calendar}
          accent="primary"
        />
        <StatCard
          title="Entities Tracked"
          value={data.memory_stats.total_entities}
          icon={Database}
          accent="cyan"
        />
        <StatCard
          title="Relationships"
          value={data.memory_stats.total_relationships}
          icon={Network}
          accent="blue"
        />
        <StatCard
          title="Decisions Made"
          value={data.memory_stats.total_decisions}
          icon={GitMerge}
          accent="amber"
        />
      </div>

      {/* Content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <SurfaceCard className="lg:col-span-3">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">Recent Meetings</CardTitle>
                <CardDescription className="mt-1">Latest indexed transcripts</CardDescription>
              </div>
              <Link
                href="/meetings"
                className="text-xs font-medium text-primary hover:text-primary/80 flex items-center gap-1"
              >
                View all
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </CardHeader>
          <CardContent>
            {recentMeetings.length > 0 ? (
              <div className="space-y-2">
                {recentMeetings.map((meeting) => (
                  <Link key={meeting.id} href={`/meetings/${meeting.id}`}>
                    <div className="group surface-row flex items-center gap-4 cursor-pointer">
                      <div className="shrink-0 w-10 h-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
                        <Calendar className="w-4 h-4 text-primary" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="font-medium text-sm truncate group-hover:text-primary transition-colors">
                          {meeting.title}
                        </div>
                        <div className="text-xs text-muted-foreground font-mono mt-0.5">
                          {new Date(meeting.date).toLocaleDateString(undefined, {
                            weekday: "short",
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })}
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="text-xs font-mono text-muted-foreground hidden sm:inline">
                          {meeting.entity_count} entities
                        </span>
                        <StatusBadge status={meeting.status} type="meeting" />
                        <ChevronRight className="w-4 h-4 text-muted-foreground/40 group-hover:text-primary transition-colors" />
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={Calendar}
                title="No meetings yet"
                description="Upload a transcript to start building memory."
              />
            )}
          </CardContent>
        </SurfaceCard>

        <SurfaceCard className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Entity Breakdown</CardTitle>
            <CardDescription className="mt-1">
              {totalEntities > 0 ? `${totalEntities} total across ${entityData.length} types` : "No data yet"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {entityData.length > 0 ? (
              <div className="flex flex-col sm:flex-row items-center gap-5">
                <div className="h-[140px] w-[140px] shrink-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={entityData}
                        cx="50%"
                        cy="50%"
                        innerRadius={42}
                        outerRadius={62}
                        paddingAngle={3}
                        dataKey="value"
                        stroke="transparent"
                      >
                        {entityData.map((_, index) => (
                          <PieCell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "hsl(var(--card))",
                          borderColor: "hsl(var(--border))",
                          borderRadius: "8px",
                          fontSize: "12px",
                        }}
                        itemStyle={{ color: "hsl(var(--foreground))" }}
                        formatter={(value: number, _name, props) => [
                          `${value} (${Math.round((value / totalEntities) * 100)}%)`,
                          props.payload.label,
                        ]}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex flex-wrap gap-2 flex-1 justify-center sm:justify-start min-w-0">
                  {entityData.map((entry, index) => (
                    <span
                      key={entry.name}
                      className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md border border-border/40 bg-background/40 text-muted-foreground"
                    >
                      <span
                        className="w-2 h-2 rounded-full shrink-0"
                        style={{ backgroundColor: CHART_COLORS[index % CHART_COLORS.length] }}
                      />
                      <span className="text-foreground">{entry.label}</span>
                      <span className="font-mono text-muted-foreground/80">{entry.value}</span>
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <EmptyState
                icon={Database}
                title="No entities yet"
                description="Entities appear after meetings are processed."
              />
            )}
          </CardContent>
        </SurfaceCard>
      </div>
    </PageShell>
  );
}
