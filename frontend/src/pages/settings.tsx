import { useState, useEffect } from "react";
import { CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { CheckCircle2, Circle, Loader2, Zap, Brain, Cpu, Settings2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { authFetch } from "@/lib/auth";
import { PageShell, HeroBanner, SurfaceCard } from "@/components/page-shell";

interface Provider {
  id: string;
  label: string;
  model: string;
  available: boolean;
}

interface LLMSettings {
  active_provider: string;
  all_providers: Provider[];
}

const PROVIDER_ICONS: Record<string, React.ReactNode> = {
  gemini: <Brain className="w-5 h-5" />,
  groq: <Zap className="w-5 h-5" />,
  openai: <Cpu className="w-5 h-5" />,
};

const PROVIDER_DESCRIPTIONS: Record<string, string> = {
  gemini: "Google Gemini 2.5 Flash — fast, multimodal, great for complex reasoning",
  groq: "Groq Llama 3.3 70B — ultra-fast inference, excellent for quick Q&A",
  openai: "OpenAI GPT-4.1 Mini — reliable, well-rounded, strong instruction following",
};

export default function Settings() {
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    authFetch("/api/settings/llm")
      .then((r) => r.json())
      .then((d) => {
        setSettings(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const switchProvider = async (id: string) => {
    setSwitching(id);
    setError(null);
    setSuccessMsg(null);
    try {
      const r = await authFetch("/api/settings/llm", {
        method: "POST",
        body: JSON.stringify({ provider: id }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || "Failed to switch");
      setSettings((prev) => (prev ? { ...prev, active_provider: id } : prev));
      setSuccessMsg(`Switched to ${data.label}`);
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to switch provider");
    } finally {
      setSwitching(null);
    }
  };

  return (
    <PageShell maxWidth="4xl" className="space-y-6">
      <HeroBanner
        eyebrow="Configuration"
        eyebrowIcon={Settings2}
        title="Settings"
        description="Configure your AI provider and preferences."
      />

      <SurfaceCard>
        <CardHeader>
          <CardTitle className="text-base">LLM Provider</CardTitle>
          <CardDescription>
            Choose which AI model powers the chat and memory features. Gemini is the default.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading && (
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading providers…
            </div>
          )}

          {!loading &&
            settings?.all_providers.map((p) => {
              const isActive = settings.active_provider === p.id;
              const isSwitching = switching === p.id;

              return (
                <div
                  key={p.id}
                  className={cn(
                    "flex items-start gap-4 p-4 rounded-xl border transition-all duration-150",
                    isActive
                      ? "border-primary/40 bg-primary/10 shadow-sm"
                      : p.available
                        ? "border-border/40 bg-card/30 hover:bg-card/50 hover:border-border/60 cursor-pointer"
                        : "border-border/30 bg-card/20 opacity-50 cursor-not-allowed"
                  )}
                  onClick={() => !isActive && p.available && !switching && switchProvider(p.id)}
                >
                  <div className={cn("mt-0.5", isActive ? "text-primary" : "text-muted-foreground")}>
                    {PROVIDER_ICONS[p.id] ?? <Cpu className="w-5 h-5" />}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm">{p.label}</span>
                      {isActive && (
                        <span className="text-[10px] bg-primary/20 text-primary px-2 py-0.5 rounded-full font-mono uppercase tracking-wider">
                          Active
                        </span>
                      )}
                      {!p.available && (
                        <span className="text-[10px] bg-muted/50 text-muted-foreground px-2 py-0.5 rounded-full font-mono uppercase tracking-wider">
                          No key
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                      {PROVIDER_DESCRIPTIONS[p.id]}
                    </p>
                    <p className="text-xs font-mono text-muted-foreground/60 mt-1.5">model: {p.model}</p>
                  </div>

                  <div className="shrink-0">
                    {isSwitching ? (
                      <Loader2 className="w-5 h-5 animate-spin text-primary" />
                    ) : isActive ? (
                      <CheckCircle2 className="w-5 h-5 text-primary" />
                    ) : (
                      <Circle className="w-5 h-5 text-muted-foreground/40" />
                    )}
                  </div>
                </div>
              );
            })}

          {successMsg && (
            <div className="flex items-center gap-2 text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 rounded-lg">
              <CheckCircle2 className="w-4 h-4" /> {successMsg}
            </div>
          )}
          {error && (
            <div className="text-sm text-rose-400 bg-rose-500/10 border border-rose-500/20 px-3 py-2 rounded-lg">
              {error}
            </div>
          )}
        </CardContent>
      </SurfaceCard>

      <SurfaceCard>
        <CardHeader>
          <CardTitle className="text-base">API Keys</CardTitle>
          <CardDescription>
            Keys are read from the project root .env file. Restart the backend after adding or updating a key.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-1">
          {["GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY"].map((key) => {
            const provId = key.replace("_API_KEY", "").toLowerCase();
            const prov = settings?.all_providers.find((p) => p.id === provId);
            return (
              <div
                key={key}
                className="flex items-center justify-between py-3 border-b border-border/30 last:border-0"
              >
                <span className="text-sm font-mono text-muted-foreground">{key}</span>
                <span
                  className={cn(
                    "text-[10px] px-2 py-0.5 rounded-full font-mono uppercase tracking-wider",
                    prov?.available
                      ? "bg-emerald-500/15 text-emerald-400"
                      : "bg-muted/30 text-muted-foreground"
                  )}
                >
                  {prov?.available ? "Configured" : "Not set"}
                </span>
              </div>
            );
          })}
        </CardContent>
      </SurfaceCard>
    </PageShell>
  );
}
