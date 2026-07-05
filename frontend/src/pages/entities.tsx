import { useListEntities } from "@workspace/api-client-react";
import { Skeleton } from "@/components/ui/skeleton";
import { EntityTypeBadge } from "@/components/badges";
import {
  Table,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableBody,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Database } from "lucide-react";
import { useState } from "react";
import { PageShell, HeroBanner, EmptyState } from "@/components/page-shell";

export default function Entities() {
  const { data: entities, isLoading } = useListEntities();
  const [filter, setFilter] = useState("");

  const filtered = entities?.filter(
    (e) =>
      e.name.toLowerCase().includes(filter.toLowerCase()) ||
      e.type.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <PageShell maxWidth="6xl" className="space-y-6">
      <HeroBanner
        eyebrow="Knowledge Base"
        eyebrowIcon={Database}
        title="Entity Database"
        description="All unique nodes extracted across all sources."
        actions={
          <div className="w-full sm:w-64">
            <Input
              placeholder="Filter entities..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="bg-background/60"
            />
          </div>
        }
      />

      <div className="rounded-xl border border-border/40 bg-card/30 backdrop-blur-sm overflow-hidden shadow-sm">
        <Table>
          <TableHeader>
            <TableRow className="border-border/40 hover:bg-transparent bg-muted/20">
              <TableHead className="w-[100px] font-mono text-xs uppercase tracking-wider">ID</TableHead>
              <TableHead className="font-mono text-xs uppercase tracking-wider">Type</TableHead>
              <TableHead className="font-mono text-xs uppercase tracking-wider">Name</TableHead>
              <TableHead className="text-right font-mono text-xs uppercase tracking-wider">Mentions</TableHead>
              <TableHead className="font-mono text-xs uppercase tracking-wider">First Seen</TableHead>
              <TableHead className="font-mono text-xs uppercase tracking-wider">Last Seen</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-12">
                  <Skeleton className="h-8 w-full max-w-md mx-auto" />
                </TableCell>
              </TableRow>
            ) : filtered && filtered.length > 0 ? (
              filtered.map((entity) => (
                <TableRow
                  key={entity.id}
                  className="border-border/30 hover:bg-accent/30 transition-colors"
                >
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    E-{entity.id.toString().padStart(4, "0")}
                  </TableCell>
                  <TableCell>
                    <EntityTypeBadge type={entity.type} />
                  </TableCell>
                  <TableCell className="font-medium">{entity.name}</TableCell>
                  <TableCell className="text-right font-mono text-sm">{entity.meeting_count}</TableCell>
                  <TableCell className="text-muted-foreground text-sm font-mono">
                    {entity.first_seen ? new Date(entity.first_seen).toLocaleDateString() : "—"}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm font-mono">
                    {entity.last_seen ? new Date(entity.last_seen).toLocaleDateString() : "—"}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={6} className="p-0">
                  <EmptyState
                    icon={Database}
                    title="No entities found"
                    description={filter ? "Try adjusting your filter." : "Entities will appear after meetings are processed."}
                  />
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </PageShell>
  );
}
