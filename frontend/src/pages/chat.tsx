import { useState, useRef, useEffect } from "react";
import { useGetChatHistory } from "@workspace/api-client-react";
import { PageShell, HeroBanner, SurfaceCard } from "@/components/page-shell";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Send, User, Bot, Zap, Brain, Cpu, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import { authFetch, getApiBase } from "@/lib/auth";

interface Source {
  meeting_title: string;
  date: string;
  entity_type: string;
  entity_name: string;
}

interface Decision {
  id: number;
  title: string;
  status: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  decisions?: Decision[];
  provider?: string;
  streaming?: boolean;
}

const PROVIDER_ICONS: Record<string, React.ReactNode> = {
  gemini: <Brain className="w-3 h-3" />,
  groq: <Zap className="w-3 h-3" />,
  openai: <Cpu className="w-3 h-3" />,
};

const PROVIDER_LABELS: Record<string, string> = {
  gemini: "Gemini",
  groq: "Groq",
  openai: "OpenAI",
};

function MarkdownText({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="space-y-1">
      {lines.map((line, i) => {
        if (line.startsWith("## ")) return <h2 key={i} className="font-bold text-sm mt-2">{line.slice(3)}</h2>;
        if (line.startsWith("### ")) return <h3 key={i} className="font-semibold text-sm mt-1">{line.slice(4)}</h3>;
        if (line.startsWith("- ") || line.startsWith("* ")) return <li key={i} className="ml-3 text-sm list-disc">{renderInline(line.slice(2))}</li>;
        if (line.startsWith("**") && line.endsWith("**")) return <p key={i} className="font-bold text-sm">{line.slice(2, -2)}</p>;
        if (line === "---") return <hr key={i} className="border-border/30 my-1" />;
        if (!line.trim()) return <div key={i} className="h-1" />;
        return <p key={i} className="text-sm leading-relaxed">{renderInline(line)}</p>;
      })}
    </div>
  );
}

function renderInline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**")
      ? <strong key={i}>{p.slice(2, -2)}</strong>
      : p
  );
}

