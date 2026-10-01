import React from "react";
import { Sidebar } from "@/components/layout/sidebar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex bg-background">
      <Sidebar />
      <main className="flex-1 ml-64 min-h-screen flex flex-col">
        <header className="h-16 border-b border-border px-8 flex items-center justify-between bg-card/40 backdrop-blur sticky top-0 z-20">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="font-semibold text-foreground">Console</span>
            <span>/</span>
            <span className="capitalize">Live Operational View</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="h-2 w-2 rounded-full bg-emerald-500" />
            <span className="text-xs font-mono text-muted-foreground">Backend Connected</span>
          </div>
        </header>
        <div className="p-8 flex-1 overflow-y-auto">{children}</div>
      </main>
    </div>
  );
}
