"use client";

import React from "react";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useWorkers, useDrainWorker } from "@/lib/api-hooks";
import { Server, PowerOff, RefreshCw, Cpu, Activity } from "lucide-react";

export default function WorkersPage() {
  const { data, isLoading, refetch } = useWorkers();
  const drainWorker = useDrainWorker();

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Worker Fleet</h1>
          <p className="text-sm text-muted-foreground">
            Distributed execution nodes, slot capacities, and health telemetry.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()} className="gap-2">
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh Fleet
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {isLoading ? (
          <div className="col-span-full p-12 text-center text-sm text-muted-foreground">
            Polling worker nodes...
          </div>
        ) : !data?.items.length ? (
          <div className="col-span-full p-12 text-center text-sm text-muted-foreground">
            No active workers connected.
          </div>
        ) : (
          data.items.map((w) => {
            const isOnline = w.status === "active";
            const util =
              w.concurrency > 0
                ? Math.round((w.active_task_count / w.concurrency) * 100)
                : 0;
            return (
              <Card key={w.worker_id} className="flex flex-col justify-between">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Server className="w-4 h-4 text-blue-500" />
                      <CardTitle className="text-sm font-semibold font-mono truncate max-w-[200px]" title={w.worker_id}>
                        {w.worker_id}
                      </CardTitle>
                    </div>
                    <Badge variant={isOnline ? "success" : "warning"}>
                      {w.status}
                    </Badge>
                  </div>
                  <CardDescription className="text-xs font-mono">
                    {w.hostname} • PID {w.process_id}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-1.5">
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-muted-foreground">Slot Utilization:</span>
                      <span className="font-semibold">{w.active_task_count} / {w.concurrency} ({util}%)</span>
                    </div>
                    <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                      <div
                        className="bg-blue-600 h-2 rounded-full transition-all"
                        style={{ width: `${Math.min(util, 100)}%` }}
                      />
                    </div>
                  </div>

                  <div className="p-3 bg-muted/40 rounded-lg text-xs font-mono space-y-1">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Queues:</span>
                      <span className="font-semibold truncate max-w-[150px]">
                        {w.queues.join(", ")}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Last Heartbeat:</span>
                      <span>{new Date(w.last_heartbeat).toLocaleTimeString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Version:</span>
                      <span>{w.version}</span>
                    </div>
                  </div>

                  {isOnline && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full text-destructive hover:bg-destructive/10 text-xs gap-2"
                      onClick={() => drainWorker.mutate(w.worker_id)}
                      disabled={drainWorker.isPending}
                    >
                      <PowerOff className="w-3.5 h-3.5" />
                      Graceful Drain
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })
        )}
      </div>
    </div>
  );
}
