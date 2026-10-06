"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  useTasks,
  useWorkers,
  useQueues,
  useDrainWorker,
  useCancelTask,
  useRetryTask,
} from "@/lib/api-hooks";
import { TaskStatusBadge } from "@/components/task/task-status-badge";
import { useWebSocketSubscription } from "@/lib/use-websocket";
import {
  Activity,
  Server,
  Layers,
  ListTodo,
  PowerOff,
  RotateCcw,
  XCircle,
  Radio,
  RefreshCw,
  Wifi,
  WifiOff,
} from "lucide-react";

export default function LiveConsolePage() {
  const [selectedQueue, setSelectedQueue] = useState<string | undefined>(undefined);
  const { isConnected, isConnecting, lastEvent } = useWebSocketSubscription({
    channel: "live",
    autoInvalidate: true,
  });

  const { data: tasksData, isLoading: tasksLoading, refetch: refetchTasks } = useTasks({
    queue: selectedQueue,
    limit: 50,
  });
  const { data: workersData, isLoading: workersLoading, refetch: refetchWorkers } = useWorkers();
  const { data: queuesData, isLoading: queuesLoading, refetch: refetchQueues } = useQueues();

  const drainWorker = useDrainWorker();
  const cancelTask = useCancelTask();
  const retryTask = useRetryTask();

  const handleRefreshAll = () => {
    refetchTasks();
    refetchWorkers();
    refetchQueues();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Live Operational Console</h1>
            {isConnected ? (
              <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 text-xs">
                <Radio className="w-3 h-3 mr-1 animate-pulse text-emerald-500" />
                Live WebSocket Stream
              </Badge>
            ) : isConnecting ? (
              <Badge variant="outline" className="bg-amber-500/10 text-amber-600 border-amber-500/20 text-xs">
                <Wifi className="w-3 h-3 mr-1 animate-spin text-amber-500" />
                Connecting Stream...
              </Badge>
            ) : (
              <Badge variant="outline" className="bg-muted text-muted-foreground border-border text-xs">
                <WifiOff className="w-3 h-3 mr-1" />
                Polling Fallback
              </Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time unified state of tasks, active worker assignments, and broker queues.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastEvent && (
            <span className="text-xs font-mono text-muted-foreground bg-muted/50 px-2.5 py-1 rounded-md border border-border">
              Last event: <span className="text-primary font-semibold">{lastEvent.type}</span>
            </span>
          )}
          <Button variant="outline" size="sm" onClick={handleRefreshAll} className="gap-2">
            <RefreshCw className="w-3.5 h-3.5" />
            Synchronize
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Server className="w-4 h-4 text-blue-500" />
                Worker Fleet Roster
              </CardTitle>
              <CardDescription>Live heartbeat status and execution slots</CardDescription>
            </div>
            <span className="text-xs font-mono text-muted-foreground">
              {workersData?.items.length || 0} nodes
            </span>
          </CardHeader>
          <CardContent>
            {workersLoading ? (
              <div className="p-4 text-center text-xs text-muted-foreground">Inspecting workers...</div>
            ) : !workersData?.items.length ? (
              <div className="p-4 text-center text-xs text-muted-foreground">No worker nodes registered.</div>
            ) : (
              <div className="divide-y divide-border max-h-72 overflow-y-auto pr-1">
                {workersData.items.map((w) => {
                  const isDraining = w.status === "draining";
                  return (
                    <div key={w.worker_id} className="py-2.5 flex items-center justify-between text-xs">
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-foreground font-mono">{w.worker_id}</span>
                          <Badge
                            variant={w.status === "active" ? "success" : "warning"}
                            className="text-[10px] px-1.5 py-0"
                          >
                            {w.status}
                          </Badge>
                        </div>
                        <p className="text-[11px] text-muted-foreground font-mono">
                          {w.hostname} • PID {w.process_id} • Queues: [{w.queues.join(", ")}]
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="text-right font-mono text-[11px]">
                          <span className="font-semibold text-foreground">{w.active_task_count}</span>
                          <span className="text-muted-foreground">/{w.concurrency} slots</span>
                        </div>
                        {w.status === "active" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-destructive hover:bg-destructive/10"
                            disabled={drainWorker.isPending}
                            onClick={() => drainWorker.mutate(w.worker_id)}
                            title="Gracefully drain worker"
                          >
                            <PowerOff className="w-3.5 h-3.5" />
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-500" />
                Queue & Broker Backlog
              </CardTitle>
              <CardDescription>Queue depth, broker backend, and throughput limits</CardDescription>
            </div>
            {selectedQueue && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 text-xs"
                onClick={() => setSelectedQueue(undefined)}
              >
                Clear Filter
              </Button>
            )}
          </CardHeader>
          <CardContent>
            {queuesLoading ? (
              <div className="p-4 text-center text-xs text-muted-foreground">Inspecting queues...</div>
            ) : !queuesData?.items.length ? (
              <div className="p-4 text-center text-xs text-muted-foreground">No queues found.</div>
            ) : (
              <div className="divide-y divide-border max-h-72 overflow-y-auto pr-1">
                {queuesData.items.map((q) => {
                  const isFiltered = selectedQueue === q.queue_name;
                  return (
                    <div
                      key={q.queue_name}
                      onClick={() =>
                        setSelectedQueue(isFiltered ? undefined : q.queue_name)
                      }
                      className={`py-2.5 flex items-center justify-between text-xs cursor-pointer rounded-md px-2.5 transition-all ${
                        isFiltered
                          ? "border-2 border-foreground bg-accent font-medium shadow-sm ring-1 ring-foreground/20"
                          : "border border-transparent hover:bg-muted/50"
                      }`}
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-foreground font-mono">{q.queue_name}</span>
                          <Badge variant="outline" className="text-[10px] font-mono">
                            {q.broker_backend}
                          </Badge>
                        </div>
                        <p className="text-[11px] text-muted-foreground">
                          Rate limit: {q.rate_limit_rps || 100} RPS • Max concurrency: {q.max_concurrency}
                        </p>
                      </div>
                      <div className="text-right font-mono text-[11px]">
                        <span className="text-muted-foreground">Priority: </span>
                        <span className="font-semibold">{q.default_priority}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Main Section: Live Task Stream with Mandatory Status Reasons */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <ListTodo className="w-4 h-4 text-emerald-500" />
              Live Task Stream
              {selectedQueue && (
                <Badge variant="outline" className="text-xs font-mono ml-2">
                  Filtered by: {selectedQueue}
                </Badge>
              )}
            </CardTitle>
            <CardDescription>
              Every task displays its mandatory status explanation (SRS §17.18.1)
            </CardDescription>
          </div>
          <span className="text-xs text-muted-foreground font-mono">
            {tasksData?.items.length || 0} active records
          </span>
        </CardHeader>
        <CardContent>
          {tasksLoading ? (
            <div className="p-8 text-center text-sm text-muted-foreground">Loading task stream...</div>
          ) : !tasksData?.items.length ? (
            <div className="p-8 text-center text-sm text-muted-foreground">
              No tasks currently matching filter.
            </div>
          ) : (
            <div className="divide-y divide-border overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-border text-muted-foreground font-mono">
                    <th className="py-2 px-3">Task ID / Type</th>
                    <th className="py-2 px-3">Queue</th>
                    <th className="py-2 px-3">Status & Reason (SRS §17.18.1)</th>
                    <th className="py-2 px-3">Attempts</th>
                    <th className="py-2 px-3">Created</th>
                    <th className="py-2 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {tasksData.items.map((task) => (
                    <tr key={task.task_id} className="hover:bg-muted/40 transition-colors">
                      <td className="py-3 px-3">
                        <Link
                          href={`/tasks/${task.task_id}`}
                          className="font-semibold text-foreground hover:underline block"
                        >
                          {task.task_type}
                        </Link>
                        <span className="font-mono text-[10px] text-muted-foreground">
                          {task.task_id}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-mono">{task.queue}</td>
                      <td className="py-3 px-3 max-w-sm">
                        <TaskStatusBadge task={task} showReason={true} />
                      </td>
                      <td className="py-3 px-3 font-mono">
                        {task.attempt_count} / {task.max_attempts}
                      </td>
                      <td className="py-3 px-3 text-muted-foreground font-mono text-[11px]">
                        {new Date(task.created_at).toLocaleTimeString()}
                      </td>
                      <td className="py-3 px-3 text-right space-x-1">
                        {["PENDING", "QUEUED", "RUNNING"].includes(task.status) && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-destructive hover:bg-destructive/10"
                            onClick={() => cancelTask.mutate(task.task_id)}
                            title="Cancel task execution"
                          >
                            <XCircle className="w-3.5 h-3.5" />
                          </Button>
                        )}
                        {["FAILED", "DEAD"].includes(task.status) && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-primary hover:bg-primary/10"
                            onClick={() => retryTask.mutate(task.task_id)}
                            title="Retry task manually"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
