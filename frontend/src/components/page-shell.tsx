import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { LucideIcon } from "lucide-react";

type MaxWidth = "4xl" | "5xl" | "6xl" | "7xl" | "full";

const maxWidthClass: Record<MaxWidth, string> = {
  "4xl": "max-w-4xl",
  "5xl": "max-w-5xl",
  "6xl": "max-w-6xl",
  "7xl": "max-w-7xl",
  full: "max-w-full",
};

export function PageShell({
  children,
  className,
  maxWidth = "7xl",
}: {
  children: ReactNode;
  className?: string;
  maxWidth?: MaxWidth;
}) {
  return (
    <div className={cn("p-6 md:p-8 mx-auto w-full", maxWidthClass[maxWidth], className)}>
      {children}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  meta,
  centered,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
  centered?: boolean;
}) {
  return (
    <div
      className={cn(
        "mb-8",
        centered ? "text-center space-y-3" : "flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"
      )}
    >
      <div className={cn("space-y-1.5", centered && "max-w-2xl mx-auto")}>
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight">{title}</h1>
        {description && (
          <p className="text-sm md:text-base text-muted-foreground leading-relaxed">{description}</p>
        )}
        {meta}
      </div>
      {actions && <div className={cn("shrink-0", centered && "flex justify-center")}>{actions}</div>}
    </div>
  );
}

export function HeroBanner({
  eyebrow,
  eyebrowIcon: EyebrowIcon,
  title,
  description,
  actions,
  pills,
  centered = false,
  compact = false,
  className,
}: {
  eyebrow?: string;
  eyebrowIcon?: LucideIcon;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  pills?: ReactNode;
  centered?: boolean;
  compact?: boolean;
  className?: string;
}) {
  if (compact) {
    return (
      <div className={cn("gradient-hero rounded-xl px-3 py-2.5 md:px-4 md:py-3 mb-3 shrink-0", className)}>
        <div className="relative flex flex-wrap items-center gap-x-3 gap-y-2 justify-between">
          <div className="flex items-center gap-2.5 min-w-0">
            {EyebrowIcon && (
              <div className="p-1.5 rounded-md bg-primary/10 border border-primary/20 shrink-0">
                <EyebrowIcon className="w-3.5 h-3.5 text-primary" />
              </div>
            )}
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-sm md:text-base font-semibold tracking-tight">{title}</h1>
                {eyebrow && (
                  <span className="text-[10px] font-mono text-primary/80 uppercase tracking-wider hidden sm:inline">
                    {eyebrow}
                  </span>
                )}
              </div>
              {description && (
                <p className="text-xs text-muted-foreground truncate max-w-md mt-0.5 hidden md:block">
                  {description}
                </p>
              )}
            </div>
          </div>
          {(actions || pills) && (
            <div className="flex flex-wrap items-center gap-2 shrink-0 ml-auto">
              {pills}
              {actions}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "gradient-hero p-6 md:p-8 mb-8",
        centered && "text-center",
        className
      )}
    >
      <div
        className={cn(
          "relative flex flex-col gap-4",
          centered
            ? "items-center max-w-2xl mx-auto"
            : "md:flex-row md:items-end md:justify-between"
        )}
      >
        <div className={cn("space-y-2", centered && "space-y-3")}>
          {eyebrow && (
            <div
              className={cn(
                "flex items-center gap-2 text-xs font-mono text-primary uppercase tracking-widest",
                centered && "justify-center"
              )}
            >
              {EyebrowIcon && <EyebrowIcon className="w-3.5 h-3.5" />}
              {eyebrow}
            </div>
          )}
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">{title}</h1>
          {description && (
            <p className="text-sm text-muted-foreground max-w-xl leading-relaxed">{description}</p>
          )}
        </div>
        {(actions || pills) && (
          <div
            className={cn(
              "flex flex-wrap gap-2 shrink-0",
              centered && "justify-center"
            )}
          >
            {pills}
            {actions}
          </div>
        )}
      </div>
    </div>
  );
}

export function SurfaceCard({
  children,
  className,
  hover = false,
  ...props
}: React.ComponentProps<typeof Card> & { hover?: boolean }) {
  return (
    <Card
      className={cn(
        "surface-card",
        hover && "surface-card-hover cursor-pointer",
        className
      )}
      {...props}
    >
      {children}
    </Card>
  );
}

export function StatCard({
  title,
  value,
  icon: Icon,
  accent = "primary",
}: {
  title: string;
  value: ReactNode;
  icon: React.ComponentType<{ className?: string }>;
  accent?: "primary" | "cyan" | "blue" | "amber" | "emerald" | "rose";
}) {
  const accentMap = {
    primary: "text-primary bg-primary/10 border-primary/20",
    cyan: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
    blue: "text-blue-400 bg-blue-500/10 border-blue-500/20",
    amber: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    emerald: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    rose: "text-rose-400 bg-rose-500/10 border-rose-500/20",
  };

  return (
    <SurfaceCard className="overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <div className={cn("p-2 rounded-lg border", accentMap[accent])}>
          <Icon className="w-4 h-4" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl md:text-3xl font-bold font-mono tracking-tight">{value}</div>
      </CardContent>
    </SurfaceCard>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center rounded-xl border border-dashed border-border/50 bg-card/20">
      <div className="p-4 rounded-full bg-muted/30 mb-4">
        <Icon className="w-8 h-8 text-muted-foreground/60" />
      </div>
      <h3 className="text-base font-medium">{title}</h3>
      {description && (
        <p className="text-sm text-muted-foreground mt-1 max-w-sm">{description}</p>
      )}
    </div>
  );
}

export function SectionCard({
  title,
  description,
  children,
  className,
}: {
  title?: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <SurfaceCard className={className}>
      {(title || description) && (
        <CardHeader>
          {title && <CardTitle>{title}</CardTitle>}
          {description && <CardDescription>{description}</CardDescription>}
        </CardHeader>
      )}
      <CardContent className={!title && !description ? "pt-6" : undefined}>{children}</CardContent>
    </SurfaceCard>
  );
}
