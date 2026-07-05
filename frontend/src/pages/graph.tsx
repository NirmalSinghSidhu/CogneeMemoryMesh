import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { useGetGraph, useGetGraphNode, getGetGraphNodeQueryKey } from "@workspace/api-client-react";
import { PageShell, HeroBanner, SurfaceCard } from "@/components/page-shell";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import ForceGraph2D, { type ForceGraphMethods, type NodeObject, type LinkObject } from "react-force-graph-2d";
import { forceCollide } from "d3-force";
import { EntityTypeBadge } from "@/components/badges";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { ZoomIn, ZoomOut, Maximize2, Network } from "lucide-react";
import { Button } from "@/components/ui/button";

const NODE_COLORS: Record<string, string> = {
  person: "#06b6d4",
  project: "#8b5cf6",
  decision: "#f59e0b",
  task: "#10b981",
  topic: "#6366f1",
  risk: "#ef4444",
  blocker: "#f97316",
  document: "#84cc16",
  question: "#ec4899",
  deadline: "#14b8a6",
  meeting: "#3b82f6",
};

type GraphNode = NodeObject & {
  id: string;
  label: string;
  type: string;
  weight: number;
  color: string;
  val: number;
};

type GraphLink = LinkObject & {
  name?: string;
};

function nodeRadius(node: GraphNode, relSize = 4): number {
  return Math.sqrt(Math.max(node.val, 1)) * relSize;
}

function truncateLabel(label: string, maxLen = 22): string {
  if (label.length <= maxLen) return label;
  return `${label.slice(0, maxLen - 1)}…`;
}