export default function Chat() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [streaming, setStreaming] = useState(false);
  const [activeProvider, setActiveProvider] = useState<string>("gemini");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const { data: history, isLoading } = useGetChatHistory();
  const base = getApiBase();

  // Load provider
  useEffect(() => {
    authFetch("/api/settings/llm")
      .then(r => r.json())
      .then(d => setActiveProvider(d.active_provider))
      .catch(() => {});
  }, []);

  // Pre-fill from history
  useEffect(() => {
    if (history && history.length > 0 && messages.length === 0) {
      setMessages(history.map((m: any) => ({
        role: m.role,
        content: m.content,
        sources: m.sources || [],
      })));
    }
  }, [history]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || streaming) return;

    const userMsg = message.trim();
    setMessage("");
    setMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setStreaming(true);

    // Add empty assistant placeholder
    setMessages(prev => [...prev, { role: "assistant", content: "", streaming: true }]);

    const abort = new AbortController();
    abortRef.current = abort;

    try {
      const token = localStorage.getItem("memorymesh_token");
      const res = await fetch(`${base}/api/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message: userMsg, conversation_id: conversationId, context_limit: 8 }),
        signal: abort.signal,
      });

      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let fullContent = "";
      let sources: Source[] = [];
      let decisions: Decision[] = [];
      let provider = activeProvider;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.error) throw new Error(data.error);
            if (data.provider) { provider = data.provider; setActiveProvider(data.provider); }
            if (data.conversation_id) setConversationId(data.conversation_id);
            if (data.content) {
              fullContent += data.content;
              setMessages(prev => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.streaming) next[next.length - 1] = { ...last, content: fullContent, provider };
                return next;
              });
            }
            if (data.done) {
              sources = data.sources || [];
              decisions = data.decisions_referenced || [];
            }
          } catch {}
        }
      }

      setMessages(prev => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.streaming) {
          next[next.length - 1] = { role: "assistant", content: fullContent, sources, decisions, provider };
        }
        return next;
      });
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setMessages(prev => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.streaming) {
          next[next.length - 1] = { role: "assistant", content: "Sorry, something went wrong. Please try again.", provider: activeProvider };
        }
        return next;
      });
    } finally {
      setStreaming(false);
      abortRef.current = null;
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const latestSources = [...messages].reverse().find(m => m.role === "assistant" && m.sources?.length)?.sources;
  const latestDecisions = [...messages].reverse().find(m => m.role === "assistant" && m.decisions?.length)?.decisions;

  return (
    <PageShell maxWidth="full" className="h-[calc(100vh-0px)] flex flex-col p-3 md:p-4">
      <HeroBanner
        compact
        eyebrow="Assistant"
        eyebrowIcon={MessageSquare}
        title="AI Chat"
        description="Ask about meetings, decisions, or projects."
        pills={
          <span className="inline-flex items-center gap-1.5 text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full font-mono">
            {PROVIDER_ICONS[activeProvider]}
            {PROVIDER_LABELS[activeProvider] ?? activeProvider}
          </span>
        }
      />
      <div className="flex flex-1 min-h-0 gap-3 max-w-7xl mx-auto w-full">
      <SurfaceCard className="flex-1 flex flex-col min-h-0">
        <div className="flex-1 overflow-y-auto p-4 md:p-5 space-y-5" ref={scrollRef}>
          {isLoading && messages.length === 0 && <Skeleton className="h-16 w-3/4" />}

          {messages.length === 0 && !isLoading && (
            <div className="h-full flex flex-col items-center justify-center text-muted-foreground gap-3 py-8">
              <div className="p-4 rounded-full bg-muted/20 border border-border/40">
                <Bot className="w-8 h-8 opacity-50" />
              </div>
              <p className="text-xs text-muted-foreground/70">Start a conversation below</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={cn("flex gap-3 max-w-[85%]", msg.role === "user" ? "ml-auto flex-row-reverse" : "")}>
              <div className={cn(
                "w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5",
                msg.role === "user" ? "bg-blue-500/20 text-blue-400" : "bg-cyan-500/20 text-cyan-500"
              )}>
                {msg.role === "user" ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
              </div>

              <div className="flex flex-col gap-1 min-w-0">
                <div className={cn(
                  "px-4 py-3 rounded-xl text-sm leading-relaxed",
                  msg.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-accent/60 border border-border/40 text-foreground"
                )}>
                  {msg.streaming && !msg.content
                    ? <div className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-bounce" />
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-bounce [animation-delay:0.1s]" />
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-bounce [animation-delay:0.2s]" />
                      </div>
                    : msg.role === "assistant"
                    ? <MarkdownText text={msg.content} />
                    : msg.content
                  }
                </div>

                {msg.role === "assistant" && msg.provider && !msg.streaming && (
                  <div className="flex items-center gap-1 text-xs text-muted-foreground/50 px-1">
                    {PROVIDER_ICONS[msg.provider]}
                    <span>{PROVIDER_LABELS[msg.provider] ?? msg.provider}</span>
                  </div>
                )}

                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-1 px-1 text-xs text-muted-foreground/60 font-mono">
                    SOURCES: {msg.sources.map(s => s.meeting_title).join(" · ")}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="p-3 md:p-4 border-t border-border/40 bg-background/30 shrink-0">
          <form onSubmit={handleSend} className="flex gap-2">
            <Input
              ref={inputRef}
              placeholder="Ask MemoryMesh…"
              value={message}
              onChange={e => setMessage(e.target.value)}
              className="flex-1 h-10 bg-background border-border/50"
              disabled={streaming}
            />
            <Button
              type="submit"
              size="icon"
              className="h-10 w-10 bg-blue-600 hover:bg-blue-500 text-white shrink-0"
              disabled={streaming || !message.trim()}
            >
              <Send className="w-4 h-4" />
            </Button>
          </form>
        </div>
      </SurfaceCard>

      {(latestSources?.length || latestDecisions?.length) ? (
        <SurfaceCard className="w-72 hidden lg:flex flex-col min-h-0">
          <div className="border-b border-border/40 px-4 py-3">
            <h3 className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Context Sources</h3>
          </div>
          <ScrollArea className="flex-1">
            <div className="p-3 space-y-3">
              {latestSources?.map((src, i) => (
                <div key={i} className="space-y-0.5 p-2.5 bg-accent/30 rounded border border-border/30">
                  <div className="text-xs font-mono text-blue-400">[{i + 1}] {src.entity_type.toUpperCase()}</div>
                  <div className="text-sm font-medium leading-tight">{src.entity_name || src.meeting_title}</div>
                  <div className="text-xs text-muted-foreground">{new Date(src.date).toLocaleDateString()}</div>
                </div>
              ))}
              {latestDecisions && latestDecisions.length > 0 && (
                <div className="pt-2 border-t border-border/40">
                  <div className="text-xs font-mono text-muted-foreground mb-2">DECISIONS</div>
                  {latestDecisions.map(d => (
                    <div key={d.id} className="text-xs bg-amber-500/10 text-amber-400 p-2 rounded mb-1.5 border border-amber-500/20">
                      {d.title}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </ScrollArea>
        </SurfaceCard>
      ) : null}
      </div>
    </PageShell>
  );
}
