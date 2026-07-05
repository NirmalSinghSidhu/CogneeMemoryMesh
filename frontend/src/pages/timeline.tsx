import { useGetTimeline } from "@workspace/api-client-react";
import { Skeleton } from "@/components/ui/skeleton";
import { GitCommit, Calendar, GitMerge, CheckSquare, Combine, Activity } from "lucide-react";
import { PageShell, HeroBanner, EmptyState } from "@/components/page-shell";

export default function Timeline() {
  const { data: timeline, isLoading } = useGetTimeline();

  if (isLoading) {
    return (
      <PageShell maxWidth="4xl" className="space-y-6">
        <Skeleton className="h-10 w-48" />
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-20" />
        ))}
      </PageShell>
    );
  }

  return (
    <PageShell maxWidth="4xl" className="space-y-8">
      <HeroBanner
        eyebrow="Chronology"
        eyebrowIcon={Activity}
        title="Organization Timeline"
        description="Chronological record of meetings, decisions, and memory updates."
      />

      {timeline && timeline.length > 0 ? (
        <div className="relative">
          <div className="absolute top-0 bottom-0 left-[27px] w-px bg-gradient-to-b from-primary/40 via-border/50 to-transparent" />
          <div className="space-y-4">
            {timeline.map((event, index) => (
              <div key={event.id || index} className="relative pl-16">
                <div className="absolute left-[18px] top-2 w-5 h-5 rounded-full border-2 border-border bg-card z-10 flex items-center justify-center shadow-sm">
                  <EventIcon type={event.type} />
                </div>
                <div className="surface-row">
                  <div className="flex justify-between items-start gap-4 mb-1">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="font-semibold text-sm truncate">{event.title}</span>
                      {event.is_milestone && (
                        <span className="text-[10px] font-mono bg-primary/15 text-primary px-1.5 py-0.5 rounded-md uppercase shrink-0">
                          Milestone
                        </span>
                      )}
                    </div>
                    <span className="text-xs font-mono text-muted-foreground shrink-0">
                      {new Date(event.date).toLocaleDateString()}
                    </span>
                  </div>
                  {event.description && (
                    <p className="text-sm text-muted-foreground mt-1 leading-relaxed">{event.description}</p>
                  )}

                  <div className="flex flex-wrap gap-3 mt-3 text-xs font-mono">
                    {event.type && <span className="text-cyan-400 uppercase">{event.type}</span>}
                    {event.project_name && <span className="text-blue-400">{event.project_name}</span>}
                    {event.meeting_title && (
                      <span className="text-muted-foreground/70">SRC: {event.meeting_title}</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <EmptyState
          icon={GitCommit}
          title="No events yet"
          description="Your organizational timeline will populate as meetings are processed."
        />
      )}
    </PageShell>
  );
}

function EventIcon({ type }: { type: string }) {
  if (type === "meeting") return <Calendar className="w-2.5 h-2.5 text-blue-400" />;
  if (type === "decision" || type === "decision_update")
    return <GitMerge className="w-2.5 h-2.5 text-amber-400" />;
  if (type === "task") return <CheckSquare className="w-2.5 h-2.5 text-emerald-400" />;
  if (type === "entity_merge") return <Combine className="w-2.5 h-2.5 text-blue-400" />;
  return <GitCommit className="w-2.5 h-2.5 text-muted-foreground" />;
}
