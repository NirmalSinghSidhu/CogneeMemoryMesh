import { useEffect, useState } from "react";
import {
  useGetMemoryStats,
  useRememberMeeting,
  useRecallMemory,
  useImproveMemory,
  useForgetMemory,
  useListMeetings,
  useListProjects,
  useListEntities,
  getGetMemoryStatsQueryKey,
  ForgetInputScope,
  ImproveInputRelationshipType,
} from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { BrainCircuit, Database, RefreshCw, Trash2, Zap } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { authFetch } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { PageShell, HeroBanner, SurfaceCard } from "@/components/page-shell";

interface CogneeHealth {
  active: boolean;
  message: string;
  dataset_count?: number | null;
  required?: boolean;
}

const selectClass =
  "w-full h-9 rounded-md border border-input bg-background px-3 text-sm";

function mutationErrorMessage(err: unknown): string {
  if (!err) return "Request failed";
  if (typeof err === "string") return err;
  if (err instanceof Error) return err.message;
  const anyErr = err as { message?: string; data?: { detail?: string } };
  return anyErr.data?.detail || anyErr.message || "Request failed";
}

function NameSelect({
  value,
  onChange,
  placeholder,
  options,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  options: { id: number; label: string }[];
  className?: string;
}) {
  return (
    <select
      className={cn(selectClass, className)}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">{placeholder}</option>
      {options.map((opt) => (
        <option key={opt.id} value={String(opt.id)}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}

export default function Memory() {
  const queryClient = useQueryClient();
  const { data: stats, isLoading } = useGetMemoryStats();
  const { data: meetings = [] } = useListMeetings();
  const { data: projects = [] } = useListProjects();
  const { data: entities = [] } = useListEntities();
  const [health, setHealth] = useState<CogneeHealth | null>(null);

  const [meetingId, setMeetingId] = useState("");
  const [forceReindex, setForceReindex] = useState(false);
  const [recallQuery, setRecallQuery] = useState("");
  const [improveMeetingId, setImproveMeetingId] = useState("");
  const [improveEntityId, setImproveEntityId] = useState("");
  const [relationshipType, setRelationshipType] = useState<string>(
    ImproveInputRelationshipType.updates
  );
  const [forgetScope, setForgetScope] = useState<string>(ForgetInputScope.meeting);
  const [forgetTargetId, setForgetTargetId] = useState("");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  const rememberMutation = useRememberMeeting();
  const recallMutation = useRecallMemory();
  const improveMutation = useImproveMemory();
  const forgetMutation = useForgetMemory();

  const meetingOptions = meetings.map((m) => ({
    id: m.id,
    label: `${m.title}${m.status ? ` (${m.status})` : ""}`,
  }));
  const projectOptions = projects.map((p) => ({
    id: p.id,
    label: p.name,
  }));
  const entityOptions = entities.map((e) => ({
    id: e.id,
    label: `${e.name} [${e.type}]`,
  }));

  const refreshStats = () => {
    queryClient.invalidateQueries({ queryKey: getGetMemoryStatsQueryKey() });
  };

  useEffect(() => {
    let cancelled = false;
    authFetch("/api/memory/health")
      .then(async (res) => {
        if (!res.ok) throw new Error("Health check failed");
        return res.json();
      })
      .then((data: CogneeHealth) => {
        if (!cancelled) setHealth(data);
      })
      .catch(() => {
        if (!cancelled) {
          setHealth({ active: false, message: "Unable to reach memory health endpoint" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Clear forget target when scope changes so the wrong list isn't reused.
  useEffect(() => {
    setForgetTargetId("");
  }, [forgetScope]);

  const setOk = (msg: string) => {
    setStatusError(null);
    setStatusMessage(msg);
    refreshStats();
  };

  const setErr = (err: unknown) => {
    setStatusMessage(null);
    setStatusError(mutationErrorMessage(err));
  };

  const handleRemember = () => {
    const id = parseInt(meetingId, 10);
    if (!id) {
      setErr("Select a meeting");
      return;
    }
    rememberMutation.mutate(
      { data: { meeting_id: id, force_reindex: forceReindex } },
      {
        onSuccess: (data) => setOk(data.message || (data.success ? "Remember complete" : "Remember failed")),
        onError: setErr,
      }
    );
  };

  const handleRecall = () => {
    if (!recallQuery.trim()) {
      setErr("Enter a recall query");
      return;
    }
    recallMutation.mutate(
      { data: { query: recallQuery.trim(), context_limit: 10 } },
      {
        onSuccess: (data) =>
          setOk(`Recall returned ${data.total} result(s) for "${data.query}"`),
        onError: setErr,
      }
    );
  };

  const handleImprove = () => {
    const mid = parseInt(improveMeetingId, 10);
    const eid = parseInt(improveEntityId, 10);
    if (!mid || !eid) {
      setErr("Select a meeting and an entity");
      return;
    }
    improveMutation.mutate(
      {
        data: {
          meeting_id: mid,
          target_entity_id: eid,
          relationship_type: relationshipType as typeof ImproveInputRelationshipType[keyof typeof ImproveInputRelationshipType],
        },
      },
      {
        onSuccess: (data) => setOk(data.message || (data.success ? "Improve complete" : "Improve failed")),
        onError: setErr,
      }
    );
  };

  const handleForget = () => {
    const needsTarget = forgetScope !== ForgetInputScope.workspace;
    const targetId = forgetTargetId ? parseInt(forgetTargetId, 10) : undefined;
    if (needsTarget && !targetId) {
      setErr(`Select a ${forgetScope} to forget`);
      return;
    }

    let label = "the entire workspace";
    if (forgetScope === ForgetInputScope.meeting) {
      label = meetings.find((m) => m.id === targetId)?.title || `meeting #${targetId}`;
    } else if (forgetScope === ForgetInputScope.project) {
      label = projects.find((p) => p.id === targetId)?.name || `project #${targetId}`;
    } else if (forgetScope === ForgetInputScope.entity) {
      label = entities.find((e) => e.id === targetId)?.name || `entity #${targetId}`;
    }

    if (!window.confirm(`Permanently forget ${label}? This cannot be undone.`)) {
      return;
    }
    forgetMutation.mutate(
      {
        data: {
          scope: forgetScope as typeof ForgetInputScope[keyof typeof ForgetInputScope],
          target_id: needsTarget ? targetId : null,
        },
      },
      {
        onSuccess: (data) => setOk(data.message || (data.success ? "Forget complete" : "Forget failed")),
        onError: setErr,
      }
    );
  };

  const forgetTargetOptions =
    forgetScope === ForgetInputScope.meeting
      ? meetingOptions
      : forgetScope === ForgetInputScope.project
        ? projectOptions
        : forgetScope === ForgetInputScope.entity
          ? entityOptions
          : [];

  const forgetPlaceholder =
    forgetScope === ForgetInputScope.meeting
      ? "Select meeting…"
      : forgetScope === ForgetInputScope.project
        ? "Select project…"
        : forgetScope === ForgetInputScope.entity
          ? "Select entity…"
          : "Select target…";

  const busy =
    rememberMutation.isPending ||
    recallMutation.isPending ||
    improveMutation.isPending ||
    forgetMutation.isPending;

  return (
    <PageShell maxWidth="6xl" className="space-y-8">
      <HeroBanner
        eyebrow="Cognee"
        eyebrowIcon={BrainCircuit}
        title="Memory Operations"
        description="Control panel for the Cognee lifecycle operations."
        pills={
          <span
            className={`text-xs font-mono px-3 py-1.5 rounded-lg border ${
              health?.active
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                : "bg-rose-500/10 border-rose-500/30 text-rose-400"
            }`}
          >
            COGNEE: {health ? (health.active ? "ACTIVE" : "INACTIVE") : "…"}
            {typeof health?.dataset_count === "number" && ` · ${health.dataset_count} datasets`}
          </span>
        }
      />

      {(statusMessage || statusError) && (
        <div
          className={`text-sm px-4 py-3 rounded border ${
            statusError
              ? "bg-rose-500/10 border-rose-500/30 text-rose-300"
              : "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
          }`}
        >
          {statusError || statusMessage}
        </div>
      )}

      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
        <SurfaceCard className="bg-blue-500/5 border-blue-500/20 hover:border-blue-500/40 transition-colors">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-blue-500">
              <Database className="w-5 h-5" /> Remember
            </CardTitle>
            <CardDescription>Index and merge new information into the graph.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <NameSelect
              value={meetingId}
              onChange={setMeetingId}
              placeholder="Select meeting…"
              options={meetingOptions}
            />
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={forceReindex}
                onChange={(e) => setForceReindex(e.target.checked)}
              />
              Force reindex
            </label>
            <Button
              variant="outline"
              className="w-full text-blue-500 border-blue-500/50 hover:bg-blue-500/10"
              disabled={busy || !meetingId}
              onClick={handleRemember}
            >
              {rememberMutation.isPending ? "Running…" : "Manual Trigger"}
            </Button>
          </CardContent>
        </SurfaceCard>

        <SurfaceCard className="bg-cyan-500/5 border-cyan-500/20 hover:border-cyan-500/40 transition-colors">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-cyan-500">
              <RefreshCw className="w-5 h-5" /> Recall
            </CardTitle>
            <CardDescription>Retrieve semantic and structural memory context.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              placeholder="Query memory…"
              value={recallQuery}
              onChange={(e) => setRecallQuery(e.target.value)}
            />
            <Button
              variant="outline"
              className="w-full text-cyan-500 border-cyan-500/50 hover:bg-cyan-500/10"
              disabled={busy}
              onClick={handleRecall}
            >
              {recallMutation.isPending ? "Running…" : "Test Recall"}
            </Button>
          </CardContent>
        </SurfaceCard>

        <SurfaceCard className="bg-emerald-500/5 border-emerald-500/20 hover:border-emerald-500/40 transition-colors">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-emerald-500">
              <Zap className="w-5 h-5" /> Improve
            </CardTitle>
            <CardDescription>Refine graph weights and entity resolution.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <NameSelect
              value={improveMeetingId}
              onChange={setImproveMeetingId}
              placeholder="Select meeting…"
              options={meetingOptions}
            />
            <NameSelect
              value={improveEntityId}
              onChange={setImproveEntityId}
              placeholder="Select entity…"
              options={entityOptions}
            />
            <select
              className={selectClass}
              value={relationshipType}
              onChange={(e) => setRelationshipType(e.target.value)}
            >
              {Object.values(ImproveInputRelationshipType).map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
            <Button
              variant="outline"
              className="w-full text-emerald-500 border-emerald-500/50 hover:bg-emerald-500/10"
              disabled={busy || !improveMeetingId || !improveEntityId}
              onClick={handleImprove}
            >
              {improveMutation.isPending ? "Running…" : "Run Optimization"}
            </Button>
          </CardContent>
        </SurfaceCard>

        <SurfaceCard className="bg-rose-500/5 border-rose-500/20 hover:border-rose-500/40 transition-colors">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-rose-500">
              <Trash2 className="w-5 h-5" /> Forget
            </CardTitle>
            <CardDescription>Prune outdated or incorrect memory branches.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <select
              className={selectClass}
              value={forgetScope}
              onChange={(e) => setForgetScope(e.target.value)}
            >
              {Object.values(ForgetInputScope).map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
            {forgetScope !== ForgetInputScope.workspace && (
              <NameSelect
                value={forgetTargetId}
                onChange={setForgetTargetId}
                placeholder={forgetPlaceholder}
                options={forgetTargetOptions}
              />
            )}
            <Button
              variant="outline"
              className="w-full text-rose-500 border-rose-500/50 hover:bg-rose-500/10"
              disabled={busy || (forgetScope !== ForgetInputScope.workspace && !forgetTargetId)}
              onClick={handleForget}
            >
              {forgetMutation.isPending ? "Running…" : "Prune Graph"}
            </Button>
          </CardContent>
        </SurfaceCard>
      </div>

      {recallMutation.data && recallMutation.data.results.length > 0 && (
        <SurfaceCard>
          <CardHeader>
            <CardTitle className="text-base">Recall Results</CardTitle>
            <CardDescription>
              {recallMutation.data.total} hit(s) for &quot;{recallMutation.data.query}&quot;
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {recallMutation.data.results.map((item, i) => (
              <div
                key={i}
                className="text-sm p-3 rounded border border-border/40 bg-accent/20 space-y-1"
              >
                <div className="flex justify-between gap-2">
                  <span className="font-medium">
                    {item.entity_name || item.meeting_title || "Memory"}
                  </span>
                  <span className="font-mono text-xs text-muted-foreground">
                    SCORE: {item.relevance_score.toFixed(3)}
                  </span>
                </div>
                <p className="text-muted-foreground text-xs leading-relaxed line-clamp-4">
                  {item.content}
                </p>
                {item.meeting_title && (
                  <div className="text-xs font-mono text-muted-foreground">
                    SOURCE: {item.meeting_title}
                    {item.meeting_id != null ? ` (#${item.meeting_id})` : ""}
                  </div>
                )}
              </div>
            ))}
          </CardContent>
        </SurfaceCard>
      )}

      <SurfaceCard>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BrainCircuit className="w-5 h-5" /> Memory Diagnostics
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center py-4">
              <div>
                <div className="text-3xl font-mono font-bold text-primary">{stats?.total_entities}</div>
                <div className="text-xs text-muted-foreground uppercase tracking-wider mt-1">Stored Entities</div>
              </div>
              <div>
                <div className="text-3xl font-mono font-bold text-primary">{stats?.total_relationships}</div>
                <div className="text-xs text-muted-foreground uppercase tracking-wider mt-1">Relationships</div>
              </div>
              <div>
                <div className="text-3xl font-mono font-bold text-primary">{stats?.memory_size_mb?.toFixed(1) || 0} MB</div>
                <div className="text-xs text-muted-foreground uppercase tracking-wider mt-1">Storage Size</div>
              </div>
              <div>
                <div className="text-3xl font-mono font-bold text-primary">{stats?.total_meetings}</div>
                <div className="text-xs text-muted-foreground uppercase tracking-wider mt-1">Indexed Sources</div>
              </div>
            </div>
          )}
        </CardContent>
      </SurfaceCard>
    </PageShell>
  );
}
