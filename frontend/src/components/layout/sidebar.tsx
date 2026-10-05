"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Activity,
  ListTodo,
  Layers,
  Server,
  CalendarClock,
  AlertOctagon,
  LineChart,
  LogOut,
  Radio,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useCurrentUser } from "@/lib/api-hooks";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/live", label: "Live Console", icon: Activity, badge: "Flower" },
  { href: "/tasks", label: "Task Backlog", icon: ListTodo },
  { href: "/queues", label: "Queues", icon: Layers },
  { href: "/workers", label: "Worker Fleet", icon: Server },
  { href: "/schedules", label: "Schedules", icon: CalendarClock },
  { href: "/dlq", label: "Dead Letter Queue", icon: AlertOctagon },
  { href: "/metrics", label: "Analytics", icon: LineChart, badge: "Grafana" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { data: user } = useCurrentUser();

  const handleLogout = async () => {
    try {
      await apiClient.post("/auth/logout");
    } finally {
      window.location.href = "/login";
    }
  };

  return (
    <aside className="w-64 border-r border-border bg-card/60 backdrop-blur-md flex flex-col h-screen fixed left-0 top-0 z-30">
      <div className="h-16 flex items-center px-6 border-b border-border gap-3">
        <div className="h-8 w-8 rounded-lg bg-primary text-primary-foreground flex items-center justify-center font-bold text-lg shadow-sm">
          TE
        </div>
        <div className="flex flex-col">
          <span className="font-semibold text-sm tracking-tight text-foreground">Task Engine</span>
          <span className="text-[10px] text-muted-foreground font-mono flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
            v5.0 Engine Live
          </span>
        </div>
      </div>

      <div className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all group border border-transparent",
                isActive
                  ? "bg-primary text-primary-foreground shadow-sm hover:bg-primary-foreground hover:text-primary hover:border-primary"
                  : "text-muted-foreground hover:bg-primary hover:text-primary-foreground"
              )}
            >
              <div className="flex items-center gap-3">
                <Icon
                  className={cn(
                    "w-4 h-4 transition-colors",
                    isActive
                      ? "text-primary-foreground group-hover:text-primary"
                      : "text-muted-foreground group-hover:text-primary-foreground"
                  )}
                />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span
                  className={cn(
                    "text-[10px] uppercase font-mono px-1.5 py-0.5 rounded-full font-semibold transition-colors",
                    isActive
                      ? "bg-primary-foreground/20 text-primary-foreground group-hover:bg-primary/20 group-hover:text-primary"
                      : "bg-muted text-muted-foreground group-hover:bg-primary-foreground/20 group-hover:text-primary-foreground"
                  )}
                >
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </div>

      <div className="p-4 border-t border-border flex flex-col gap-2">
        {user && (
          <div className="flex items-center gap-2.5 px-3 py-2 bg-muted/40 rounded-lg border border-border/50">
            <div className="w-7 h-7 rounded-full bg-primary/20 text-primary font-bold flex items-center justify-center text-xs uppercase shrink-0">
              {user.username ? user.username[0] : (user.principal_id ? user.principal_id[0] : "U")}
            </div>
            <div className="flex flex-col min-w-0">
              <span className="text-xs font-semibold truncate text-foreground">
                {user.username || user.principal_id}
              </span>
              <span className="text-[10px] text-muted-foreground truncate font-mono">
                tenant: {user.tenant_id || "default"}
              </span>
            </div>
          </div>
        )}
        <div className="flex items-center justify-between text-xs text-muted-foreground px-2 py-1 bg-muted/40 rounded-md">
          <span className="flex items-center gap-1.5">
            <Radio className="w-3.5 h-3.5 text-emerald-500" />
            WebSocket Live
          </span>
          <span className="font-mono text-[10px]">60 FPS</span>
        </div>
        <button
          onClick={handleLogout}
          className="flex items-center gap-2.5 w-full px-3 py-2 text-xs font-medium text-destructive hover:bg-destructive hover:text-destructive-foreground border border-transparent hover:border-destructive rounded-lg transition-all cursor-pointer group"
        >
          <LogOut className="w-4 h-4 transition-colors group-hover:text-destructive-foreground" />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
}
