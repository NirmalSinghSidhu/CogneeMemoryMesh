import { useState } from "react";
import { Link, useLocation } from "wouter";
import {
  Activity,
  BrainCircuit,
  Calendar,
  Database,
  GitMerge,
  LayoutDashboard,
  MessageSquare,
  Network,
  Search,
  Menu,
  Settings,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/auth-context";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/meetings", label: "Meetings", icon: Calendar },
  { href: "/graph", label: "Knowledge Graph", icon: Network },
  { href: "/search", label: "Search", icon: Search },
  { href: "/chat", label: "AI Chat", icon: MessageSquare },
  { href: "/decisions", label: "Decisions", icon: GitMerge },
  { href: "/timeline", label: "Timeline", icon: Activity },
  { href: "/memory", label: "Memory Control", icon: BrainCircuit },
  { href: "/entities", label: "Entities", icon: Database },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const [location] = useLocation();
  const [, setLocation] = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const { user, tenant, logout } = useAuth();

  const handleLogout = () => {
    logout();
    setLocation("/login");
  };

  return (
    <div
      className={cn(
        "flex flex-col border-r border-border/60 bg-sidebar/95 backdrop-blur-md h-screen transition-all duration-300 shrink-0",
        collapsed ? "w-16" : "w-64"
      )}
    >
      <div className="flex h-14 items-center justify-between px-3 border-b border-border/60">
        {!collapsed && (
          <div className="flex items-center gap-2.5 font-bold text-lg tracking-tight pl-1">
            <div className="p-1.5 rounded-lg bg-primary/15 border border-primary/20">
              <BrainCircuit className="w-4 h-4 text-primary" />
            </div>
            <span className="bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
              MemoryMesh
            </span>
          </div>
        )}
        <Button
          variant="ghost"
          size="icon"
          className={cn("h-8 w-8 text-muted-foreground", collapsed && "mx-auto")}
          onClick={() => setCollapsed(!collapsed)}
        >
          <Menu className="w-4 h-4" />
        </Button>
      </div>

      <nav className="flex-1 overflow-y-auto overflow-x-hidden py-3 flex flex-col gap-0.5 px-2 scrollbar-sidebar">
        {NAV_ITEMS.map((item) => {
          const active =
            location === item.href || (item.href !== "/" && location.startsWith(item.href));
          return (
            <Link key={item.href} href={item.href}>
              <div
                className={cn(
                  "relative flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-150 cursor-pointer text-sm font-medium",
                  active
                    ? "bg-accent/50 text-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent/35"
                )}
              >
                {active && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-0.5 rounded-full bg-primary" />
                )}
                <item.icon
                  className={cn("w-4 h-4 shrink-0", active ? "text-primary" : "text-muted-foreground")}
                />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </div>
            </Link>
          );
        })}
      </nav>

      {!collapsed && (
        <div className="p-4 border-t border-border/60 space-y-3 bg-card/20">
          {user && (
            <div className="text-xs space-y-0.5 px-1">
              <p className="font-medium text-foreground truncate">{user.name}</p>
              <p className="text-muted-foreground truncate">{tenant?.name}</p>
            </div>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start text-muted-foreground hover:text-foreground"
            onClick={handleLogout}
          >
            <LogOut className="w-4 h-4 mr-2" />
            Sign out
          </Button>
          <div className="text-[10px] font-mono text-muted-foreground flex items-center justify-between pt-1 px-1">
            <span>SYS_STATUS</span>
            <span className="text-emerald-400 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block animate-pulse" />
              ONLINE
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

export function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto overflow-x-hidden page-mesh-bg scrollbar-sidebar">{children}</main>
    </div>
  );
}
