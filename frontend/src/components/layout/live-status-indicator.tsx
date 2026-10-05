"use client";

import React from "react";
import { useWebSocketSubscription } from "@/lib/use-websocket";
import { Radio, WifiOff, RefreshCw } from "lucide-react";

export function LiveStatusIndicator() {
  const { isConnected, isConnecting, lastEvent } = useWebSocketSubscription({
    channel: "live",
    autoInvalidate: true,
  });

  return (
    <div className="flex items-center gap-2">
      {lastEvent && (
        <span className="hidden md:inline-block text-[11px] font-mono text-muted-foreground bg-muted/60 px-2 py-0.5 rounded border border-border">
          {lastEvent.type}
        </span>
      )}
      {isConnected ? (
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 text-xs font-mono">
          <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>Live WS Sync</span>
        </div>
      ) : isConnecting ? (
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-600 text-xs font-mono">
          <RefreshCw className="h-3 w-3 animate-spin text-amber-500" />
          <span>Reconnecting...</span>
        </div>
      ) : (
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-muted border border-border text-muted-foreground text-xs font-mono">
          <div className="h-2 w-2 rounded-full bg-muted-foreground" />
          <span>Polling Fallback</span>
        </div>
      )}
    </div>
  );
}
