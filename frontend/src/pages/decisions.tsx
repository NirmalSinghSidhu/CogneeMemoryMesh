import { useListDecisions } from "@workspace/api-client-react";
import { CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "wouter";
import { StatusBadge } from "@/components/badges";
import { GitMerge, User, Calendar, History } from "lucide-react";
import { PageShell, HeroBanner, SurfaceCard, EmptyState } from "@/components/page-shell";

export default function Decisions() {
  const { data: decisions, isLoading } = useListDecisions();

  return (
    <PageShell maxWidth="6xl" className="space-y-6">
      <HeroBanner
        eyebrow="Lifecycle"
        eyebrowIcon={GitMerge}
        title="Decisions Tracker"
        description="Track the lifecycle of every technical and business decision."
      />

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : decisions && decisions.length > 0 ? (
        <div className="grid gap-3">
          {decisions.map((decision) => (
            <Link key={decision.id} href={`/decisions/${decision.id}/evolution`}>
              <SurfaceCard hover>
                <CardContent className="p-5 md:p-6 flex items-center justify-between gap-4">
                  <div className="space-y-2 min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-base md:text-lg font-medium">{decision.title}</h3>
                      <StatusBadge status={decision.status} type="decision" />
                      {decision.revision_count ? (
                        <span className="text-xs font-mono bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-md border border-blue-500/20 flex items-center gap-1">
                          <History className="w-3 h-3" />
                          v{decision.revision_count + 1}
                        </span>
                      ) : null}
                    </div>
                    {decision.description && (
                      <p className="text-sm text-muted-foreground line-clamp-2">{decision.description}</p>
                    )}
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs font-mono text-muted-foreground pt-1">
                      {decision.project_name && (
                        <span className="text-blue-400">PROJECT: {decision.project_name}</span>
                      )}
                      {decision.assigned_to && (
                        <span className="flex items-center gap-1 text-cyan-400">
                          <User className="w-3 h-3" /> {decision.assigned_to}
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" /> {new Date(decision.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                  <GitMerge className="w-7 h-7 text-muted-foreground/25 shrink-0 hidden sm:block" />
                </CardContent>
              </SurfaceCard>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={GitMerge}
          title="No decisions tracked"
          description="Decisions extracted from meetings will appear here."
        />
      )}
    </PageShell>
  );
}