export default function Graph() {
  const [filter, setFilter] = useState("");
  const { data, isLoading } = useGetGraph();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [hoverNode, setHoverNode] = useState<GraphNode | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<ForceGraphMethods<GraphNode, GraphLink> | undefined>(undefined);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  const { data: selectedNode } = useGetGraphNode(selectedNodeId as string, {
    query: { enabled: !!selectedNodeId, queryKey: getGetGraphNodeQueryKey(selectedNodeId as string) },
  });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const updateSize = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };

    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const graphData = data || { nodes: [], edges: [] };
  const filterLower = filter.trim().toLowerCase();

  const { gData, legendTypes } = useMemo(() => {
    const filteredNodes = filterLower
      ? graphData.nodes.filter((n) => (n.label || "").toLowerCase().includes(filterLower))
      : graphData.nodes;
    const nodeIdSet = new Set(filteredNodes.map((n) => n.id));
    const filteredEdges = graphData.edges.filter(
      (e) => nodeIdSet.has(e.source) && nodeIdSet.has(e.target)
    );

    const types = new Set<string>();
    const nodes: GraphNode[] = filteredNodes.map((n) => {
      types.add(n.type);
      const val = Math.min(12, Math.max(2, Math.sqrt(n.weight || 1) * 2.5));
      return {
        ...n,
        val,
        color: n.color || NODE_COLORS[n.type] || "#94a3b8",
      };
    });

    return {
      gData: {
        nodes,
        links: filteredEdges.map((e) => ({
          source: e.source,
          target: e.target,
          name: e.relationship,
        })),
      },
      legendTypes: Array.from(types).sort(),
      filteredNodes,
      filteredEdges,
    };
  }, [graphData, filterLower]);

  const filteredCount = gData.nodes.length;
  const totalNodes = graphData.nodes.length;
  const filteredEdgesCount = gData.links.length;
  const totalEdges = graphData.edges.length;

  useEffect(() => {
    const fg = graphRef.current;
    if (!fg) return;

    fg.d3Force("charge")?.strength(-280);
    fg.d3Force("link")?.distance(90).strength(0.4);
    fg.d3Force(
      "collision",
      forceCollide<GraphNode>().radius((node) => nodeRadius(node, 4) + 14)
    );
    fg.d3Force("center")?.strength(0.04);
  }, [gData]);

  const fitGraph = useCallback(() => {
    graphRef.current?.zoomToFit(400, 60);
  }, []);

  useEffect(() => {
    if (gData.nodes.length === 0) return;
    const timer = setTimeout(fitGraph, 600);
    return () => clearTimeout(timer);
  }, [gData, fitGraph]);

  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNodeId(node.id);
  }, []);

  const handleNodeHover = useCallback((node: GraphNode | null) => {
    setHoverNode(node);
    if (containerRef.current) {
      containerRef.current.style.cursor = node ? "pointer" : "grab";
    }
  }, []);

  const paintNode = useCallback(
    (node: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const r = nodeRadius(node, 4);
      const isHovered = hoverNode?.id === node.id;
      const isSelected = selectedNodeId === node.id;
      const x = node.x ?? 0;
      const y = node.y ?? 0;

      ctx.beginPath();
      ctx.arc(x, y, r, 0, 2 * Math.PI);
      ctx.fillStyle = node.color;
      ctx.fill();

      if (isHovered || isSelected) {
        ctx.strokeStyle = isSelected ? "#ffffff" : "rgba(255,255,255,0.85)";
        ctx.lineWidth = (isSelected ? 2.5 : 1.5) / globalScale;
        ctx.stroke();
      }

      if (globalScale >= 0.35) {
        const fontSize = Math.max(10 / globalScale, 3);
        ctx.font = `${fontSize}px ui-sans-serif, system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillStyle = isHovered || isSelected ? "#f8fafc" : "rgba(226,232,240,0.9)";
        ctx.fillText(truncateLabel(node.label), x, y + r + 2 / globalScale);
      }
    },
    [hoverNode, selectedNodeId]
  );

  const linkColor = useCallback(
    (link: GraphLink) => {
      if (!hoverNode) return "rgba(148,163,184,0.22)";
      const source = link.source as GraphNode;
      const target = link.target as GraphNode;
      return source.id === hoverNode.id || target.id === hoverNode.id
        ? "rgba(148,163,184,0.7)"
        : "rgba(148,163,184,0.08)";
    },
    [hoverNode]
  );

  const linkWidth = useCallback(
    (link: GraphLink) => {
      if (!hoverNode) return 0.8;
      const source = link.source as GraphNode;
      const target = link.target as GraphNode;
      return source.id === hoverNode.id || target.id === hoverNode.id ? 1.5 : 0.5;
    },
    [hoverNode]
  );

  if (isLoading) {
    return (
      <div className="p-8 h-full flex flex-col">
        <Skeleton className="h-10 w-64 mb-4" />
        <Skeleton className="flex-1 w-full" />
      </div>
    );
  }

  return (
    <PageShell maxWidth="full" className="h-[calc(100vh-0px)] flex flex-col p-3 md:p-4">
      <HeroBanner
        compact
        eyebrow="Graph View"
        eyebrowIcon={Network}
        title="Knowledge Graph"
        description={`${filteredCount}${filterLower ? ` / ${totalNodes}` : ""} nodes · ${filteredEdgesCount}${filterLower ? ` / ${totalEdges}` : ""} edges`}
        pills={
          <span
            className={`text-[10px] px-2 py-0.5 rounded-md border uppercase tracking-wider font-mono ${
              (graphData as { source?: string }).source === "cognee"
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                : "bg-amber-500/10 border-amber-500/30 text-amber-400"
            }`}
          >
            {(graphData as { source?: string }).source || "sql"}
          </span>
        }
        actions={
          <div className="w-44 sm:w-52">
            <Input
              placeholder="Filter nodes..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="h-8 text-xs bg-background/60"
            />
          </div>
        }
      />

      <SurfaceCard className="flex-1 min-h-0 overflow-hidden relative">
        <div ref={containerRef} className="absolute inset-0">
        {gData.nodes.length === 0 ? (
          <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
            No nodes match your filter.
          </div>
        ) : (
          <ForceGraph2D
            ref={graphRef}
            width={dimensions.width}
            height={dimensions.height}
            graphData={gData}
            onNodeClick={handleNodeClick}
            onNodeHover={handleNodeHover}
            onEngineStop={fitGraph}
            nodeCanvasObject={paintNode}
            linkColor={linkColor}
            linkWidth={linkWidth}
            nodePointerAreaPaint={(node, color, ctx) => {
              const r = nodeRadius(node as GraphNode, 4) + 6;
              ctx.beginPath();
              ctx.arc(node.x ?? 0, node.y ?? 0, r, 0, 2 * Math.PI);
              ctx.fillStyle = color;
              ctx.fill();
            }}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={0.92}
            linkDirectionalParticles={hoverNode ? 2 : 0}
            linkDirectionalParticleWidth={2}
            cooldownTicks={120}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.35}
            enableNodeDrag
            enableZoomInteraction
            enablePanInteraction
            backgroundColor="transparent"
          />
        )}

        {legendTypes.length > 0 && (
          <div className="absolute bottom-3 left-3 flex flex-wrap gap-2 max-w-[70%] pointer-events-none">
            {legendTypes.map((type) => (
              <span
                key={type}
                className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider font-mono bg-background/80 backdrop-blur-sm border border-border/50 rounded px-2 py-1"
              >
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: NODE_COLORS[type] || "#94a3b8" }}
                />
                {type}
              </span>
            ))}
          </div>
        )}

        <div className="absolute top-3 right-3 flex gap-1">
          <Button
            variant="secondary"
            size="icon"
            className="h-8 w-8 bg-background/80 backdrop-blur-sm"
            onClick={() => graphRef.current?.zoom(graphRef.current.zoom() * 1.4, 400)}
            title="Zoom in"
          >
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button
            variant="secondary"
            size="icon"
            className="h-8 w-8 bg-background/80 backdrop-blur-sm"
            onClick={() => graphRef.current?.zoom(graphRef.current.zoom() / 1.4, 400)}
            title="Zoom out"
          >
            <ZoomOut className="h-4 w-4" />
          </Button>
          <Button
            variant="secondary"
            size="icon"
            className="h-8 w-8 bg-background/80 backdrop-blur-sm"
            onClick={fitGraph}
            title="Fit to view"
          >
            <Maximize2 className="h-4 w-4" />
          </Button>
        </div>

        <p className="absolute bottom-3 right-3 text-[10px] text-muted-foreground/70 pointer-events-none z-10">
          Scroll to zoom • Drag nodes • Click for details
        </p>
        </div>
      </SurfaceCard>

      <Sheet open={!!selectedNodeId} onOpenChange={(open) => !open && setSelectedNodeId(null)}>
        <SheetContent className="w-[400px] sm:w-[540px] overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-3">
              {selectedNode ? selectedNode.label : "Loading..."}
              {selectedNode && <EntityTypeBadge type={selectedNode.type} />}
            </SheetTitle>
            <SheetDescription>
              {selectedNode?.description || "No description available."}
            </SheetDescription>
          </SheetHeader>

          {selectedNode && (
            <div className="mt-8 space-y-6">
              <div className="space-y-3">
                <h4 className="text-sm font-medium border-b border-border pb-1">Connections</h4>
                <div className="space-y-2">
                  {selectedNode.connections.length === 0 && (
                    <p className="text-xs text-muted-foreground">No connections for this node.</p>
                  )}
                  {selectedNode.connections.map((c, i) => {
                    const isSource = c.source === selectedNode.id;
                    const otherNodeId = isSource ? c.target : c.source;
                    const arrowMatch = c.relationship.match(/→\s*(.+)$/);
                    const otherLabel = arrowMatch?.[1] || otherNodeId;
                    const relLabel = arrowMatch
                      ? c.relationship.replace(/\s*→\s*.+$/, "")
                      : c.relationship;
                    return (
                      <div
                        key={i}
                        className="text-sm flex items-start gap-2 bg-accent/30 p-2 rounded border border-border/30"
                      >
                        <span className="font-mono text-xs text-muted-foreground whitespace-nowrap pt-0.5">
                          {isSource ? "OUT:" : "IN:"} {relLabel}
                        </span>
                        <span className="truncate" title={otherNodeId}>
                          {otherLabel}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {selectedNode.meetings && selectedNode.meetings.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-sm font-medium border-b border-border pb-1">Referenced In Meetings</h4>
                  <div className="space-y-2">
                    {selectedNode.meetings.map((m) => (
                      <div key={m.id} className="text-sm bg-accent/30 p-2 rounded border border-border/30">
                        <div className="font-medium">{m.title}</div>
                        <div className="text-xs text-muted-foreground font-mono mt-1">
                          {new Date(m.date).toLocaleDateString()}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </PageShell>
  );
}
