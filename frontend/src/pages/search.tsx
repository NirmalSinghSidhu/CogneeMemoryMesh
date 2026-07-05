import { useState } from "react";
import { useSearchMemory } from "@workspace/api-client-react";
import { CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Search as SearchIcon, Network, Sparkles, Filter } from "lucide-react";
import { EntityTypeBadge } from "@/components/badges";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageShell, HeroBanner, SurfaceCard, EmptyState } from "@/components/page-shell";

export default function Search() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"hybrid" | "semantic" | "graph">("hybrid");
  const searchMutation = useSearchMemory();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    searchMutation.mutate({ data: { query, mode } });
  };

  return (
    <PageShell maxWidth="5xl" className="space-y-8">
      <HeroBanner
        centered
        eyebrow="Recall"
        eyebrowIcon={Sparkles}
        title="Search Memory"
        description="Query across all meetings, decisions, and entities. MemoryMesh understands context, relationships, and semantics — not just keywords."
      />

      <SurfaceCard className="sticky top-4 z-10 shadow-md">
        <CardContent className="p-4 md:p-5">
          <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <Input
                className="pl-10 h-12 text-base bg-background/80"
                placeholder="What was decided about the auth migration?"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <Button type="submit" className="h-12 px-8 shrink-0" disabled={searchMutation.isPending || !query.trim()}>
              {searchMutation.isPending ? "Searching..." : "Search"}
            </Button>
          </form>

          <div className="flex items-center mt-4 px-1">
            <Tabs value={mode} onValueChange={(v) => setMode(v as typeof mode)}>
              <TabsList className="bg-background/60">
                <TabsTrigger value="hybrid" className="gap-2 text-xs">
                  <Filter className="w-3 h-3" /> Hybrid
                </TabsTrigger>
                <TabsTrigger value="semantic" className="gap-2 text-xs">
                  <Sparkles className="w-3 h-3" /> Semantic
                </TabsTrigger>
                <TabsTrigger value="graph" className="gap-2 text-xs">
                  <Network className="w-3 h-3" /> Graph
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </CardContent>
      </SurfaceCard>

      <div className="space-y-6">
        {searchMutation.isPending && (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <SurfaceCard key={i}>
                <CardContent className="p-6 space-y-3">
                  <Skeleton className="h-6 w-1/3" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-2/3" />
                </CardContent>
              </SurfaceCard>
            ))}
          </div>
        )}

        {searchMutation.data && (
          <div className="space-y-6">
            <div className="text-xs font-mono text-muted-foreground flex justify-between px-1">
              <span>FOUND {searchMutation.data.total} RESULTS</span>
              <span>MODE: {searchMutation.data.search_mode}</span>
            </div>

            {searchMutation.data.results.length > 0 ? (
              <div className="grid gap-3">
                {searchMutation.data.results.map((hit, i) => (
                  <SurfaceCard key={`${hit.id}-${i}`} hover>
                    <CardContent className="p-5 md:p-6">
                      <div className="flex justify-between items-start gap-4 mb-3">
                        <div className="flex items-center gap-3 min-w-0">
                          <EntityTypeBadge type={hit.type || hit.entity_type || "document"} />
                          <h3 className="text-base font-medium truncate">{hit.title}</h3>
                        </div>
                        <div className="text-xs font-mono bg-muted/40 px-2 py-1 rounded-md text-muted-foreground shrink-0">
                          {hit.score.toFixed(3)}
                        </div>
                      </div>

                      <p className="text-muted-foreground text-sm leading-relaxed">{hit.excerpt}</p>

                      {hit.meeting_title && (
                        <div className="text-xs font-mono text-muted-foreground flex flex-wrap gap-3 pt-3 mt-3 border-t border-border/40">
                          <span className="text-primary/80">SOURCE: {hit.meeting_title}</span>
                          {hit.date && <span>DATE: {new Date(hit.date).toLocaleDateString()}</span>}
                        </div>
                      )}
                    </CardContent>
                  </SurfaceCard>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={SearchIcon}
                title="No results found"
                description={`No relevant memories matched "${searchMutation.data.query}". Try a different query or search mode.`}
              />
            )}
          </div>
        )}
      </div>
    </PageShell>
  );
}
