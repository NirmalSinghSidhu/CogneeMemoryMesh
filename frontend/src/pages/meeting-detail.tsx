import { useParams } from "wouter";
import { useGetMeeting, useProcessMeeting, getGetMeetingQueryKey } from "@workspace/api-client-react";
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageShell, PageHeader, SurfaceCard } from "@/components/page-shell";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge, EntityTypeBadge } from "@/components/badges";
import { RefreshCw, Users, FileText, CheckCircle2, AlertTriangle, Lightbulb, CheckSquare } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useQueryClient } from "@tanstack/react-query";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function MeetingDetail() {
  const params = useParams();
  const id = parseInt(params.id || "0", 10);
  const { data: meeting, isLoading } = useGetMeeting(id, { query: { enabled: !!id, queryKey: getGetMeetingQueryKey(id) } });
  const processMeeting = useProcessMeeting();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  if (isLoading) {
    return (
      <div className="p-8 space-y-6 max-w-7xl mx-auto">
        <Skeleton className="h-12 w-1/3" />
        <Skeleton className="h-6 w-1/4" />
        <div className="grid grid-cols-3 gap-6 mt-8">
          <Skeleton className="col-span-2 h-[600px]" />
          <Skeleton className="h-[600px]" />
        </div>
      </div>
    );
  }

  if (!meeting) return <div className="p-8 text-center text-muted-foreground">Meeting not found</div>;

  const handleProcess = () => {
    processMeeting.mutate({ id }, {
      onSuccess: () => {
        toast({ title: "Success", description: "Reprocessing triggered" });
        queryClient.invalidateQueries({ queryKey: getGetMeetingQueryKey(id) });
      },
      onError: () => {
        toast({ title: "Error", description: "Failed to trigger processing", variant: "destructive" });
      }
    });
  };

  const groupedEntities = meeting.entities.reduce((acc, entity) => {
    if (!acc[entity.type]) acc[entity.type] = [];
    acc[entity.type].push(entity);
    return acc;
  }, {} as Record<string, typeof meeting.entities>);

  return (
    <PageShell className="space-y-6">
      <PageHeader
        title={meeting.title}
        description={
          <span className="font-mono text-xs md:text-sm">
            {new Date(meeting.date).toLocaleString()} • {meeting.duration_minutes || "?"} min duration
          </span>
        }
        actions={
          <div className="flex items-center gap-3">
            <StatusBadge status={meeting.status} type="meeting" />
            <Button variant="outline" onClick={handleProcess} disabled={processMeeting.isPending} className="gap-2">
              <RefreshCw className={`w-4 h-4 ${processMeeting.isPending ? "animate-spin" : ""}`} />
              Re-process
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {meeting.summary && (
            <SurfaceCard className="bg-primary/5 border-primary/20">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Lightbulb className="w-5 h-5 text-primary" />
                  AI Summary
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed">{meeting.summary}</p>
              </CardContent>
            </SurfaceCard>
          )}

          <Tabs defaultValue="transcript" className="w-full">
            <TabsList className="w-full justify-start bg-card/50 border-b rounded-none px-0 h-auto">
              <TabsTrigger value="transcript" className="rounded-none data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-primary px-4 py-2">
                Transcript
              </TabsTrigger>
              <TabsTrigger value="decisions" className="rounded-none data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-primary px-4 py-2">
                Decisions ({meeting.decisions?.length || 0})
              </TabsTrigger>
              <TabsTrigger value="tasks" className="rounded-none data-[state=active]:bg-transparent data-[state=active]:border-b-2 data-[state=active]:border-primary px-4 py-2">
                Tasks ({meeting.tasks?.length || 0})
              </TabsTrigger>
            </TabsList>
            
            <TabsContent value="transcript" className="mt-4">
              <SurfaceCard>
                <CardContent className="p-6">
                  <div className="prose dark:prose-invert max-w-none text-sm font-mono whitespace-pre-wrap leading-relaxed opacity-80">
                    {meeting.transcript}
                  </div>
                </CardContent>
              </SurfaceCard>
            </TabsContent>

            <TabsContent value="decisions" className="mt-4">
              <div className="space-y-4">
                {meeting.decisions?.map(d => (
                  <SurfaceCard key={d.id}>
                    <CardContent className="p-4 flex justify-between items-start">
                      <div>
                        <div className="font-medium">{d.title}</div>
                        {d.description && <p className="text-sm text-muted-foreground mt-1">{d.description}</p>}
                        {d.assigned_to && <div className="text-xs font-mono mt-2 text-cyan-500">Assigned: {d.assigned_to}</div>}
                      </div>
                      <StatusBadge status={d.status} type="decision" />
                    </CardContent>
                  </SurfaceCard>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="tasks" className="mt-4">
              <div className="space-y-4">
                {meeting.tasks?.map(t => (
                  <SurfaceCard key={t.id}>
                    <CardContent className="p-4 flex justify-between items-start">
                      <div>
                        <div className="font-medium flex items-center gap-2">
                          <CheckSquare className="w-4 h-4 text-emerald-500" />
                          {t.title}
                        </div>
                        {t.description && <p className="text-sm text-muted-foreground mt-1">{t.description}</p>}
                        <div className="flex gap-4 mt-2">
                          {t.assigned_to && <div className="text-xs font-mono text-cyan-500">Owner: {t.assigned_to}</div>}
                          {t.due_date && <div className="text-xs font-mono text-rose-500">Due: {new Date(t.due_date).toLocaleDateString()}</div>}
                        </div>
                      </div>
                      <StatusBadge status={t.status} type="task" />
                    </CardContent>
                  </SurfaceCard>
                ))}
              </div>
            </TabsContent>
          </Tabs>
        </div>

        <div className="space-y-6">
          <SurfaceCard>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Users className="w-5 h-5" />
                Participants
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {meeting.participants?.map(p => (
                  <div key={p.id} className="px-3 py-1.5 bg-accent rounded-md text-sm border border-border flex flex-col">
                    <span className="font-medium">{p.name}</span>
                    {p.role && <span className="text-[10px] text-muted-foreground font-mono uppercase">{p.role}</span>}
                  </div>
                ))}
              </div>
            </CardContent>
          </SurfaceCard>

          <SurfaceCard>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">Extracted Entities</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {Object.entries(groupedEntities).map(([type, entities]) => (
                <div key={type} className="space-y-2">
                  <div className="text-xs font-mono uppercase tracking-wider text-muted-foreground border-b border-border/50 pb-1">
                    {type} ({entities.length})
                  </div>
                  <div className="flex flex-wrap gap-2 pt-1">
                    {entities.map(e => (
                      <div key={e.id} className="flex items-center gap-2 px-2 py-1 bg-background border border-border/50 rounded text-sm">
                        <EntityTypeBadge type={e.type} />
                        <span>{e.name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </CardContent>
          </SurfaceCard>

          {(meeting.risks?.length || 0) > 0 && (
            <SurfaceCard className="bg-rose-500/5 border-rose-500/20">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2 text-rose-500">
                  <AlertTriangle className="w-5 h-5" />
                  Identified Risks
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-disc pl-5 text-sm space-y-2 text-rose-400/90">
                  {meeting.risks?.map((risk, i) => <li key={i}>{risk}</li>)}
                </ul>
              </CardContent>
            </SurfaceCard>
          )}
        </div>
      </div>
    </PageShell>
  );
}
