import { useParams } from "wouter";
import { useGetDecisionEvolution, getGetDecisionEvolutionQueryKey } from "@workspace/api-client-react";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/badges";
import { GitMerge, ArrowRight, GitCommit, CheckCircle2, XCircle } from "lucide-react";
import { CardContent } from "@/components/ui/card";
import { PageShell, PageHeader, SurfaceCard } from "@/components/page-shell";
import { cn } from "@/lib/utils";

export default function DecisionEvolution() {
  const params = useParams();
  const id = parseInt(params.id || "0", 10);
  const { data, isLoading } = useGetDecisionEvolution(id, { query: { enabled: !!id, queryKey: getGetDecisionEvolutionQueryKey(id) } });

  if (isLoading) {
    return (
      <div className="p-8 max-w-4xl mx-auto space-y-8">
        <Skeleton className="h-12 w-2/3" />
        <div className="space-y-4 relative border-l-2 border-primary/20 ml-4 pl-8">
          {[1, 2, 3].map(i => <Skeleton key={i} className="h-32" />)}
        </div>
      </div>
    );
  }

  if (!data) return <div className="p-8 text-center text-muted-foreground">Decision evolution not found</div>;

  return (
    <PageShell maxWidth="6xl" className="space-y-10">
      <PageHeader
        title={data.title}
        description={data.current_description}
        meta={
          <div className="flex flex-wrap items-center gap-3 pt-2">
            <span className="text-xs font-mono text-primary flex items-center gap-1.5">
              <GitMerge className="w-3.5 h-3.5" />
              DECISION EVOLUTION
            </span>
            <StatusBadge status={data.current_status} type="decision" />
            {data.project_name && (
              <span className="text-xs font-mono text-blue-400 border border-blue-500/20 bg-blue-500/10 px-2 py-1 rounded-md">
                {data.project_name}
              </span>
            )}
          </div>
        }
      />

      <div className="grid md:grid-cols-2 gap-6">
        {(data.pros && data.pros.length > 0) && (
          <SurfaceCard className="bg-emerald-500/5 border-emerald-500/20">
            <CardContent className="p-4">
              <h3 className="font-medium text-emerald-500 flex items-center gap-2 mb-3">
                <CheckCircle2 className="w-4 h-4" /> Supporting Factors
              </h3>
              <ul className="space-y-2 text-sm text-emerald-100/80">
                {data.pros.map((p, i) => <li key={i} className="flex gap-2"><span className="opacity-50">•</span>{p}</li>)}
              </ul>
            </CardContent>
          </SurfaceCard>
        )}
        {(data.cons && data.cons.length > 0) && (
          <SurfaceCard className="bg-rose-500/5 border-rose-500/20">
            <CardContent className="p-4">
              <h3 className="font-medium text-rose-500 flex items-center gap-2 mb-3">
                <XCircle className="w-4 h-4" /> Risk Factors
              </h3>
              <ul className="space-y-2 text-sm text-rose-100/80">
                {data.cons.map((c, i) => <li key={i} className="flex gap-2"><span className="opacity-50">•</span>{c}</li>)}
              </ul>
            </CardContent>
          </SurfaceCard>
        )}
      </div>

      <div className="relative">
        <div className="absolute top-0 bottom-0 left-[23px] w-px bg-gradient-to-b from-primary/40 via-border/50 to-transparent" />
        <div className="space-y-8">
          {data.history.map((entry, index) => {
            const isLast = index === data.history.length - 1;
            return (
              <div key={index} className="relative pl-14">
                <div className={cn(
                  "absolute left-4 top-5 w-3 h-3 rounded-full border-2 bg-background z-10 -translate-x-1/2",
                  isLast ? "border-primary bg-primary shadow-[0_0_10px_rgba(139,92,246,0.5)]" : "border-primary/50"
                )} />
                <SurfaceCard className={cn("transition-all", isLast && "border-primary/40 bg-primary/5 shadow-md shadow-primary/5")}>
                  <CardContent className="p-5 space-y-3">
                    <div className="flex justify-between items-start">
                      <div className="flex items-center gap-3">
                        <BadgeForAction action={entry.action} />
                        <span className="text-sm font-mono text-muted-foreground">{new Date(entry.date).toLocaleDateString()}</span>
                      </div>
                      <div className="text-xs font-mono text-muted-foreground px-2 py-1 bg-accent rounded">
                        {entry.meeting_title}
                      </div>
                    </div>

                    <p className="text-sm">{entry.description}</p>

                    {entry.previous_value && entry.new_value && (
                      <div className="mt-4 p-3 bg-background/50 rounded border border-border/50 flex flex-col sm:flex-row items-center gap-3 font-mono text-xs">
                        <div className="flex-1 w-full p-2 bg-rose-500/10 text-rose-400 rounded border border-rose-500/20 line-through decoration-rose-500/50">
                          {entry.previous_value}
                        </div>
                        <ArrowRight className="w-4 h-4 text-muted-foreground shrink-0" />
                        <div className="flex-1 w-full p-2 bg-emerald-500/10 text-emerald-400 rounded border border-emerald-500/20">
                          {entry.new_value}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </SurfaceCard>
              </div>
            );
          })}
        </div>
      </div>
    </PageShell>
  );
}

function BadgeForAction({ action }: { action: string }) {
  let color = "text-slate-400 border-slate-500/20 bg-slate-500/10";
  if (action === "created") color = "text-blue-400 border-blue-500/20 bg-blue-500/10";
  if (action === "updated") color = "text-amber-400 border-amber-500/20 bg-amber-500/10";
  if (action === "superseded") color = "text-rose-400 border-rose-500/20 bg-rose-500/10";
  if (action === "confirmed") color = "text-emerald-400 border-emerald-500/20 bg-emerald-500/10";

  return (
    <span className={cn("text-xs font-mono px-2 py-1 rounded border uppercase", color)}>
      {action}
    </span>
  );
}
