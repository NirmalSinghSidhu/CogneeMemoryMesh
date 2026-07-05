import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function EntityTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    person: "bg-cyan-500/10 text-cyan-500 border-cyan-500/20",
    project: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    topic: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    decision: "bg-amber-500/10 text-amber-500 border-amber-500/20",
    task: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
    risk: "bg-red-500/10 text-red-500 border-red-500/20",
    blocker: "bg-rose-500/10 text-rose-500 border-rose-500/20",
    document: "bg-slate-500/10 text-slate-500 border-slate-500/20",
    question: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    deadline: "bg-orange-500/10 text-orange-500 border-orange-500/20",
  };

  return (
    <Badge variant="outline" className={cn("font-mono text-[10px] uppercase", colors[type] || colors.topic)}>
      {type}
    </Badge>
  );
}

export function StatusBadge({ status, type = "meeting" }: { status: string, type?: "meeting" | "decision" | "task" }) {
  let color = "bg-slate-500/10 text-slate-500 border-slate-500/20";
  
  if (type === "meeting") {
    if (status === "pending") color = "bg-amber-500/10 text-amber-500 border-amber-500/20";
    if (status === "processing") color = "bg-blue-500/10 text-blue-500 border-blue-500/20 animate-pulse";
    if (status === "indexed") color = "bg-emerald-500/10 text-emerald-500 border-emerald-500/20";
    if (status === "failed") color = "bg-red-500/10 text-red-500 border-red-500/20";
  } else if (type === "decision") {
    if (status === "active") color = "bg-emerald-500/10 text-emerald-500 border-emerald-500/20";
    if (status === "revised") color = "bg-amber-500/10 text-amber-500 border-amber-500/20";
    if (status === "superseded") color = "bg-slate-500/10 text-slate-500 border-slate-500/20";
    if (status === "implemented") color = "bg-blue-500/10 text-blue-500 border-blue-500/20";
    if (status === "rejected") color = "bg-red-500/10 text-red-500 border-red-500/20";
  } else if (type === "task") {
    if (status === "open") color = "bg-blue-500/10 text-blue-500 border-blue-500/20";
    if (status === "in_progress") color = "bg-amber-500/10 text-amber-500 border-amber-500/20";
    if (status === "completed") color = "bg-emerald-500/10 text-emerald-500 border-emerald-500/20";
    if (status === "blocked") color = "bg-red-500/10 text-red-500 border-red-500/20";
    if (status === "overdue") color = "bg-rose-500/10 text-rose-500 border-rose-500/20";
  }

  return (
    <Badge variant="outline" className={cn("font-mono text-[10px] uppercase", color)}>
      {status}
    </Badge>
  );
}
